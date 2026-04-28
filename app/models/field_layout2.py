from __future__ import annotations
import math
import os
import geopandas as gpd
from shapely.geometry import Point, Polygon, box
from app.models.pv_system import PVSystem, PANEL_WIDTH_M, PANEL_HEIGHT_M, ROW_SPACING
from app.models.plant import Plant

ROW_HEIGHT = 2.0   # plant row height in metres (north–south)
GAP_HEIGHT = 0.5   # tractor path gap height in metres

# Absolute path to <project_root>/pack_debug.pdf so the debug output lands in a
# predictable place regardless of the CWD that started Flask / gunicorn.
_PROJECT_ROOT     = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_DEBUG_PDF = os.path.join(_PROJECT_ROOT, "pack_debug.pdf")


def _rect_coords(x0: float, y0: float, x1: float, y1: float) -> list:
    """Return a closed GeoJSON polygon ring for a rectangle — no Shapely needed."""
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]


class FieldLayout:
    """
    Builds the field structural geometry and serialises it to a GeoJSON FeatureCollection.

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
    """

    def __init__(
        self,
        field_length: float,
        field_width: float,
        pv_system: PVSystem,
        trees: list[Plant] | None = None,
        **kwargs,
    ):
        self.field_length     = field_length
        self.field_width      = field_width
        self.pv_system        = pv_system
        self.trees            = trees or []
        self.sun_plants       = kwargs.get("sun_plants")    or []
        self.shadow_plants    = kwargs.get("shadow_plants") or []

        # Rectangular structural features (plant rows, gaps, PV panels, shadows):
        self._rect_coords: list[list] = []
        self._rect_props:  list[dict] = []
        # Tree circle features — Shapely buffer (few dozen at most).
        self._tree_geoms:  list       = []
        self._tree_props:  list[dict] = []
        # Plant instances aggregated by species → one MultiPoint per plant.
        # {plant_id: {"plant_name":…, "spread_m":…, "radius_m":…, "coords":[…]}}
        self._plant_points: dict[int, dict] = {}

        self._row_y_bottoms: list[float] = []
        self._tree_row_indices: set[int] = set()
        self._shadow_y_ranges: list[tuple[float, float]] = []
        self._row_metadata: list[dict] = []

    # ── public API ────────────────────────────────────────────────────────────

    def build(self) -> FieldLayout:
        self._build_plant_rows()
        self._build_pv_rows()
        self._mark_shadow_rows()
        if self.trees:
            self._build_tree_rows()
            self._mark_tree_rows()
        self.assign_packed_rows_to_field()
        self.plot()
        return self

    def to_geojson(self) -> dict:
        """
        Build GeoDataFrames internally, then return the same GeoJSON
        FeatureCollection the UI already expects — identical format
        to the original field_layout.py output.
        """
        gdfs = self.to_geodataframes()
        features = []

        # field — not sent to the UI (structural rows cover it)

        # rows — Polygon with {"type": "plant_row", "row_index": …}
        gdf = gdfs["rows"]
        for _, row in gdf.iterrows():
            coords = [list(c) for c in row.geometry.exterior.coords]
            features.append({
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [coords]},
                "properties": {
                    "type":      "plant_row",
                    "row_index": int(row["row_index"]),
                },
            })

        # gaps — stored in _rect_coords/props but not in a GeoDataFrame,
        # so emit them directly to keep the UI format intact.
        for coords, props in zip(self._rect_coords, self._rect_props):
            if props["type"] == "gap":
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Polygon", "coordinates": [coords]},
                    "properties": props,
                })

        # solar panels — Polygon with {"type": "pv_row", …}
        gdf = gdfs["solar_panels"]
        for _, row in gdf.iterrows():
            coords = [list(c) for c in row.geometry.exterior.coords]
            features.append({
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [coords]},
                "properties": {
                    "type":      "pv_row",
                    "row_index": int(row["row_index"]),
                    "kw":        row["kw"],
                },
            })

        # shadows — Polygon with {"type": "shadow", …}
        gdf = gdfs["shadows"]
        for _, row in gdf.iterrows():
            coords = [list(c) for c in row.geometry.exterior.coords]
            features.append({
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [coords]},
                "properties": {
                    "type":            "shadow",
                    "row_index":       int(row["row_index"]),
                    "shadow_length_m": row["shadow_length_m"],
                },
            })

        # trees — Polygon with {"type": "tree", …}
        gdf = gdfs["trees"]
        for _, row in gdf.iterrows():
            coords = [list(c) for c in row.geometry.exterior.coords]
            features.append({
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [coords]},
                "properties": {
                    "type":     "tree",
                    "name":     row["name"],
                    "spread_m": row["spread_m"],
                    "height_m": row["height_m"],
                    "center_x": row["center_x"],
                    "center_y": row["center_y"],
                    "radius_m": row["radius_m"],
                },
            })

        # plants — MultiPoint with {"type": "plant_instance", …}, one feature
        # per species. Format matches ui_render_plants.txt — the UI filters on
        # properties.type === "plant_instance" and geometry.type === "MultiPoint",
        # so this is the contract that gets the circles to actually render.
        for pid, data in self._plant_points.items():
            if not data["coords"]:
                continue
            features.append({
                "type": "Feature",
                "geometry": {
                    "type":        "MultiPoint",
                    "coordinates": data["coords"],
                },
                "properties": {
                    "type":       "plant_instance",
                    "plant_id":   int(pid),
                    "plant_name": data["plant_name"],
                    "spread_m":   data["spread_m"],
                    "radius_m":   data["radius_m"],
                },
            })

        return {"type": "FeatureCollection", "features": features}

    def to_geodataframes(self) -> dict[str, gpd.GeoDataFrame]:
        """
        Return a dict of GeoDataFrames, one per geometry kind:
            "field"        – single polygon covering the whole field
            "rows"         – plant row rectangles with row metadata
            "solar_panels" – individual PV panel rectangles
            "shadows"      – shadow area rectangles
            "trees"        – tree circle polygons
            "plants"       – one circle Polygon per packed plant instance
        """
        field_gdf = gpd.GeoDataFrame(
            [{"field_length": self.field_length, "field_width": self.field_width}],
            geometry=[box(0, 0, self.field_length, self.field_width)],
        )

        row_geoms, row_attrs = [], []
        panel_geoms, panel_attrs = [], []
        shadow_geoms, shadow_attrs = [], []

        for coords, props in zip(self._rect_coords, self._rect_props):
            poly = Polygon(coords)
            t = props["type"]
            if t == "plant_row":
                row_geoms.append(poly)
                meta = self._row_metadata[props["row_index"]]
                row_attrs.append({
                    "row_index":       meta["row_index"],
                    "is_tree_row":     meta["is_tree_row"],
                    "is_above_tree":   meta["is_above_tree_row"],
                    "is_below_tree":   meta["is_below_tree_row"],
                    "is_in_shadow":    meta["is_in_shadow"],
                })
            elif t == "pv_row":
                panel_geoms.append(poly)
                panel_attrs.append({
                    "row_index": props["row_index"],
                    "kw":        props["kw"],
                })
            elif t == "shadow":
                shadow_geoms.append(poly)
                shadow_attrs.append({
                    "row_index":       props["row_index"],
                    "shadow_length_m": props["shadow_length_m"],
                })

        rows_gdf   = gpd.GeoDataFrame(row_attrs,    geometry=row_geoms)    if row_geoms    else gpd.GeoDataFrame(columns=["row_index", "geometry"])
        panels_gdf = gpd.GeoDataFrame(panel_attrs,  geometry=panel_geoms)  if panel_geoms  else gpd.GeoDataFrame(columns=["row_index", "geometry"])
        shadows_gdf = gpd.GeoDataFrame(shadow_attrs, geometry=shadow_geoms) if shadow_geoms else gpd.GeoDataFrame(columns=["row_index", "geometry"])

        tree_attrs = []
        for props in self._tree_props:
            tree_attrs.append({
                "name":     props["name"],
                "spread_m": props["spread_m"],
                "height_m": props["height_m"],
                "center_x": props["center_x"],
                "center_y": props["center_y"],
                "radius_m": props["radius_m"],
            })
        trees_gdf = gpd.GeoDataFrame(tree_attrs, geometry=list(self._tree_geoms)) if self._tree_geoms else gpd.GeoDataFrame(columns=["name", "geometry"])

        plant_geoms, plant_attrs = [], []
        for pid, data in self._plant_points.items():
            name     = data["plant_name"]
            spread_m = data["spread_m"]
            radius_m = data["radius_m"]
            for cx, cy in data["coords"]:
                plant_geoms.append(Point(cx, cy).buffer(radius_m, resolution=16))
                plant_attrs.append({
                    "plant_id":   pid,
                    "plant_name": name,
                    "spread_m":   spread_m,
                    "radius_m":   radius_m,
                    "center_x":   cx,
                    "center_y":   cy,
                })
        plants_gdf = (
            gpd.GeoDataFrame(plant_attrs, geometry=plant_geoms)
            if plant_geoms
            else gpd.GeoDataFrame(
                columns=["plant_id", "plant_name", "spread_m", "radius_m", "center_x", "center_y", "geometry"],
                geometry="geometry",
            )
        )

        return {
            "field":        field_gdf,
            "rows":         rows_gdf,
            "solar_panels": panels_gdf,
            "shadows":      shadows_gdf,
            "trees":        trees_gdf,
            "plants":       plants_gdf,
        }

    # ── plant packing ─────────────────────────────────────────────────────────

    def assign_packed_rows_to_field(self) -> None:
        """
        Pack two template rows (one sun, one shadow) — main packing followed
        by `pack_free_spaces_in_row` for gap filling — then **replicate each
        template into every other plant row of the same kind** by translating
        the captured placements to that row's `y_bottom`. The whole field
        ends up filled with the same diversity pattern as the templates.
        """
        sun_template_idx    = next((m["row_index"] for m in self._row_metadata if not m["is_in_shadow"]), None)
        shadow_template_idx = next((m["row_index"] for m in self._row_metadata if     m["is_in_shadow"]), None)

        sun_template, shadow_template = None, None

        if sun_template_idx is not None:
            self.pack_plants_in_row(self.sun_plants, sun_template_idx)
            self.pack_free_spaces_in_row(
                self._row_plants_to_gdf(sun_template_idx),
                self._row_to_gdf(sun_template_idx),
                self.sun_plants,
            )
            sun_template = self._capture_row_template(sun_template_idx)

        if shadow_template_idx is not None:
            self.pack_plants_in_row(self.shadow_plants, shadow_template_idx)
            self.pack_free_spaces_in_row(
                self._row_plants_to_gdf(shadow_template_idx),
                self._row_to_gdf(shadow_template_idx),
                self.shadow_plants,
            )
            shadow_template = self._capture_row_template(shadow_template_idx)

        for meta in self._row_metadata:
            ri = meta["row_index"]
            if ri == sun_template_idx or ri == shadow_template_idx:
                continue   # template row — already packed
            if meta["is_in_shadow"]:
                if shadow_template:
                    self._apply_template(shadow_template, meta["y_bottom"])
            else:
                if sun_template:
                    self._apply_template(sun_template, meta["y_bottom"])

    def _capture_row_template(self, row_index: int) -> list[tuple]:
        """
        Snapshot the placements inside `row_index` as relative-coord tuples
        `(plant_id, plant_name, spread_m, radius_m, abs_x, rel_y)` so they can
        be replayed at any other row's `y_bottom`. Reads from `_plant_points`.
        """
        y_bottom = self._row_metadata[row_index]["y_bottom"]
        y_top    = y_bottom + ROW_HEIGHT
        template: list[tuple] = []
        for pid, data in self._plant_points.items():
            for cx, cy in data["coords"]:
                if y_bottom <= cy <= y_top:
                    template.append((
                        pid,
                        data["plant_name"],
                        data["spread_m"],
                        data["radius_m"],
                        cx,
                        cy - y_bottom,
                    ))
        return template

    def _apply_template(self, template: list[tuple], y_bottom: float) -> None:
        """Replay a captured template at the given row's `y_bottom`."""
        for pid, name, spread_m, radius_m, abs_x, rel_y in template:
            if pid not in self._plant_points:
                self._plant_points[pid] = {
                    "plant_name": name,
                    "spread_m":   spread_m,
                    "radius_m":   radius_m,
                    "coords":     [],
                }
            self._plant_points[pid]["coords"].append([
                round(abs_x, 4),
                round(y_bottom + rel_y, 4),
            ])

    def _row_plants_to_gdf(self, row_index: int) -> gpd.GeoDataFrame:
        """
        Build a GeoDataFrame of plant circles whose centres fall inside the
        plant row at `row_index`. Each row of the GDF is one circle (Polygon
        from `Point.buffer(radius)`) with `plant_id`, `plant_name`, `radius_m`.
        """
        y_bottom = self._row_metadata[row_index]["y_bottom"]
        y_top    = y_bottom + ROW_HEIGHT
        geoms, attrs = [], []
        for pid, data in self._plant_points.items():
            r = data["radius_m"]
            for cx, cy in data["coords"]:
                if y_bottom <= cy <= y_top:
                    geoms.append(Point(cx, cy).buffer(r, resolution=16))
                    attrs.append({
                        "plant_id":   pid,
                        "plant_name": data["plant_name"],
                        "radius_m":   r,
                    })
        if not geoms:
            return gpd.GeoDataFrame(
                columns=["plant_id", "plant_name", "radius_m", "geometry"],
                geometry="geometry",
            )
        return gpd.GeoDataFrame(attrs, geometry=geoms)

    def _row_to_gdf(self, row_index: int) -> gpd.GeoDataFrame:
        """Build a single-row GeoDataFrame holding the rectangle of `row_index`."""
        y_bottom = self._row_metadata[row_index]["y_bottom"]
        return gpd.GeoDataFrame(
            [{"row_index": row_index, "y_bottom": y_bottom}],
            geometry=[box(0, y_bottom, self.field_length, y_bottom + ROW_HEIGHT)],
        )

    def pack_free_spaces_in_row(
        self,
        plants_gdf: gpd.GeoDataFrame,
        row_gdf: gpd.GeoDataFrame,
        fillers: list[Plant],
    ) -> None:
        """
        Fill the empty spaces left by `pack_plants_in_row`. The gap geometry
        is computed via geopandas — the union of the planted plants is
        subtracted from the union of the row — and `fillers` are then packed
        into the gap on a coarse grid (smallest species first), with each
        placed circle subtracted from the remaining gap so we never overlap.

        Pure side-effect: each placement is appended to `self._plant_points`.
        """
        if not fillers or row_gdf.empty:
            return

        row_geom = row_gdf.geometry.unary_union
        if not plants_gdf.empty:
            planted_union = plants_gdf.geometry.unary_union
            gap_geom      = row_geom.difference(planted_union)
        else:
            gap_geom = row_geom

        if gap_geom.is_empty:
            return

        sizes    = [p.spread / 100 for p in fillers]
        n        = len(fillers)
        min_size = min(sizes)
        if min_size <= 0:
            return
        step = min_size

        minx, miny, maxx, maxy = gap_geom.bounds
        idx = 0  # cycling index — advanced after every placement for diversity
        y = miny + min_size / 2
        while y <= maxy - min_size / 2 + 1e-9:
            x = minx + min_size / 2
            while x <= maxx - min_size / 2 + 1e-9:
                placed = False
                # Try the next species in the cycle first; only fall through to
                # later species when the current one doesn't fit (too big for
                # the remaining gap, or running off the row's bbox).
                for offset in range(n):
                    i    = (idx + offset) % n
                    size = sizes[i]
                    r    = size / 2
                    if x - r < minx or x + r > maxx or y - r < miny or y + r > maxy:
                        continue
                    circle = Point(x, y).buffer(r, resolution=12)
                    if gap_geom.covers(circle):
                        plant = fillers[i]
                        pid   = plant.id
                        if pid not in self._plant_points:
                            self._plant_points[pid] = {
                                "plant_name": plant.name,
                                "spread_m":   round(size, 2),
                                "radius_m":   round(r, 4),
                                "coords":     [],
                            }
                        self._plant_points[pid]["coords"].append([round(x, 4), round(y, 4)])
                        gap_geom = gap_geom.difference(circle)
                        if gap_geom.is_empty:
                            return
                        idx     = (i + 1) % n   # advance cycle past placed species
                        x      += size
                        placed  = True
                        break
                if not placed:
                    x += step
            y += step

    def plot(self, out_path: str = DEFAULT_DEBUG_PDF) -> str:
        """
        Render a quick PDF showing plant-row strips, gaps, and any plants packed
        into them via `pack_plants_in_row`. Independent of the pdf.py pipeline —
        meant for visual inspection of the packing during development.
        """
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import Rectangle, Circle, Patch

        palette = [
            "#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231",
            "#911eb4", "#42d4f4", "#f032e6", "#bfef45", "#fabed4",
            "#469990", "#dcbeff", "#9a6324", "#fffac8", "#800000",
            "#aaffc3", "#808000", "#ffd8b1", "#000075", "#a9a9a9",
        ]

        aspect = self.field_length / max(self.field_width, 0.001)
        fig_h  = 8.0
        fig_w  = min(fig_h * aspect, 18.0) + 3.0
        fig, ax = plt.subplots(figsize=(fig_w, fig_h))
        ax.set_xlim(0, self.field_length)
        ax.set_ylim(0, self.field_width)
        ax.set_aspect("equal", adjustable="box")
        ax.set_xlabel("East → (m)")
        ax.set_ylabel("North → (m)")
        ax.set_title("Packed rows — debug view")

        for coords, props in zip(self._rect_coords, self._rect_props):
            t = props.get("type")
            if t == "plant_row":
                fc, ec = "#eaf4e0", "#c8ddb0"
            elif t == "gap":
                fc, ec = "#d6d6d6", "#bbbbbb"
            else:
                continue
            x0, y0 = coords[0]
            x1, y1 = coords[2]
            ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0,
                                   facecolor=fc, edgecolor=ec, linewidth=0.4, zorder=1))

        species   = sorted(self._plant_points.keys())
        color_map = {pid: palette[i % len(palette)] for i, pid in enumerate(species)}
        for pid, data in self._plant_points.items():
            r = data["radius_m"]
            for cx, cy in data["coords"]:
                ax.add_patch(Circle((cx, cy), r,
                                    facecolor=color_map[pid], edgecolor="none",
                                    alpha=0.85, zorder=2))

        if species:
            handles = [
                Patch(facecolor=color_map[pid], edgecolor="none",
                      label=self._plant_points[pid]["plant_name"])
                for pid in species
            ]
            ax.legend(handles=handles, loc="upper right", fontsize=8, frameon=True)

        fig.tight_layout()
        fig.savefig(out_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return out_path

    def pack_plants_in_row(self, plants: list[Plant], row_index: int) -> None:
        """
        Pack `plants` into the plant row identified by `row_index`.

        Plants are drawn as circles whose diameter equals `plant.spread / 100` (m).
        They are cycled left-to-right, stacking columns top-to-bottom within the
        ROW_HEIGHT band until the row is full or no remaining plant fits.
        Each placement is appended to `self._plant_points` (one MultiPoint per
        species, keyed by `plant.id`).
        """
        if not plants or not (0 <= row_index < len(self._row_metadata)):
            return

        y_bottom = self._row_metadata[row_index]["y_bottom"]
        sizes    = [p.spread / 100 for p in plants]
        n        = len(plants)

        idx, x = 0, 0.0
        while x < self.field_length:
            col_y, col_width = 0.0, 0.0
            # Stack a column. For each placement, scan the species cycle for the
            # first one that fits both vertically (col_y + size ≤ ROW_HEIGHT) and
            # horizontally (x + size ≤ field_length). Skipping oversized species
            # is what lets the row keep packing past plants like Watermelon (3 m)
            # whose spread exceeds ROW_HEIGHT (2 m).
            while True:
                placed = False
                for offset in range(n):
                    i    = (idx + offset) % n
                    size = sizes[i]
                    if col_y + size <= ROW_HEIGHT and x + size <= self.field_length:
                        plant = plants[i]
                        r  = size / 2
                        cx = x + r
                        cy = y_bottom + col_y + r
                        pid = plant.id
                        if pid not in self._plant_points:
                            self._plant_points[pid] = {
                                "plant_name": plant.name,
                                "spread_m":   round(size, 2),
                                "radius_m":   round(r, 4),
                                "coords":     [],
                            }
                        self._plant_points[pid]["coords"].append([round(cx, 4), round(cy, 4)])
                        col_y     += size
                        col_width  = max(col_width, size)
                        idx        = (i + 1) % n
                        placed     = True
                        break
                if not placed:
                    break
            if col_width == 0:
                break  # no species fits at all at this x — close the row
            x += col_width

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

            tree_index += 1
            next_radius = (self.trees[tree_index % len(self.trees)].spread / 100) / 2
            x += 2 * (radius + next_radius)

        return tree_index
