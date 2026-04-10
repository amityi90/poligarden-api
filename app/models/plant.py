from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Plant:
    id: int
    name: str
    planting_start: int
    planting_end: int
    harvesting_start: int
    harvesting_end: int
    water: int
    shadow: bool
    height: int
    spread: int
    body_water: bool
    is_tree: bool = False
    companion_plants: list[Plant] = field(default_factory=list)
    antagonistic_plants: list[Plant] = field(default_factory=list)

    @classmethod
    def from_db_row(cls, row: dict) -> Plant:
        """Create a Plant from a raw Supabase row (no relations attached yet)."""
        return cls(
            id=row["id"],
            name=row["name"],
            planting_start=row["planting_start"],
            planting_end=row["planting_end"],
            harvesting_start=row["harvesting_start"],
            harvesting_end=row["harvesting_end"],
            water=row["water"],
            shadow=row["shadow"],
            height=row["height"],
            spread=row["spread"],
            body_water=row["body_water"],
            is_tree=row.get("is_tree", False),
        )

    def to_dict(self) -> dict:
        """Serialize to a JSON-safe dict, including related plant lists."""
        return {
            "id": self.id,
            "name": self.name,
            "planting_start": self.planting_start,
            "planting_end": self.planting_end,
            "harvesting_start": self.harvesting_start,
            "harvesting_end": self.harvesting_end,
            "water": self.water,
            "shadow": self.shadow,
            "height": self.height,
            "spread": self.spread,
            "body_water": self.body_water,
            "is_tree": self.is_tree,
            "companion_plants": [p.to_dict() for p in self.companion_plants],
            "antagonistic_plants": [p.to_dict() for p in self.antagonistic_plants],
        }
