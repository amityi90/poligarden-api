from __future__ import annotations
import math
from shapely.geometry import box, Point
from app.models.pv_system import PVSystem, PANEL_WIDTH_M, PANEL_HEIGHT_M, ROW_SPACING
from app.models.plant import Plant
import random

ROW_HEIGHT = 2.0   # plant row height in metres (north–south)
GAP_HEIGHT = 0.5   # tractor path gap height in metres


def _rect(x0: float, y0: float, x1: float, y1: float):
    return box(x0, y0, x1, y1)


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
        "plant_instance" – circle polygon for each packed plant instance
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
        self.field_length      = field_length
        self.field_width       = field_width
        self.pv_system         = pv_system
        self.trees             = trees or []
        self.shadow_groups     = shadow_groups or []
        self.sun_groups        = sun_groups or []
        self.non_tree_plants   = non_tree_plants or []
        self.shadow_ungrouped  = shadow_ungrouped or []
        self.sun_ungrouped     = sun_ungrouped or []
        self.neutral_plants    = neutral_plants or []
        self._geometries: list = []
        self._properties: list[dict] = []
        self._row_y_bottoms: list[float] = []
        # tree_zones[row_index] = [(x_start, x_end, [companion_plants])]
        self._tree_zones: dict[int, list] = {}
        self._tree_row_indices: set[int] = set()
        self._shadow_y_ranges: list[tuple[float, float]] = []  # (y_start, y_end) of each shadow zone
        self._row_metadata: list[dict] = []
        # {plant_row_index: [(x_center, radius, Tree), ...]}
        self._tree_placements: dict[int, list] = {}

    def build(self) -> FieldLayout:
        self._build_plant_rows()
        self._build_pv_rows()
        self._mark_shadow_rows()
        if self.trees:
            self._build_tree_rows()
            self._mark_tree_rows()
        self._pack_plant_rows()
        return self

    # ── plant rows packing ────────────────────────────────────────────────────

    def _pack_plant_rows(self):
        """
        Pack plant instances into every plant row.

        Available data:
          - self.trees             : list of tree Plants
          - self.shadow_groups     : CompanionGroups built from shadow plants
          - self.sun_groups        : CompanionGroups built from sun plants
          - self.shadow_ungrouped  : shadow plants not in any companion group
          - self.sun_ungrouped     : sun plants not in any companion group
          - self._row_y_bottoms    : y_bottom of each plant row
          - self._tree_row_indices : set of row indices that are tree rows
          - self._tree_zones       : {row_index: [(x_start, x_end, companions)]}
          - self.field_length      : E-W width of each row (metres)
        """

        geometries = []
        metadata = []
        
        def add_plant(x, y, plant):
            radius = (plant.spread / 100) / 2
            self._geometries.append(Point(x + radius, y + radius).buffer(radius, resolution=64))
            self._properties.append({
                "type":      "tree",
                "name":      plant.name,
                "spread_m":  round(plant.spread / 100, 2),
                "height_m":  round(plant.height / 100, 2),
                "center_x":  round(x, 4),
                "center_y":  round(y, 4),
                "radius_m":  round(radius, 4),
                })
            # meta data need to be checed as all metadata


        def fill_rect_gap(start_x, start_y, gap_w, gap_h, fillers: list, y_bottom: float = 0.0):
            """
            Fill a rectangular gap (start_x, start_y, gap_w × gap_h) with the
            largest fitting filler plant at each position — row by row, left to right.
            Fillers are sorted smallest-first so we can scan reversed for best fit.
            Mirrors pack_plants_balanced.fill_rect_gap logic.
            """
            if gap_w <= 0 or gap_h <= 0 or not fillers:
                return
            fillers_sorted = sorted(fillers, key=lambda p: p.spread)
            smallest = fillers_sorted[0].spread / 100

            curr_y = start_y
            while curr_y + smallest <= start_y + gap_h:
                curr_x   = start_x
                row_max_h = 0.0
                while curr_x + smallest <= start_x + gap_w:
                    best = None
                    for f in reversed(fillers_sorted):
                        f_s = f.spread / 100
                        if curr_x + f_s <= start_x + gap_w and curr_y + f_s <= start_y + gap_h:
                            best = f
                            break
                    if best is None:
                        break
                    f_size = best.spread / 100
                    add_plant(curr_x, y_bottom + curr_y, best)
                    curr_x   += f_size
                    row_max_h = max(row_max_h, f_size)
                if row_max_h == 0:
                    break
                curr_y += row_max_h

        def close_column(group, current_x, current_y, row_length, size, column_plants, row_plants, y_bottom):
            """Fill gaps in the finished column then reset column state."""
            col_w = row_length if row_length > 0 else size
            fillers = sorted(group.plants + group.non_antagonistic_plants, key=lambda p: p.spread)
            # gap above last plant
            fill_rect_gap(current_x, current_y, col_w, ROW_HEIGHT - current_y, fillers, y_bottom)
            # gaps beside narrower plants in this column
            for rx, ry, rs in column_plants:
                gap_w = col_w - rs
                if gap_w > 1e-6:
                    fill_rect_gap(rx + rs, ry, gap_w, rs, fillers, y_bottom)
            row_plants.extend(column_plants)
            return current_x + col_w   # new current_x

        def pack_single_row(row_index: int, y_bottom: float, groups: list, ungrouped: list):
            current_x  = 0.0
            current_y  = 0.0
            row_length = 0.0
            row_plants    = []   # all plants placed in this row (all columns)
            column_plants = []   # plants in the current column only

            randomized_groups = random.sample(groups, len(groups))

            row_is_over = False
            while not row_is_over:
                for group in randomized_groups:
                    if row_is_over:
                        break
                    use_external_plants = False
                    for plant in group.plants:
                        if row_is_over:
                            break
                        size = plant.spread / 100
                        if current_y + size > ROW_HEIGHT:
                            current_x = close_column(group, current_x, current_y, row_length, size, column_plants, row_plants, y_bottom)
                            current_y = 0.0
                            row_length = 0.0
                            column_plants = []
                            if current_x >= self.field_length:
                                row_is_over = True
                                break
                        if current_x + size > self.field_length:
                            row_is_over = True
                            break

                        add_plant(current_x, y_bottom + current_y, plant)
                        column_plants.append((current_x, current_y, size))
                        current_y += size
                        if size > row_length:
                            row_length = size

                    for plant in group.non_antagonistic_plants:
                        if row_is_over:
                            break
                        size = plant.spread / 100
                        if current_y + size > ROW_HEIGHT:
                            current_x = close_column(group, current_x, current_y, row_length, size, column_plants, row_plants, y_bottom)
                            current_y = 0.0
                            row_length = 0.0
                            column_plants = []
                            if current_x >= self.field_length:
                                row_is_over = True
                            break
                        if current_x + size > self.field_length:
                            row_is_over = True
                            break

                        add_plant(current_x, y_bottom + current_y, plant)
                        column_plants.append((current_x, current_y, size))
                        current_y += size
                        if size > row_length:
                            row_length = size

                for i in range(3):
                    for plant in ungrouped:
                        if row_is_over:
                            break
                        size = plant.spread / 100
                        if current_y + size > ROW_HEIGHT:
                            fillers = sorted(ungrouped, key=lambda p: p.spread)
                            fill_rect_gap(current_x, current_y, row_length if row_length > 0 else size, ROW_HEIGHT - current_y, fillers, y_bottom)
                            row_plants.extend(column_plants)
                            current_x += row_length if row_length > 0 else size
                            current_y = 0.0
                            row_length = 0.0
                            column_plants = []
                            if current_x >= self.field_length:
                                row_is_over = True
                            break
                        if current_x + size > self.field_length:
                            row_is_over = True
                            break

                        add_plant(current_x, y_bottom + current_y, plant)
                        column_plants.append((current_x, current_y, size))
                        current_y += size
                        if size > row_length:
                            row_length = size

            # flush last column into row_plants
            row_plants.extend(column_plants)

            # ── gap filling with neutral plants ──────────────────────────────
            if not self.neutral_plants or not row_plants:
                return

            # 1. Find x-gaps (columns not covered by any plant)
            #    Build covered intervals [x, x+size], merge, find uncovered ranges
            intervals = sorted({(rx, rx + rs) for rx, _, rs in row_plants})
            merged = []
            for start, end in intervals:
                if merged and start <= merged[-1][1]:
                    merged[-1] = (merged[-1][0], max(merged[-1][1], end))
                else:
                    merged.append([start, end])

            # gaps before first, between intervals, after last
            x_gaps: list[tuple[float, float]] = []
            prev = 0.0
            for start, end in merged:
                if start - prev > 1e-6:
                    x_gaps.append((prev, start))
                prev = end
            if self.field_length - prev > 1e-6:
                x_gaps.append((prev, self.field_length))

            for gx0, gx1 in x_gaps:
                fill_rect_gap(gx0, 0.0, gx1 - gx0, ROW_HEIGHT, self.neutral_plants, y_bottom)

            # 2. Find y-gaps within each covered x-column
            #    For each unique x in row_plants, find the max y+size → gap above
            col_max_y: dict[float, float] = {}
            col_width_map: dict[float, float] = {}
            for rx, ry, rs in row_plants:
                top = ry + rs
                if rx not in col_max_y or top > col_max_y[rx]:
                    col_max_y[rx] = top
                if rx not in col_width_map or rs > col_width_map[rx]:
                    col_width_map[rx] = rs

            for rx, max_top in col_max_y.items():
                gap_h = ROW_HEIGHT - max_top
                if gap_h > 1e-6:
                    fill_rect_gap(rx, max_top, col_width_map[rx], gap_h, self.neutral_plants, y_bottom)

            # 3. Find gaps beside narrower plants within a column
            #    Each plant at (rx, ry, rs) may be narrower than the column width.
            #    Fill the strip to its right: [rx+rs .. rx+col_width] × [ry .. ry+rs]
            for rx, ry, rs in row_plants:
                col_w = col_width_map.get(rx, rs)
                gap_w = col_w - rs
                if gap_w > 1e-6:
                    fill_rect_gap(rx + rs, ry, gap_w, rs, self.neutral_plants, y_bottom)

        tree_rows = sorted(self._tree_row_indices)
        print(f"[pack_plant_rows] tree row indices: {tree_rows}")

        for row_index, row_y_bottom in enumerate(self._row_y_bottoms):
            meta = self._row_metadata[row_index]

            if meta["is_tree_row"]:
                self._pack_tree_row(row_index, row_y_bottom)
            elif meta["is_above_tree_row"]:
                self._pack_adjacent_tree_row(row_index, row_y_bottom)
            elif meta["is_below_tree_row"]:
                self._pack_adjacent_tree_row(row_index, row_y_bottom)
            elif meta["is_in_shadow"]:
                pack_single_row(row_index, row_y_bottom,
                                self.shadow_groups, self.shadow_ungrouped)
            else:
                pack_single_row(row_index, row_y_bottom,
                                self.sun_groups, self.sun_ungrouped)

        all_groups = self.shadow_groups + self.sun_groups
        print(f"\n[pack_plant_rows] companion groups — shadow={len(self.shadow_groups)} sun={len(self.sun_groups)}:")
        for i, group in enumerate(all_groups):
            label = "shadow" if i < len(self.shadow_groups) else "sun"
            plant_names   = [p.name for p in group.plants]
            non_ant_names = [p.name for p in group.non_antagonistic_plants]
            print(f"  [{label}] group {i}: plants={plant_names}")
            print(f"           non_antagonistic={non_ant_names}")

    # ── adjacent-tree row packing ────────────────────────────────────────────

    def _pack_adjacent_tree_row(self, row_index: int, row_y_bottom: float) -> None:
        """
        Pack a row that is directly above or below a tree row.

        The row is split into sections — one per tree in the adjacent tree row.
        Section boundaries are the midpoints of the gaps between neighbouring trees;
        the first section starts at x=0 and the last ends at field_length.

        Each section is then packed with that tree's companion_groups using the
        same column + gap-filling strategy as the rest of the layout.
        """
        meta = self._row_metadata[row_index]
        tree_row_index = (row_index + 1) if meta["is_above_tree_row"] else (row_index - 1)

        placements = sorted(
            self._tree_placements.get(tree_row_index, []), key=lambda t: t[0]
        )
        if not placements:
            return

        # Build sections: each tree owns from the left-midpoint to the right-midpoint
        n = len(placements)
        sections: list[tuple[float, float, object]] = []
        for i, (x, r, tree) in enumerate(placements):
            left = (
                0.0 if i == 0
                else (placements[i - 1][0] + placements[i - 1][1] + x - r) / 2
            )
            right = (
                self.field_length if i == n - 1
                else (x + r + placements[i + 1][0] - placements[i + 1][1]) / 2
            )
            sections.append((left, right, tree))

        for sec_start, sec_end, tree in sections:
            if not tree.companion_groups or sec_end - sec_start <= 0:
                continue
            self._pack_section(sec_start, sec_end, row_y_bottom, row_index,
                               tree.companion_groups)

    def _pack_section(
        self,
        x_start: float,
        x_end: float,
        y_bottom: float,
        row_index: int,
        groups: list,
    ) -> None:
        """
        Pack plants into the horizontal strip [x_start, x_end] × [0, ROW_HEIGHT]
        using the column method:

          1. Cycle through every group's plants to fill columns.
          2. When a column is full (height), close it: fill the gap above the last
             plant and the side-gaps beside narrower plants using the group's
             non_antagonistic_plants as fillers.
          3. After all columns, fill any remaining x-gaps in the section.
        """
        # Flatten all group plants for cycling; skip plants too tall for a row
        flat_plants = [
            p for g in groups for p in g.plants
            if p.spread / 100 <= ROW_HEIGHT
        ]
        if not flat_plants:
            return

        # Filler pool: non_antagonistic_plants from all groups (for gap filling)
        filler_pool = sorted(
            {
                p.id: p
                for g in groups
                for p in g.non_antagonistic_plants
                if p.spread / 100 <= ROW_HEIGHT
            }.values(),
            key=lambda p: p.spread,
        )
        # Fall back to flat_plants if no dedicated fillers
        gap_fillers = filler_pool if filler_pool else sorted(flat_plants, key=lambda p: p.spread)

        # ── inner helpers ────────────────────────────────────────────────────

        def _place(x: float, y_local: float, plant) -> None:
            size   = plant.spread / 100
            radius = size / 2
            self._geometries.append(
                Point(x + radius, y_bottom + y_local + radius)
                .buffer(radius, resolution=64)
            )
            self._properties.append({
                "type":       "plant_instance",
                "plant_id":   plant.id,
                "plant_name": plant.name,
                "spread_m":   round(size, 2),
                "row_index":  row_index,
            })

        def _fill_rect(x0: float, y0: float, w: float, h: float) -> None:
            if w <= 0 or h <= 0 or not gap_fillers:
                return
            sm = gap_fillers[0].spread / 100
            cy = y0
            while cy + sm <= y0 + h:
                cx    = x0
                max_h = 0.0
                while cx + sm <= x0 + w:
                    best = next(
                        (f for f in reversed(gap_fillers)
                         if cx + f.spread / 100 <= x0 + w
                         and cy + f.spread / 100 <= y0 + h),
                        None,
                    )
                    if best is None:
                        break
                    s = best.spread / 100
                    _place(cx, cy, best)
                    cx    += s
                    max_h  = max(max_h, s)
                if max_h == 0:
                    break
                cy += max_h

        def _close_col(col_x: float, col_y: float, col_w: float,
                       col_plants: list, all_plants: list) -> float:
            # gap above the last plant in this column
            _fill_rect(col_x, col_y, col_w, ROW_HEIGHT - col_y)
            # gaps beside narrower plants within this column
            for px, py, ps in col_plants:
                side_w = col_w - ps
                if side_w > 1e-6:
                    _fill_rect(px + ps, py, side_w, ps)
            all_plants.extend(col_plants)
            return col_x + col_w

        # ── column packing ───────────────────────────────────────────────────
        all_placed: list = []
        filler_idx = 0
        curr_x     = x_start

        while curr_x < x_end:
            col_y     = 0.0
            col_width = 0.0
            col_plants: list = []

            while col_y < ROW_HEIGHT:
                plant = flat_plants[filler_idx % len(flat_plants)]
                size  = plant.spread / 100

                if col_y + size > ROW_HEIGHT:
                    break          # column height exhausted
                if curr_x + size > x_end:
                    break          # plant would cross section boundary

                _place(curr_x, col_y, plant)
                col_plants.append((curr_x, col_y, size))
                col_y     += size
                col_width  = max(col_width, size)
                filler_idx = (filler_idx + 1) % len(flat_plants)

            if col_width == 0:
                break   # section too narrow for any plant

            curr_x = _close_col(curr_x, col_y, col_width, col_plants, all_placed)

        # ── fill remaining x-gaps across the section ─────────────────────────
        if all_placed:
            intervals = sorted({(px, px + ps) for px, _, ps in all_placed})
            merged: list = []
            for s, e in intervals:
                if merged and s <= merged[-1][1]:
                    merged[-1] = (merged[-1][0], max(merged[-1][1], e))
                else:
                    merged.append([s, e])
            prev = x_start
            for s, e in merged:
                if s - prev > 1e-6:
                    _fill_rect(prev, 0.0, s - prev, ROW_HEIGHT)
                prev = e
            if x_end - prev > 1e-6:
                _fill_rect(prev, 0.0, x_end - prev, ROW_HEIGHT)
        else:
            _fill_rect(x_start, 0.0, x_end - x_start, ROW_HEIGHT)

    # ── plant row backgrounds ─────────────────────────────────────────────────

    def _build_plant_rows(self):
        y         = 0.0
        row_index = 0

        while y + ROW_HEIGHT <= self.field_width:
            self._row_y_bottoms.append(y)
            self._geometries.append(_rect(0, y, self.field_length, y + ROW_HEIGHT))
            self._properties.append({
                "type":      "plant_row",
                "row_index": row_index,
            })
            self._row_metadata.append({
                "row_index":          row_index,
                "y_bottom":           round(y, 4),
                "is_tree_row":        False,
                "is_above_tree_row":  False,
                "is_below_tree_row":  False,
                "is_in_shadow":       False,
            })
            y         += ROW_HEIGHT
            row_index += 1

            if y + GAP_HEIGHT <= self.field_width:
                self._geometries.append(_rect(0, y, self.field_length, y + GAP_HEIGHT))
                self._properties.append({"type": "gap"})
                y += GAP_HEIGHT

    def _mark_shadow_rows(self):
        for meta in self._row_metadata:
            y0 = meta["y_bottom"]
            y1 = y0 + ROW_HEIGHT
            for s0, s1 in self._shadow_y_ranges:
                if y0 < s1 and y1 > s0:   # row overlaps shadow zone
                    meta["is_in_shadow"] = True
                    break

    def _mark_tree_rows(self):
        for meta in self._row_metadata:
            i = meta["row_index"]
            meta["is_tree_row"]       = i in self._tree_row_indices
            meta["is_above_tree_row"] = (i + 1) in self._tree_row_indices
            meta["is_below_tree_row"] = (i - 1) in self._tree_row_indices

    # ── PV rows ───────────────────────────────────────────────────────────────

    def _build_pv_rows(self):
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
                x1 = x0 + PANEL_WIDTH_M
                self._geometries.append(_rect(x0, y, x1, y + PANEL_HEIGHT_M))
                self._properties.append({
                    "type":      "pv_row",
                    "row_index": pv_row_index,
                    "kw":        row_kw,
                })

            panels_placed += row_panels
            pv_row_index  += 1

            shadow_start = y + PANEL_HEIGHT_M
            shadow_end   = shadow_start + pv.shadow_length
            if shadow_start < self.field_width:
                self._shadow_y_ranges.append((shadow_start, min(shadow_end, self.field_width)))
                self._geometries.append(
                    _rect(0, shadow_start, self.field_length, min(shadow_end, self.field_width))
                )
                self._properties.append({
                    "type":            "shadow",
                    "row_index":       pv_row_index - 1,
                    "shadow_length_m": round(pv.shadow_length, 2),
                })

            raw_step = PANEL_HEIGHT_M + 2 * pv.shadow_length
            step     = math.ceil(raw_step / ROW_SPACING) * ROW_SPACING
            y       += step

    # ── tree rows ─────────────────────────────────────────────────────────────

    def _build_tree_rows(self):
        pv = self.pv_system

        raw_step         = PANEL_HEIGHT_M + 2 * pv.shadow_length
        step             = math.ceil(raw_step / ROW_SPACING) * ROW_SPACING
        n_rows_between   = round(step / ROW_SPACING)

        total_plant_rows = math.floor(self.field_width / ROW_SPACING)

        tree_index = 0
        plant_row  = 2
        while plant_row < total_plant_rows:
            centre_y = plant_row * ROW_SPACING + ROW_HEIGHT / 2
            if centre_y > self.field_width:
                break
            self._tree_row_indices.add(plant_row)
            tree_index = self._place_tree_line(centre_y, tree_index, plant_row)
            plant_row += 2 * n_rows_between

    def _place_tree_line(self, centre_y: float, tree_index: int, plant_row: int) -> int:
        tree   = self.trees[tree_index % len(self.trees)]
        radius = (tree.spread / 100) / 2
        x      = radius

        while x < self.field_length:
            tree   = self.trees[tree_index % len(self.trees)]
            radius = (tree.spread / 100) / 2

            self._geometries.append(Point(x, centre_y).buffer(radius, resolution=64))
            self._properties.append({
                "type":      "tree",
                "name":      tree.name,
                "spread_m":  round(tree.spread / 100, 2),
                "height_m":  round(tree.height / 100, 2),
                "center_x":  round(x, 4),
                "center_y":  round(centre_y, 4),
                "radius_m":  round(radius, 4),
            })

            # Record tree placement for gap packing
            self._tree_placements.setdefault(plant_row, []).append((x, radius, tree))

            # Record companion zones for the plant rows directly above and below
            companions = [p for p in tree.companion_plants if not p.is_tree]
            if companions:
                x_start = x - radius
                x_end   = x + radius
                for adj in (plant_row - 1, plant_row + 1):
                    if 0 <= adj < len(self._row_y_bottoms):
                        self._tree_zones.setdefault(adj, []).append(
                            (x_start, x_end, companions)
                        )

            tree_index += 1
            next_tree   = self.trees[tree_index % len(self.trees)]
            next_radius = (next_tree.spread / 100) / 2
            x          += 2 * (radius + next_radius)

        return tree_index

    # ── 2D plant packing — TODO ───────────────────────────────────────────────

    def _pack_tree_row(self, row_index: int, row_y_bottom: float):
        """
        Pack plants in the gaps between trees in a tree row.

        Steps:
          1. Get the list of placed trees for this row (sorted by x).
          2. Find empty x-segments: gaps between tree spread areas.
          3. For each gap, determine the left and right trees.
          4. Build companion_trees_gap_plants:
             - Plants companion to either tree, not antagonistic to both trees
               and not antagonistic to each other.
             - If list < 6, pad with non_antagonistic_plants from both trees.
          5. Pack that plant list into the gap rectangle (full ROW_HEIGHT),
             using fill_rect_gap logic.
        """
        if not self.trees:
            return

        placements = sorted(self._tree_placements.get(row_index, []), key=lambda t: t[0])
        if not placements:
            return

        # Gaps: before first tree, between trees, after last tree
        gaps: list[tuple[float, float, object, object]] = []
        # (gap_x_start, gap_x_end, left_tree_or_None, right_tree_or_None)

        # gap before first tree
        first_x, first_r, first_tree = placements[0]
        if first_x - first_r > 1e-6:
            gaps.append((0.0, first_x - first_r, None, first_tree))

        # gaps between consecutive trees
        for i in range(len(placements) - 1):
            lx, lr, ltree = placements[i]
            rx, rr, rtree = placements[i + 1]
            gap_start = lx + lr
            gap_end   = rx - rr
            if gap_end - gap_start > 1e-6:
                gaps.append((gap_start, gap_end, ltree, rtree))

        # gap after last tree
        last_x, last_r, last_tree = placements[-1]
        if self.field_length - (last_x + last_r) > 1e-6:
            gaps.append((last_x + last_r, self.field_length, last_tree, None))

        ant_ids = lambda plant: {a.id for a in plant.antagonistic_plants}

        for gap_start, gap_end, left_tree, right_tree in gaps:
            gap_w = gap_end - gap_start
            if gap_w <= 0:
                continue

            # Collect antagonist ids from both flanking trees
            tree_ant_ids: set[int] = set()
            if left_tree:
                tree_ant_ids |= ant_ids(left_tree)
            if right_tree:
                tree_ant_ids |= ant_ids(right_tree)

            # Companion plants of either tree, not antagonistic to both trees
            companion_candidates: list = []
            seen_ids: set[int] = set()
            for tree in [left_tree, right_tree]:
                if tree is None:
                    continue
                for p in tree.companion_non_tree_plants:
                    if p.id in seen_ids or p.id in tree_ant_ids:
                        continue
                    existing_ids = {c.id for c in companion_candidates}
                    # p antagonizes something already added
                    if ant_ids(p) & existing_ids:
                        continue
                    # something already added antagonizes p
                    if p.id in {a.id for c in companion_candidates for a in c.antagonistic_plants}:
                        continue
                    companion_candidates.append(p)
                    seen_ids.add(p.id)

            # Pad with non_antagonistic_plants if fewer than 6
            if len(companion_candidates) < 6:
                for tree in [left_tree, right_tree]:
                    if tree is None:
                        continue
                    for p in tree.non_antagonistic_plants:
                        if len(companion_candidates) >= 6:
                            break
                        if p.id in seen_ids or p.id in tree_ant_ids:
                            continue
                        existing_ids = {c.id for c in companion_candidates}
                        if ant_ids(p) & existing_ids:
                            continue
                        if p.id in {a.id for c in companion_candidates for a in c.antagonistic_plants}:
                            continue
                        companion_candidates.append(p)
                        seen_ids.add(p.id)

            if not companion_candidates:
                continue

            # Only keep plants that can actually fit in a row
            fillers = sorted(
                [p for p in companion_candidates if p.spread / 100 <= ROW_HEIGHT],
                key=lambda p: p.spread,
            )
            if not fillers:
                continue

            # ── inner helpers scoped to this gap ─────────────────────────────

            def _place(x: float, y_local: float, plant) -> None:
                size   = plant.spread / 100
                radius = size / 2
                self._geometries.append(
                    Point(x + radius, row_y_bottom + y_local + radius)
                    .buffer(radius, resolution=64)
                )
                self._properties.append({
                    "type":       "plant_instance",
                    "plant_id":   plant.id,
                    "plant_name": plant.name,
                    "spread_m":   round(size, 2),
                    "row_index":  row_index,
                })

            def _fill_rect(x0: float, y0: float, w: float, h: float) -> None:
                """Fill a rectangle with fillers (largest-fit, row-by-row)."""
                if w <= 0 or h <= 0:
                    return
                sm = fillers[0].spread / 100
                cy = y0
                while cy + sm <= y0 + h:
                    cx      = x0
                    max_h   = 0.0
                    while cx + sm <= x0 + w:
                        best = next(
                            (f for f in reversed(fillers)
                             if cx + f.spread/100 <= x0 + w
                             and cy + f.spread/100 <= y0 + h),
                            None,
                        )
                        if best is None:
                            break
                        s = best.spread / 100
                        _place(cx, cy, best)
                        cx    += s
                        max_h  = max(max_h, s)
                    if max_h == 0:
                        break
                    cy += max_h

            def _close_col(col_x: float, col_y: float, col_w: float,
                           col_plants: list, all_plants: list) -> float:
                """
                Fill gaps inside the finished column, record its plants, and
                return the x-position of the next column.
                """
                # gap above the last plant
                _fill_rect(col_x, col_y, col_w, ROW_HEIGHT - col_y)
                # gaps beside narrower plants within this column
                for px, py, ps in col_plants:
                    side_w = col_w - ps
                    if side_w > 1e-6:
                        _fill_rect(px + ps, py, side_w, ps)
                all_plants.extend(col_plants)
                return col_x + col_w

            # ── column-based packing across the gap ──────────────────────────
            all_plants: list = []   # (x, y_local, size) for every placed plant
            filler_idx = 0
            curr_x     = gap_start

            while curr_x < gap_end:
                col_y     = 0.0
                col_width = 0.0
                col_plants: list = []

                # Fill one column top-to-bottom, cycling through fillers
                while col_y < ROW_HEIGHT:
                    plant = fillers[filler_idx % len(fillers)]
                    size  = plant.spread / 100

                    if col_y + size > ROW_HEIGHT:
                        break   # column height exhausted
                    if curr_x + size > gap_end:
                        break   # plant would cross into the tree

                    _place(curr_x, col_y, plant)
                    col_plants.append((curr_x, col_y, size))
                    col_y      += size
                    col_width   = max(col_width, size)
                    filler_idx  = (filler_idx + 1) % len(fillers)

                if col_width == 0:
                    break   # no plant could fit — gap too narrow

                curr_x = _close_col(curr_x, col_y, col_width, col_plants, all_plants)

            # ── fill remaining x-gaps across the whole tree gap ───────────────
            if all_plants:
                intervals = sorted({(px, px + ps) for px, _, ps in all_plants})
                merged: list = []
                for s, e in intervals:
                    if merged and s <= merged[-1][1]:
                        merged[-1] = (merged[-1][0], max(merged[-1][1], e))
                    else:
                        merged.append([s, e])
                prev = gap_start
                for s, e in merged:
                    if s - prev > 1e-6:
                        _fill_rect(prev, 0.0, s - prev, ROW_HEIGHT)
                    prev = e
                if gap_end - prev > 1e-6:
                    _fill_rect(prev, 0.0, gap_end - prev, ROW_HEIGHT)
            else:
                _fill_rect(gap_start, 0.0, gap_w, ROW_HEIGHT)

    # ── serialisation ─────────────────────────────────────────────────────────

    def to_geojson(self) -> dict:
        features = []
        for geom, props in zip(self._geometries, self._properties):
            coords = [list(coord) for coord in geom.exterior.coords]
            features.append({
                "type": "Feature",
                "geometry": {
                    "type":        "Polygon",
                    "coordinates": [coords],
                },
                "properties": props,
            })
        return {"type": "FeatureCollection", "features": features}
