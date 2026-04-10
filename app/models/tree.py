from __future__ import annotations
from dataclasses import dataclass, field
from app.models.plant import Plant
from app.models.companion_group import CompanionGroup


@dataclass
class Tree(Plant):
    """
    A tree is a Plant with is_tree=True plus extra computed fields:
      - companion_non_tree_plants : selected non-tree plants that are companions of this tree
      - non_antagonistic_plants   : selected non-tree plants with no antagonistic
                                    relationship with this tree (in either direction)
      - companion_groups          : companion groups built from companion_non_tree_plants
                                    (padded with non_antagonistic_plants if fewer than 2 groups)
    """
    companion_non_tree_plants: list[Plant] = field(default_factory=list)
    non_antagonistic_plants: list[Plant] = field(default_factory=list)
    companion_groups: list[CompanionGroup] = field(default_factory=list)

    @classmethod
    def from_plant(cls, plant: Plant) -> Tree:
        """Promote an existing Plant instance to a Tree."""
        return cls(
            id=plant.id,
            name=plant.name,
            planting_start=plant.planting_start,
            planting_end=plant.planting_end,
            harvesting_start=plant.harvesting_start,
            harvesting_end=plant.harvesting_end,
            water=plant.water,
            shadow=plant.shadow,
            height=plant.height,
            spread=plant.spread,
            body_water=plant.body_water,
            is_tree=True,
            companion_plants=plant.companion_plants,
            antagonistic_plants=plant.antagonistic_plants,
        )

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["companion_non_tree_plants"] = [p.to_dict() for p in self.companion_non_tree_plants]
        d["non_antagonistic_plants"]   = [p.to_dict() for p in self.non_antagonistic_plants]
        d["companion_groups"]          = [g.to_dict() for g in self.companion_groups]
        return d
