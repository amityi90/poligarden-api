from app.services.field_service import FieldService
from app.models.garden_layout import GardenLayout


class GardenService:
    """Garden Planner orchestration — reuses the field planner's plant fetch
    (which attaches companion/antagonist relationships) and runs the Ecological
    Circle Packing layout. Trees are excluded: the garden is non-tree only."""

    @staticmethod
    def get_non_tree_plants(plant_ids: list[int]):
        plants = FieldService.get_plants_by_ids(plant_ids)
        return [p for p in plants if not p.is_tree]

    @staticmethod
    def build_layout(field_length: float, field_width: float, plants, on_progress=None) -> GardenLayout:
        return GardenLayout(field_length, field_width, plants).build(on_progress=on_progress)
