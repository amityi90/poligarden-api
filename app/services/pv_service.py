import math
from dataclasses import dataclass


PANEL_WIDTH_M = 1.15   # each panel is 1.15 m wide (east–west)
PANEL_WATT    = 450    # each panel produces 450 W
MIN_PV_HEIGHT = 3.0    # minimum mounting height in metres
ROW_SPACING   = 2.5    # plant rows are 2.5 m wide (2 m bed + 0.5 m path)


@dataclass
class PVRange:
    min_kw: float
    max_kw: float

    def to_dict(self) -> dict:
        return {"min_kw": self.min_kw, "max_kw": self.max_kw}


class PVService:

    @staticmethod
    def calculate_range(
        latitude: float,
        field_length: float,
        field_width: float,
        pv_height: float = MIN_PV_HEIGHT,
    ) -> PVRange:
        pv_height = max(pv_height, MIN_PV_HEIGHT)

        sun_angle   = PVService._sun_angle(latitude)
        shadow_len  = PVService._shadow_length(sun_angle, pv_height)
        row_spacing = PVService._ceil_to_row_multiple(2 * shadow_len)
        max_rows    = math.floor(field_width / row_spacing) + 1

        return PVRange(
            min_kw=PVService._kw(1,        field_length),
            max_kw=PVService._kw(max_rows, field_length),
        )

    # ── private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _sun_angle(latitude: float) -> float:
        """Worst-case solar elevation angle (winter solstice, solar noon)."""
        return 90 - abs(latitude - 23.5)

    @staticmethod
    def _shadow_length(sun_angle_deg: float, pv_height_m: float) -> float:
        """Horizontal shadow cast by pv_height_m at sun_angle_deg."""
        return pv_height_m / math.tan(math.radians(sun_angle_deg))

    @staticmethod
    def _ceil_to_row_multiple(value: float) -> float:
        """Round up to the nearest multiple of 2.5 m (plant-row boundary)."""
        return math.ceil(value / ROW_SPACING) * ROW_SPACING

    @staticmethod
    def _kw(num_rows: int, field_length: float) -> float:
        panels = num_rows * (field_length / PANEL_WIDTH_M)
        return round(panels * PANEL_WATT / 1000, 2)
