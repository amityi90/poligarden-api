from __future__ import annotations
import math

PANEL_WIDTH_M  = 1.13   # east–west
PANEL_HEIGHT_M = 1.76   # north–south (physical panel dimension on the ground)
PANEL_WATT     = 450
ROW_SPACING    = 2.5    # plant rows are 2.5 m wide (2 m bed + 0.5 m path)


class PVSystem:
    """
    Holds all PV configuration and pre-computes derived values:
        - number of panels needed
        - sun angle at worst case (winter solstice)
        - shadow length cast by the array
        - north–south spacing between PV rows (rounded to plant-row boundary)
    """

    def __init__(
        self,
        production_kw: float,
        battery_size: float,
        system_height_m: float,
        latitude: float,
    ):
        self.production_kw   = production_kw
        self.battery_size    = battery_size
        self.system_height_m = system_height_m
        self.latitude        = latitude

        # derived
        self.num_panels    = math.ceil((production_kw * 1000) / PANEL_WATT)
        self.sun_angle_deg = self._sun_angle()
        self.shadow_length = self._shadow_length()
        self.row_spacing   = self._row_spacing()   # gap between PV rows (edge to edge)

    # ── private helpers ───────────────────────────────────────────────────────

    def _sun_angle(self) -> float:
        """Worst-case solar elevation (winter solstice, solar noon)."""
        return 90 - abs(self.latitude - 23.5)

    def _shadow_length(self) -> float:
        """Horizontal shadow cast northward by the array at worst-case sun angle."""
        return self.system_height_m / math.tan(math.radians(self.sun_angle_deg))

    def _row_spacing(self) -> float:
        """
        Distance from the northern edge of one PV row to the southern edge
        of the next = 2 × shadow, rounded up to the nearest 2.5 m so PV rows
        always start at a plant-row boundary.
        """
        raw = 2 * self.shadow_length
        return math.ceil(raw / ROW_SPACING) * ROW_SPACING

    def to_dict(self) -> dict:
        return {
            "production_kw":   self.production_kw,
            "battery_size":    self.battery_size,
            "system_height_m": self.system_height_m,
            "latitude":        self.latitude,
            "num_panels":      self.num_panels,
            "sun_angle_deg":   round(self.sun_angle_deg, 2),
            "shadow_length_m": round(self.shadow_length, 2),
            "row_spacing_m":   self.row_spacing,
        }
