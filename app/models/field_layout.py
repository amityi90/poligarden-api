from __future__ import annotations
import bisect
import math
import time
from shapely.geometry import Point
from app.models.pv_system import PVSystem, PANEL_WIDTH_M, PANEL_HEIGHT_M, ROW_SPACING
from app.models.plant import Plant

ROW_HEIGHT = 2.0   # plant row height in metres (north–south)
GAP_HEIGHT = 0.5   # tractor path gap height in metres


def _rect_coords(x0: float, y0: float, x1: float, y1: float) -> list:
    """Return a closed GeoJSON polygon ring for a rectangle — no Shapely needed."""
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]


def _flat_sorted(plants: list, key=lambda p: p.spread) -> list:
    """Return plants filtered to those that fit in a row, sorted by spread."""
    return sorted([p for p in plants if p.spread / 100 <= ROW_HEIGHT], key=key)


def _deduped_sorted(plants: list) -> list:
    """Deduplicate by id, sort smallest-first."""
    seen: dict = {}
    for p in plants:
        if p.id not in seen:
            seen[p.id] = p
    return sorted(seen.values(), key=lambda p: p.spread)


class FieldLayout:
    """
    Builds the full field geometry and serialises it to a GeoJSON FeatureCollection.

    Coordinate system:
        (0, 0) = south-west corner of the field
        X axis = east  (0 → field_length)
        Y axis = north (0 → field_width)

    Feature types:
        "plant_row"      – 2 m tall background rectangle, full field length
        "gap"            – 0.5 m tractor path
        "pv_row"         – individual solar panel rectangles
        "shadow"         – shaded area north of each PV row
        "tree"           – circle polygon sized to tree spread
        "plant_instance" – Point at circle centre; radius_m in properties
    """

    def __init__(
        self,
        field_length: float,
        field_width: float,
        pv_system: PVSystem,
        trees: list[Plant] | None = None,
        shadow_groups: list | None = None,
        sun_groups: list | None = None,
        non_tree_plants: list[Plant] | None = None,
        shadow_ungrouped: list[Plant] | None = None,
        sun_ungrouped: list[Plant] | None = None,
        neutral_plants: list[Plant] | None = None,
    ):
        self.field_length     = field_length
        self.field_width      = field_width
        self.pv_system        = pv_system
        self.trees            = trees or []
        self.shadow_groups    = shadow_groups or []
        self.sun_groups       = sun_groups or []
        self.non_tree_plants  = non_tree_plants or []
        self.shadow_ungrouped = shadow_ungrouped or []
        self.sun_ungrouped    = sun_ungrouped or []
        self.neutral_plants   = neutral_plants or []

        # Rectangular structural features (plant rows, gaps, PV panels, shadows):
        # coords are pre-built lists — no Shapely needed.
        self._rect_coords: list[list] = []
        self._rect_props:  list[dict] = []
        # Tree circle features — Shapely buffer (few dozen at most).
        self._tree_geoms:  list       = []
        self._tree_props:  list[dict] = []
        # Plant instances aggregated by species → one MultiPoint per plant.
        # {plant_id: {"plant_name":…, "spread_m":…, "radius_m":…, "coords":[…]}}
        self._plant_points: dict[int, dict] = {}

        self._row_y_bottoms: list[float] = []
        self._tree_zones: dict[int, list] = {}
        self._tree_row_indices: set[int] = set()
        self._shadow_y_ranges: list[tuple[float, float]] = []
        self._row_metadata: list[dict] = []
        self._tree_placements: dict[int, list] = {}

    # ── public API ────────────────────────────────────────────────────────────

    def build(self) -> FieldLayout:
        t0 = time.perf_counter()
        self._build_plant_rows()
        self._build_pv_rows()
        self._mark_shadow_rows()
        if self.trees:
            self._build_tree_rows()
            self._mark_tree_rows()
        t1 = time.perf_counter()
        self._pack_plant_rows()
        t2 = time.perf_counter()
        print(f"[build] setup={t1-t0:.3f}s  pack={t2-t1:.3f}s  total={t2-t0:.3f}s")
        return self

    def to_geojson(self) -> dict:
        features = []

        # 1. Rectangular structural features — coords already pre-built, no Shapely
        for coords, props in zip(self._rect_coords, self._rect_props):
            features.append({
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [coords]},
                "properties": props,
            })

        # 2. Tree circle features — convert Shapely buffer polygon
        for geom, props in zip(self._tree_geoms, self._tree_props):
            coords = [list(c) for c in geom.exterior.coords]
            features.append({
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [coords]},
                "properties": props,
            })

        # 3. Plant instances — one MultiPoint per species.
        #    All placements of a species share a single GeoJSON feature,
        #    reducing ~100k features to ~35 and keeping the response small.
        #
        #    UI rendering note:
        #      feature.geometry.type  === "MultiPoint"
        #      feature.geometry.coordinates  → [[x,y], [x,y], …]   (one per plant)
        #      feature.properties.radius_m   → circle radius in metres
        #    For each coordinate, draw a filled circle of that radius centred at (x, y).
        for plant_id, data in self._plant_points.items():
            features.append({
                "type": "Feature",
                "geometry": {"type": "MultiPoint", "coordinates": data["coords"]},
                "properties": {
                    "type":       "plant_instance",
                    "plant_id":   plant_id,
                    "plant_name": data["plant_name"],
                    "spread_m":   data["spread_m"],
                    "radius_m":   data["radius_m"],
                },
            })

        return {"type": "FeatureCollection", "features": features}

    # ── primitive emitters ────────────────────────────────────────────────────

    def _emit_plant(self, cx: float, cy: float, plant, row_index: int = -1) -> None:
        """Accumulate a plant instance into the per-species MultiPoint bucket."""
        pid = plant.id
        if pid not in self._plant_points:
            size   = plant.spread / 100
            radius = size / 2
            self._plant_points[pid] = {
                "plant_name": plant.name,
                "spread_m":   round(size, 2),
                "radius_m":   round(radius, 4),
                "coords":     [],
            }
        self._plant_points[pid]["coords"].append([round(cx, 4), round(cy, 4)])

    # ── core packing primitives ───────────────────────────────────────────────

    def _fill_rect(
        self,
        x0: float, y0_abs: float,
        w: float, h: float,
        fillers: list,          # sorted smallest-first
        row_index: int = -1,
    ) -> None:
        """
        Fill a rectangle with filler plants using largest-fit, row-by-row.
        (x0, y0_abs) is the absolute bottom-left corner; (w, h) is the size.
        Uses binary search (O log n) to find the largest fitting plant.
        """
        if w <= 0 or h <= 0 or not fillers:
            return
        sizes = [f.spread / 100 for f in fillers]   # pre-cached, sorted asc
        sm    = sizes[0]
        ly    = 0.0
        while ly + sm <= h:
            lx    = 0.0
            max_h = 0.0
            while lx + sm <= w:
                max_size = min(w - lx, h - ly)
                idx = bisect.bisect_right(sizes, max_size + 1e-9) - 1
                if idx < 0:
                    break
                s    = sizes[idx]
                best = fillers[idx]
                r    = s / 2
                self._emit_plant(x0 + lx + r, y0_abs + ly + r, best, row_index)
                lx    += s
                max_h  = max(max_h, s)
            if max_h == 0:
                break
            ly += max_h

    def _pack_columns(
        self,
        x_start: float, x_end: float,
        y_abs: float,
        row_index: int,
        main_plants: list,   # sorted smallest-first, pre-filtered ≤ ROW_HEIGHT
        gap_fillers: list,   # sorted smallest-first, for gaps within columns
    ) -> list:
        """
        Pack columns of main_plants into [x_start, x_end] × [y_abs, y_abs+ROW_HEIGHT].

        Cycles through main_plants for diversity. After each column is height-full,
        fills the gap above the last plant and beside any narrower plants with
        gap_fillers.

        Returns list of (col_x_start, col_x_end) intervals so the caller can
        identify and fill the x-gaps between columns without overlap.
        """
        if not main_plants:
            return []

        eff_fillers  = gap_fillers if gap_fillers else main_plants
        main_sizes   = [p.spread / 100 for p in main_plants]   # pre-cached
        n_main       = len(main_plants)
        col_intervals: list = []
        filler_idx   = 0
        curr_x       = x_start

        while curr_x < x_end:
            col_y       = 0.0
            col_width   = 0.0
            col_plants: list = []
            col_x_start = curr_x

            while col_y < ROW_HEIGHT:
                idx   = filler_idx % n_main
                plant = main_plants[idx]
                size  = main_sizes[idx]
                if col_y + size > ROW_HEIGHT or curr_x + size > x_end:
                    break
                r = size / 2
                self._emit_plant(curr_x + r, y_abs + col_y + r, plant, row_index)
                col_plants.append((curr_x, col_y, size))
                col_y     += size
                col_width  = max(col_width, size)
                filler_idx += 1

            if col_width == 0:
                break   # no plant fits — region too narrow

            # Close column: fill gap above and beside narrower plants
            self._fill_rect(curr_x, y_abs + col_y, col_width, ROW_HEIGHT - col_y,
                            eff_fillers, row_index)
            for px, py, ps in col_plants:
                side_w = col_width - ps
                if side_w > 1e-6:
                    self._fill_rect(px + ps, y_abs + py, side_w, ps,
                                    eff_fillers, row_index)

            curr_x += col_width
            col_intervals.append((col_x_start, curr_x))

        return col_intervals

    def _fill_x_gaps(
        self,
        x_start: float, x_end: float,
        y_abs: float,
        col_intervals: list,
        fillers: list,
        row_index: int = -1,
    ) -> None:
        """
        Fill horizontal gaps between column intervals with filler plants.
        Uses column intervals (not individual plant positions) so we never
        re-enter space already covered by _pack_columns.
        """
        if not fillers:
            return
        if not col_intervals:
            self._fill_rect(x_start, y_abs, x_end - x_start, ROW_HEIGHT, fillers, row_index)
            return
        prev = x_start
        for s, e in col_intervals:
            if s - prev > 1e-6:
                self._fill_rect(prev, y_abs, s - prev, ROW_HEIGHT, fillers, row_index)
            prev = e
        if x_end - prev > 1e-6:
            self._fill_rect(prev, y_abs, x_end - prev, ROW_HEIGHT, fillers, row_index)

    # ── row packing dispatch ──────────────────────────────────────────────────

    def _apply_row_template(
        self,
        cache: dict,
        cache_key: tuple,
        x_start: float, x_end: float,
        y_abs: float, row_index: int,
        main: list, fillers: list, neutral: list,
    ) -> None:
        """
        Pack a standard (non-tree) row using a template cache.

        On the first call for a given (x_start, x_end, plant-list combination),
        runs _pack_columns + _fill_x_gaps normally and records every emitted
        plant as a (rel_cx, rel_cy, …) tuple relative to (x_start, y_abs).

        On subsequent calls with the same key, replays the recorded template —
        just appending coordinates — without re-running the packing algorithm.
        For a 200 m field with 80 regular rows this is an ~80× speedup.
        """
        if cache_key in cache:
            for rel_cx, rel_cy, pid, pname, sm, rm in cache[cache_key]:
                if pid not in self._plant_points:
                    self._plant_points[pid] = {
                        "plant_name": pname,
                        "spread_m":   sm,
                        "radius_m":   rm,
                        "coords":     [],
                    }
                self._plant_points[pid]["coords"].append(
                    [round(x_start + rel_cx, 4), round(y_abs + rel_cy, 4)]
                )
            return

        # ── first call: run packing and record the delta ──────────────────────
        snapshot = {pid: len(d["coords"]) for pid, d in self._plant_points.items()}

        cols = self._pack_columns(x_start, x_end, y_abs, row_index, main, fillers)
        self._fill_x_gaps(x_start, x_end, y_abs, cols, neutral, row_index)

        template: list = []
        for pid, data in self._plant_points.items():
            start = snapshot.get(pid, 0)
            if len(data["coords"]) > start:
                pname, sm, rm = data["plant_name"], data["spread_m"], data["radius_m"]
                for cx, cy in data["coords"][start:]:
                    template.append((cx - x_start, cy - y_abs, pid, pname, sm, rm))
        cache[cache_key] = template

    def _pack_plant_rows(self) -> None:
        """Dispatch each plant row to the appropriate packing strategy."""

        # Pre-compute flat sorted plant lists once — not per row.
        def _groups_to_plants(groups):
            return _flat_sorted([p for g in groups for p in g.plants])

        def _groups_to_fillers(groups):
            return _deduped_sorted(
                [p for g in groups for p in g.non_antagonistic_plants
                 if p.spread / 100 <= ROW_HEIGHT]
            )

        sun_main    = _groups_to_plants(self.sun_groups)
        sun_fillers = _groups_to_fillers(self.sun_groups) or sun_main

        shadow_main    = _groups_to_plants(self.shadow_groups)
        shadow_fillers = _groups_to_fillers(self.shadow_groups) or shadow_main

        neutral = _flat_sorted(self.neutral_plants)


        # Template caches keyed by (x_start, x_end, id(main), id(fillers), id(neutral)).
        # Using list identity (id) is safe because the lists are built once above.
        row_cache: dict = {}

        t_tree = t_adj = t_shadow = t_sun = 0.0
        n_tree = n_adj = n_shadow = n_sun = 0

        for row_index, row_y_bottom in enumerate(self._row_y_bottoms):
            meta = self._row_metadata[row_index]
            _t = time.perf_counter()

            if meta["is_tree_row"]:
                self._pack_tree_row(row_index, row_y_bottom)
                t_tree += time.perf_counter() - _t; n_tree += 1

            elif meta["is_above_tree_row"] or meta["is_below_tree_row"]:
                self._pack_adjacent_tree_row(row_index, row_y_bottom)
                t_adj += time.perf_counter() - _t; n_adj += 1

            elif meta["is_in_shadow"]:
                n = neutral or shadow_fillers
                self._apply_row_template(
                    row_cache,
                    (0.0, self.field_length, id(shadow_main), id(shadow_fillers), id(n)),
                    0.0, self.field_length, row_y_bottom, row_index,
                    shadow_main, shadow_fillers, n,
                )
                t_shadow += time.perf_counter() - _t; n_shadow += 1

            else:
                n = neutral or sun_fillers
                self._apply_row_template(
                    row_cache,
                    (0.0, self.field_length, id(sun_main), id(sun_fillers), id(n)),
                    0.0, self.field_length, row_y_bottom, row_index,
                    sun_main, sun_fillers, n,
                )
                t_sun += time.perf_counter() - _t; n_sun += 1

        print(
            f"[pack] rows: tree={n_tree}({t_tree:.3f}s)  "
            f"adj={n_adj}({t_adj:.3f}s)  "
            f"shadow={n_shadow}({t_shadow:.3f}s)  "
            f"sun={n_sun}({t_sun:.3f}s)"
        )

    # ── tree-adjacent row packing ─────────────────────────────────────────────

    def _pack_adjacent_tree_row(self, row_index: int, row_y_bottom: float) -> None:
        """
        Pack a row directly above or below a tree row.
        Divides the row into sections — one per adjacent tree.
        Each section is packed with that tree's companion_groups.
        """
        meta = self._row_metadata[row_index]
        tree_row_index = (row_index + 1) if meta["is_above_tree_row"] else (row_index - 1)

        placements = sorted(
            self._tree_placements.get(tree_row_index, []), key=lambda t: t[0]
        )
        if not placements:
            return

        n = len(placements)
        for i, (x, r, tree) in enumerate(placements):
            left = (
                0.0 if i == 0
                else (placements[i - 1][0] + placements[i - 1][1] + x - r) / 2
            )
            right = (
                self.field_length if i == n - 1
                else (x + r + placements[i + 1][0] - placements[i + 1][1]) / 2
            )
            if not tree.companion_groups or right - left <= 0:
                continue

            main    = _flat_sorted([p for g in tree.companion_groups for p in g.plants])
            fillers = _deduped_sorted(
                [p for g in tree.companion_groups for p in g.non_antagonistic_plants
                 if p.spread / 100 <= ROW_HEIGHT]
            ) or main
            if not main:
                continue

            cols = self._pack_columns(left, right, row_y_bottom, row_index, main, fillers)
            self._fill_x_gaps(left, right, row_y_bottom, cols, fillers, row_index)

    # ── tree row packing ──────────────────────────────────────────────────────

    def _pack_tree_row(self, row_index: int, row_y_bottom: float) -> None:
        """Pack plants in the gaps between trees in a tree row."""
        placements = sorted(self._tree_placements.get(row_index, []), key=lambda t: t[0])
        if not placements:
            return

        # Build gap list: (gap_start, gap_end, left_tree_or_None, right_tree_or_None)
        gaps: list = []
        fx, fr, ft = placements[0]
        if fx - fr > 1e-6:
            gaps.append((0.0, fx - fr, None, ft))
        for i in range(len(placements) - 1):
            lx, lr, lt = placements[i]
            rx, rr, rt = placements[i + 1]
            gs, ge = lx + lr, rx - rr
            if ge - gs > 1e-6:
                gaps.append((gs, ge, lt, rt))
        lx, lr, lt = placements[-1]
        if self.field_length - (lx + lr) > 1e-6:
            gaps.append((lx + lr, self.field_length, lt, None))

        for gap_start, gap_end, left_tree, right_tree in gaps:
            fillers = self._build_gap_fillers(left_tree, right_tree)
            if not fillers:
                continue
            cols = self._pack_columns(gap_start, gap_end, row_y_bottom,
                                      row_index, fillers, fillers)
            self._fill_x_gaps(gap_start, gap_end, row_y_bottom, cols, fillers, row_index)

    def _build_gap_fillers(self, left_tree, right_tree) -> list:
        """
        Build the plant list for a gap between two trees.
        Prefers companion_non_tree_plants of either tree; pads with
        non_antagonistic_plants if fewer than 6 candidates.
        Returns sorted smallest-first.
        """
        def ant_ids(plant):
            return {a.id for a in plant.antagonistic_plants}

        tree_ant_ids: set[int] = set()
        for tree in (left_tree, right_tree):
            if tree:
                tree_ant_ids |= ant_ids(tree)

        candidates: list = []
        seen_ids:   set  = set()

        def _try_add(p) -> bool:
            if p.id in seen_ids or p.id in tree_ant_ids:
                return False
            existing_ids = {c.id for c in candidates}
            if ant_ids(p) & existing_ids:
                return False
            if p.id in {a.id for c in candidates for a in c.antagonistic_plants}:
                return False
            candidates.append(p)
            seen_ids.add(p.id)
            return True

        for tree in (left_tree, right_tree):
            if tree:
                for p in tree.companion_non_tree_plants:
                    _try_add(p)

        if len(candidates) < 6:
            for tree in (left_tree, right_tree):
                if tree:
                    for p in tree.non_antagonistic_plants:
                        if len(candidates) >= 6:
                            break
                        _try_add(p)

        return _flat_sorted(candidates)

    # ── plant row backgrounds ─────────────────────────────────────────────────

    def _build_plant_rows(self) -> None:
        y, row_index = 0.0, 0
        while y + ROW_HEIGHT <= self.field_width:
            self._row_y_bottoms.append(y)
            self._rect_coords.append(_rect_coords(0, y, self.field_length, y + ROW_HEIGHT))
            self._rect_props.append({"type": "plant_row", "row_index": row_index})
            self._row_metadata.append({
                "row_index":         row_index,
                "y_bottom":          round(y, 4),
                "is_tree_row":       False,
                "is_above_tree_row": False,
                "is_below_tree_row": False,
                "is_in_shadow":      False,
            })
            y += ROW_HEIGHT
            row_index += 1
            if y + GAP_HEIGHT <= self.field_width:
                self._rect_coords.append(_rect_coords(0, y, self.field_length, y + GAP_HEIGHT))
                self._rect_props.append({"type": "gap"})
                y += GAP_HEIGHT

    def _mark_shadow_rows(self) -> None:
        for meta in self._row_metadata:
            y0, y1 = meta["y_bottom"], meta["y_bottom"] + ROW_HEIGHT
            for s0, s1 in self._shadow_y_ranges:
                if y0 < s1 and y1 > s0:
                    meta["is_in_shadow"] = True
                    break

    def _mark_tree_rows(self) -> None:
        for meta in self._row_metadata:
            i = meta["row_index"]
            meta["is_tree_row"]       = i in self._tree_row_indices
            meta["is_above_tree_row"] = (i + 1) in self._tree_row_indices
            meta["is_below_tree_row"] = (i - 1) in self._tree_row_indices

    # ── PV rows ───────────────────────────────────────────────────────────────

    def _build_pv_rows(self) -> None:
        pv             = self.pv_system
        panels_per_row = math.floor(self.field_length / PANEL_WIDTH_M)
        if panels_per_row == 0:
            return

        total_panels  = pv.num_panels
        pv_row_index  = 0
        y             = 0.0
        panels_placed = 0

        while panels_placed < total_panels and y + PANEL_HEIGHT_M <= self.field_width:
            remaining  = total_panels - panels_placed
            row_panels = min(panels_per_row, remaining)
            row_kw     = round(row_panels * 450 / 1000, 2)

            for i in range(row_panels):
                x0 = i * PANEL_WIDTH_M
                self._rect_coords.append(_rect_coords(x0, y, x0 + PANEL_WIDTH_M, y + PANEL_HEIGHT_M))
                self._rect_props.append({"type": "pv_row", "row_index": pv_row_index, "kw": row_kw})

            panels_placed += row_panels
            pv_row_index  += 1

            shadow_start = y + PANEL_HEIGHT_M
            shadow_end   = shadow_start + pv.shadow_length
            if shadow_start < self.field_width:
                clipped_end = min(shadow_end, self.field_width)
                self._shadow_y_ranges.append((shadow_start, clipped_end))
                self._rect_coords.append(_rect_coords(0, shadow_start, self.field_length, clipped_end))
                self._rect_props.append({
                    "type":            "shadow",
                    "row_index":       pv_row_index - 1,
                    "shadow_length_m": round(pv.shadow_length, 2),
                })

            raw_step = PANEL_HEIGHT_M + 2 * pv.shadow_length
            y += math.ceil(raw_step / ROW_SPACING) * ROW_SPACING

    # ── tree rows ─────────────────────────────────────────────────────────────

    def _build_tree_rows(self) -> None:
        pv             = self.pv_system
        raw_step       = PANEL_HEIGHT_M + 2 * pv.shadow_length
        step           = math.ceil(raw_step / ROW_SPACING) * ROW_SPACING
        n_between      = round(step / ROW_SPACING)
        total_rows     = math.floor(self.field_width / ROW_SPACING)

        tree_index, plant_row = 0, 2
        while plant_row < total_rows:
            centre_y = plant_row * ROW_SPACING + ROW_HEIGHT / 2
            if centre_y > self.field_width:
                break
            self._tree_row_indices.add(plant_row)
            tree_index = self._place_tree_line(centre_y, tree_index, plant_row)
            plant_row += 2 * n_between

    def _place_tree_line(self, centre_y: float, tree_index: int, plant_row: int) -> int:
        x = (self.trees[tree_index % len(self.trees)].spread / 100) / 2

        while x < self.field_length:
            tree   = self.trees[tree_index % len(self.trees)]
            radius = (tree.spread / 100) / 2

            self._tree_geoms.append(Point(x, centre_y).buffer(radius, resolution=16))
            self._tree_props.append({
                "type":     "tree",
                "name":     tree.name,
                "spread_m": round(tree.spread / 100, 2),
                "height_m": round(tree.height / 100, 2),
                "center_x": round(x, 4),
                "center_y": round(centre_y, 4),
                "radius_m": round(radius, 4),
            })
            self._tree_placements.setdefault(plant_row, []).append((x, radius, tree))

            companions = [p for p in tree.companion_plants if not p.is_tree]
            if companions:
                for adj in (plant_row - 1, plant_row + 1):
                    if 0 <= adj < len(self._row_y_bottoms):
                        self._tree_zones.setdefault(adj, []).append(
                            (x - radius, x + radius, companions)
                        )

            tree_index += 1
            next_radius = (self.trees[tree_index % len(self.trees)].spread / 100) / 2
            x += 2 * (radius + next_radius)

        return tree_index
