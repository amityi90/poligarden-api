from __future__ import annotations

import math
import time

import numpy as np

from app.models.plant import Plant

# ── Tunable globals (single source of truth — change here) ────────────────────
GRID_STEP       = 0.02   # candidate-grid spacing in metres (2 cm)
NEIGHBOR_RADIUS = 2.0    # ecological interaction radius in metres
COMPANION_W     = 2.0    # IDW weight for a companion neighbour
ANTAGONIST_W    = -1.0   # IDW weight for an antagonist neighbour
SELF_REPULSION_W = -0.5  # IDW penalty per same-species neighbour (spreads a species apart)
EPS             = 0.05   # distance floor so the IDW score can't blow up
PROGRESS_FLUSH_SECONDS = 0.25   # how often to stream a partial layout to the UI
PROGRESS_FLUSH_EVERY_N = 200    # …or after this many placements, whichever first
# Local-diversity demotion: if the top-scored species already occupies more than
# its fair share of footprint area within the NEIGHBOR_RADIUS circle, prefer the
# next-best species. "Fair share" = 1 / (number of selected species).
DIVERSITY_FACTOR = 1.5   # over-representation multiple of fair share before demoting
DIVERSITY_TOP_K  = 3     # how many top-scored species the demotion may walk
MIN_LOCAL_PLANTS = 3     # below this many neighbours the circle is too sparse to judge
# Each species is issued ≈ this × the largest plant's footprint area per stack
# cycle (N_i = max(1, round(M·(s_max/spread_i)²))). It scales the whole cycle
# length without changing per-species ratios: lower = shorter cycles = smaller
# end-of-cycle bands = finer local mixing.
# Sweep (8×6 m, 6 species) — 1.0 gave the lowest local dominant share (0.226 vs
# 0.245 at 2.0), the best global area-balance, at ~6% fewer plants. 1.0 is the
# floor: below it the max(1,…) clamp starts pinning mid-size species and skews
# balance.
STACK_AREA_MULTIPLIER = 1.0
# Second pass: after the field is packed, fill the leftover gaps with the
# smallest plants only (at their real size), planted diversely — maximises land use.
FILL_GAPS_PASS = True
FILLER_SPREAD_GROUPS = 2     # filler pool = species in the N smallest distinct spread values
FILLER_GRID_STEP = GRID_STEP # pass-2 grid step (coarsen to trade gap coverage for speed)


