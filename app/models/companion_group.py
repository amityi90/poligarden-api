from __future__ import annotations
from dataclasses import dataclass, field
from app.models.plant import Plant


@dataclass
class CompanionGroup:
    plants: list[Plant] = field(default_factory=list)
    trees_companion: list[Plant] = field(default_factory=list)
    non_antagonistic_plants: list[Plant] = field(default_factory=list)
    planting_length: float = 0.0

    def plant_ids(self) -> set[int]:
        return {p.id for p in self.plants}

    def can_accept(self, plant: Plant, plant_antagonist_ids: set[int]) -> bool:
        """
        A plant can join this group only if it has NO antagonistic
        relationship with any plant already in the group.
        """
        return not (self.plant_ids() & plant_antagonist_ids)

    def companion_score(self, plant: Plant, plant_companion_ids: set[int]) -> int:
        """How many plants already in the group are companions of the candidate."""
        return len(self.plant_ids() & plant_companion_ids)

    def arrange_plants(self) -> None:
        """
        Reorder self.plants so that every consecutive pair are mutual companions:
        each plant is in the companion list of its neighbour, or its neighbour
        is in its companion list.

        Algorithm: greedy chain.
          - Build a companion-edge set for plants within the group.
          - Pick the plant with the fewest in-group companions as the start
            (end of chain, so it doesn't strand anyone).
          - At each step, extend the chain with the connected unvisited plant
            that itself has the fewest remaining connections (prefer plants
            that would be hard to place later).
          - If no connected plant exists, append the remaining plants in the
            same greedy order (they have no companion edge to the chain).
        """
        if len(self.plants) <= 1:
            return

        ids = {p.id for p in self.plants}
        by_id = {p.id: p for p in self.plants}

        # companion edges within the group only
        def connected(a: Plant, b: Plant) -> bool:
            a_companions = {c.id for c in a.companion_plants}
            b_companions = {c.id for c in b.companion_plants}
            return b.id in a_companions or a.id in b_companions

        def in_group_degree(p: Plant) -> int:
            return sum(1 for q in self.plants if q.id != p.id and connected(p, q))

        unvisited = set(ids)

        # start with the plant that has the fewest in-group companion connections
        start = min(self.plants, key=in_group_degree)
        chain = [start]
        unvisited.remove(start.id)

        while unvisited:
            current = chain[-1]
            # candidates: unvisited plants connected to current
            neighbours = [
                by_id[pid] for pid in unvisited if connected(current, by_id[pid])
            ]
            if neighbours:
                # pick the neighbour with fewest remaining connections (hardest to place)
                nxt = min(neighbours, key=lambda p: sum(
                    1 for pid in unvisited - {p.id} if connected(p, by_id[pid])
                ))
            else:
                # no companion edge — just pick least-connected remaining plant
                nxt = min((by_id[pid] for pid in unvisited), key=in_group_degree)

            chain.append(nxt)
            unvisited.remove(nxt.id)

        self.plants = chain

    def to_dict(self) -> dict:
        return {
            "plants": [p.to_dict() for p in self.plants],
            "trees_companion": [t.to_dict() for t in self.trees_companion],
            "non_antagonistic_plants": [p.to_dict() for p in self.non_antagonistic_plants],
            "planting_length": self.planting_length,
        }