class GardenLayout:
    """
    Ecological Circle Packing — packs variable-sized circular plant footprints
    into a bounded box (<= 20 x 20 m), favouring companions and avoiding
    antagonists via inverse-distance-weighted scoring, with per-species
    volumetric inventory equalisation.

    Output GeoJSON matches field_layout2.to_geojson()'s `plant_instance`
    contract (one MultiPoint feature per species) so the existing UI canvases
    and the PDF renderer consume it unchanged. Each feature additionally carries
    companion/antagonist ids+names (restricted to the selected set) to drive the
    summary hover effect.
    """

    def __init__(self, field_length: float, field_width: float, plants: list[Plant]):
        self.X = float(field_length)
        self.Y = float(field_width)
        self.plants = plants                       # non-tree plants only (filtered upstream)

        # one entry per species that actually got placed; same shape as field_layout2
        self._plant_points: dict[int, dict] = {}

        # placed circles as flat parallel arrays (no shapely/geopandas in the hot loop)
        self._cx: list[float] = []
        self._cy: list[float] = []
        self._cr: list[float] = []
        self._cspecies: list[int] = []             # index into self.plants

    # ── public API ────────────────────────────────────────────────────────────

    def build(self, on_progress=None, progress_every_s: float = PROGRESS_FLUSH_SECONDS,
              progress_every_n: int = PROGRESS_FLUSH_EVERY_N) -> "GardenLayout":
        species = self.plants
        n_sp = len(species)
        if n_sp == 0:
            if on_progress:
                on_progress(self)
            return self

        radii = [p.spread / 100 / 2 for p in species]   # circle radius, metres
        spread_m = [p.spread / 100 for p in species]     # spread, metres
        s_max = max(spread_m)
        max_radius = max(radii)
        sp_id = [p.id for p in species]

        # companion / antagonist id sets, restricted to the selected set
        sel_ids = {p.id for p in species}
        name_by_id = {p.id: p.name for p in species}
        comp_ids = [{c.id for c in p.companion_plants}    & sel_ids for p in species]
        anta_ids = [{a.id for a in p.antagonistic_plants} & sel_ids for p in species]

        # per-species feature metadata (computed once, copied on first placement)
        self._meta = [
            {
                "plant_name":       species[i].name,
                "spread_m":         round(spread_m[i], 2),
                "radius_m":         round(radii[i], 4),
                "height_m":         round(species[i].height / 100, 2),
                "companion_ids":    sorted(comp_ids[i]),
                "antagonist_ids":   sorted(anta_ids[i]),
                "companion_names":  sorted(name_by_id[cid] for cid in comp_ids[i]),
                "antagonist_names": sorted(name_by_id[aid] for aid in anta_ids[i]),
            }
            for i in range(n_sp)
        ]

        # Volumetric stack equalisation: V_target = M * area(largest); each
        # species' inventory is inversely proportional to its footprint area.
        v_target = STACK_AREA_MULTIPLIER * math.pi * (s_max / 2) ** 2

        def init_stacks() -> list[int]:
            return [max(1, round(v_target / (math.pi * (spread_m[i] / 2) ** 2)))
                    for i in range(n_sp)]

        # Uniform spatial hash. Cell sized so the 3x3 block around a candidate
        # captures every neighbour relevant to BOTH scoring (<= NEIGHBOR_RADIUS)
        # and collision (<= r_new + r_neighbor <= 2*max_radius).
        cell = max(NEIGHBOR_RADIUS, 2 * max_radius)
        buckets: dict[tuple[int, int], list[int]] = {}

        def bkey(x: float, y: float) -> tuple[int, int]:
            return (int(x // cell), int(y // cell))

        def neighbor_indices(x: float, y: float):
            bx, by = bkey(x, y)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    b = buckets.get((bx + dx, by + dy))
                    if b:
                        yield from b

        last_flush = time.perf_counter()
        since_flush = 0
        if on_progress:
            on_progress(self)   # initial (empty) flush so the UI starts rendering

        def run_pass(candidates: list[int], stock, grid_step: float) -> None:
            """One grid sweep. `candidates` = species indices allowed to be placed.
            `stock` = per-species inventory (gate + replenish) or None for an
            unlimited pass. Shares the placed-circle arrays + buckets across passes
            so collisions/diversity see everything placed so far."""
            nonlocal last_flush, since_flush
            use_stock = stock is not None
            xs = np.arange(grid_step, self.X, grid_step)
            ys = np.arange(grid_step, self.Y, grid_step)

            for gx_np in xs:
                gx = float(gx_np)
                for gy_np in ys:
                    gy = float(gy_np)

                    if use_stock and all(s <= 0 for s in stock):
                        stock = init_stacks()   # replenish when every stack is spent

                    cand = list(neighbor_indices(gx, gy))

                    # Stage 2a — skip if this point falls inside an existing circle
                    covered = False
                    for k in cand:
                        ddx = gx - self._cx[k]
                        ddy = gy - self._cy[k]
                        if ddx * ddx + ddy * ddy < self._cr[k] * self._cr[k]:
                            covered = True
                            break
                    if covered:
                        continue

                    # Stage 2b — neighbours within the interaction radius (for scoring)
                    # plus per-species footprint area in the circle (for diversity).
                    near: list[tuple[float, int]] = []
                    local_area = [0.0] * n_sp
                    local_total = 0.0
                    local_count = 0
                    for k in cand:
                        d = math.hypot(gx - self._cx[k], gy - self._cy[k])
                        if d <= NEIGHBOR_RADIUS:
                            k_sp = self._cspecies[k]
                            near.append((d, k_sp))
                            a = math.pi * self._cr[k] * self._cr[k]
                            local_area[k_sp] += a
                            local_total += a
                            local_count += 1

                    # Stage 3 — rank candidate species by IDW score, then apply a
                    # local-diversity demotion: if the top pick already over-fills the
                    # circle (> fair share × DIVERSITY_FACTOR), prefer the next best.
                    ranked: list[tuple[float, int]] = []
                    for i in candidates:
                        if use_stock and stock[i] <= 0:
                            continue
                        score = 0.0
                        ci = comp_ids[i]
                        ai = anta_ids[i]
                        for d, k_sp in near:
                            if k_sp == i:                     # same species → self-repulsion
                                score += SELF_REPULSION_W / max(d, EPS)
                                continue
                            nid = sp_id[k_sp]
                            if nid in ci:
                                score += COMPANION_W / max(d, EPS)
                            elif nid in ai:
                                score += ANTAGONIST_W / max(d, EPS)
                        ranked.append((score, i))
                    if not ranked:
                        continue
                    ranked.sort(key=lambda t: t[0], reverse=True)   # stable → ties keep lower index

                    best_i = ranked[0][1]
                    if local_count >= MIN_LOCAL_PLANTS and local_total > 0:
                        threshold = DIVERSITY_FACTOR / n_sp
                        for _, i in ranked[:DIVERSITY_TOP_K]:
                            if local_area[i] / local_total <= threshold:
                                best_i = i
                                break
                        # else: all top-K over-represented → keep ranked[0] (fallback)

                    # Stage 4 — boundary + collision checks, then commit
                    r = radii[best_i]
                    if gx - r < 0 or gx + r > self.X or gy - r < 0 or gy + r > self.Y:
                        continue
                    overlaps = False
                    for k in cand:
                        if math.hypot(gx - self._cx[k], gy - self._cy[k]) < r + self._cr[k]:
                            overlaps = True
                            break
                    if overlaps:
                        continue

                    self._commit(best_i, gx, gy, r)
                    buckets.setdefault(bkey(gx, gy), []).append(len(self._cx) - 1)
                    if use_stock:
                        stock[best_i] -= 1

                    # Periodic partial flush for progressive streaming to the UI
                    since_flush += 1
                    now = time.perf_counter()
                    if on_progress and (since_flush >= progress_every_n
                                        or now - last_flush >= progress_every_s):
                        on_progress(self)
                        last_flush = now
                        since_flush = 0

        # Pass 1 — main packing (volumetric stacks on).
        run_pass(list(range(n_sp)), init_stacks(), GRID_STEP)

        # Pass 2 — fill the leftover gaps with the smallest plants (no stacks):
        # the species in the FILLER_SPREAD_GROUPS smallest distinct spread values
        # (e.g. all 10 cm + all 15 cm plants), at real size, picked by best
        # companion compatibility from the top-3 scores. Streams via the same
        # on_progress, and the job is marked done only after this returns.
        if FILL_GAPS_PASS:
            distinct = sorted({species[i].spread for i in range(n_sp)})   # cm, ascending
            target = set(distinct[:FILLER_SPREAD_GROUPS])                 # smallest spread groups
            smallest_pool = [i for i in range(n_sp) if species[i].spread in target]
            if smallest_pool:
                run_pass(smallest_pool, None, FILLER_GRID_STEP)

        if on_progress:
            on_progress(self)   # final flush (== full layout)
        return self

    def _commit(self, i: int, x: float, y: float, r: float) -> None:
        pid = self.plants[i].id
        self._cx.append(x)
        self._cy.append(y)
        self._cr.append(r)
        self._cspecies.append(i)

        entry = self._plant_points.get(pid)
        if entry is None:
            entry = dict(self._meta[i])
            entry["coords"] = []
            self._plant_points[pid] = entry
        entry["coords"].append([round(x, 4), round(y, 4)])

    def to_geojson(self) -> dict:
        """One MultiPoint `plant_instance` feature per species (UI/PDF contract),
        preceded by a `garden_bounds` Polygon so the 2D canvas can derive the
        field extent (it sizes from Polygon features). The bounds polygon is not
        drawn by the canvas/PDF (unknown type → skipped) but defines the box."""
        features = [{
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [0.0, 0.0], [self.X, 0.0], [self.X, self.Y], [0.0, self.Y], [0.0, 0.0],
                ]],
            },
            "properties": {"type": "garden_bounds"},
        }]
        for pid, data in self._plant_points.items():
            if not data["coords"]:
                continue
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "MultiPoint",
                    "coordinates": data["coords"],
                },
                "properties": {
                    "type":             "plant_instance",
                    "plant_id":         int(pid),
                    "plant_name":       data["plant_name"],
                    "spread_m":         data["spread_m"],
                    "radius_m":         data["radius_m"],
                    "height_m":         data["height_m"],
                    "companion_ids":    data["companion_ids"],
                    "antagonist_ids":   data["antagonist_ids"],
                    "companion_names":  data["companion_names"],
                    "antagonist_names": data["antagonist_names"],
                },
            })
        return {"type": "FeatureCollection", "features": features}
