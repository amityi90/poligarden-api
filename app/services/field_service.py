from app.db import get_db
from app.models.plant import Plant
from app.models.tree import Tree
from app.models.companion_group import CompanionGroup
from app.models.field_layout import FieldLayout
from app.models.pv_system import PVSystem


class FieldService:

    @staticmethod
    def get_plants_by_ids(plant_ids: list[int]) -> list[Plant]:
        """Fetch the chosen plants from DB by their IDs."""
        db = get_db()

        plant_rows = (
            db.table("plants")
            .select("*")
            .in_("id", plant_ids)
            .execute()
            .data
        )

        companion_rows = (
            db.table("companion_plants")
            .select("plant_id, companion:companion_plant_id(*)")
            .in_("plant_id", plant_ids)
            .execute()
            .data
        )

        antagonist_rows = (
            db.table("antagonistic_plants")
            .select("plant_id, antagonist:antagonistic_plant_id(*)")
            .in_("plant_id", plant_ids)
            .execute()
            .data
        )

        companions_map: dict[int, list[Plant]] = {}
        for row in companion_rows:
            pid = row["plant_id"]
            companions_map.setdefault(pid, []).append(
                Plant.from_db_row(row["companion"])
            )

        antagonists_map: dict[int, list[Plant]] = {}
        for row in antagonist_rows:
            pid = row["plant_id"]
            antagonists_map.setdefault(pid, []).append(
                Plant.from_db_row(row["antagonist"])
            )

        plants: list[Plant] = []
        for row in plant_rows:
            plant = Plant.from_db_row(row)
            plant.companion_plants = companions_map.get(plant.id, [])
            plant.antagonistic_plants = antagonists_map.get(plant.id, [])
            plants.append(plant)

        return plants

    @staticmethod
    def separate_trees(plants: list[Plant]) -> tuple[list[Plant], list[Tree]]:
        """Split into (non_trees, trees). Promotes tree plants to Tree instances."""
        non_trees = [p for p in plants if not p.is_tree]
        raw_trees = [p for p in plants if p.is_tree]

        trees: list[Tree] = []
        for plant in raw_trees:
            tree = Tree.from_plant(plant)

            companion_ids   = {c.id for c in tree.companion_plants}
            antagonist_ids  = {a.id for a in tree.antagonistic_plants}
            # IDs of non-trees that have this tree in their antagonistic list
            antagonised_by  = {p.id for p in non_trees if any(a.id == tree.id for a in p.antagonistic_plants)}

            tree.companion_non_tree_plants = [
                p for p in non_trees if p.id in companion_ids
            ]
            tree.non_antagonistic_plants = [
                p for p in non_trees
                if p.id not in companion_ids
                and p.id not in antagonist_ids
                and p.id not in antagonised_by
            ]

            # Build companion groups from companion non-tree plants.
            # If fewer than 2 groups result, combine with non_antagonistic_plants
            # so there is at least one well-populated group (up to 6 plants).
            groups = FieldService.build_companion_groups(tree.companion_non_tree_plants)
            if len(groups) <= 1:
                seen_ids = {p.id for p in tree.companion_non_tree_plants}
                combined = list(tree.companion_non_tree_plants)
                for p in tree.non_antagonistic_plants:
                    if p.id not in seen_ids:
                        combined.append(p)
                        seen_ids.add(p.id)
                    if len(combined) >= 6:
                        break
                groups = FieldService.build_companion_groups(combined)
            tree.companion_groups = groups

            trees.append(tree)

        return non_trees, trees

    @staticmethod
    def separate_by_shadow(plants: list[Plant]) -> tuple[list[Plant], list[Plant]]:
        """Split plants into (shadow_lovers, sun_lovers)."""
        shadow = [p for p in plants if p.shadow]
        sun    = [p for p in plants if not p.shadow]
        return shadow, sun

    @staticmethod
    def build_companion_groups(plants: list[Plant]) -> list[CompanionGroup]:
        """
        Group plants into CompanionGroups following two rules:
          1. Plants in the same group must not be antagonists of each other.
          2. Prefer placing a plant in a group where it already has companions.

        Algorithm:
          - Sort by companion count descending so well-connected plants
            anchor groups first — this reduces the number of singleton groups.
          - For each plant, score every existing group by how many companions
            it already has there. Pick the highest-scoring group that has no
            antagonist conflict. If none fits, open a new singleton group.
        """
        # Pre-compute companion/antagonist ID sets per plant (IDs only, fast lookup)
        companion_ids: dict[int, set[int]] = {
            p.id: {c.id for c in p.companion_plants} for p in plants
        }
        antagonist_ids: dict[int, set[int]] = {
            p.id: {a.id for a in p.antagonistic_plants} for p in plants
        }

        # Sort most-connected first so they anchor groups early
        sorted_plants = sorted(plants, key=lambda p: len(companion_ids[p.id]), reverse=True)

        groups: list[CompanionGroup] = []

        for plant in sorted_plants:
            p_antagonists = antagonist_ids[plant.id]
            p_companions  = companion_ids[plant.id]

            best_group: CompanionGroup | None = None
            best_score = -1

            for group in groups:
                if not group.can_accept(plant, p_antagonists):
                    continue
                score = group.companion_score(plant, p_companions)
                if score > best_score:
                    best_score = score
                    best_group = group

            if best_group is not None:
                best_group.plants.append(plant)
            else:
                new_group = CompanionGroup()
                new_group.plants.append(plant)
                groups.append(new_group)

        groups = [g for g in groups if len(g.plants) > 2]

        for group in groups:
            group.arrange_plants()
            group.planting_length = sum(p.spread for p in group.plants) / 100 * 3

        return groups

    @staticmethod
    def assign_non_antagonistic_plants(
        groups: list[CompanionGroup], non_tree_plants: list[Plant]
    ) -> None:
        """
        For each group, find plants from the selected non-tree list that are:
          - not already in this group
          - not antagonistic to any plant in this group (in either direction)
        """
        for group in groups:
            group_ids = group.plant_ids()
            group_antagonist_ids: set[int] = set()
            for p in group.plants:
                for a in p.antagonistic_plants:
                    group_antagonist_ids.add(a.id)

            group.non_antagonistic_plants = [
                p for p in non_tree_plants
                if p.id not in group_ids
                and p.id not in group_antagonist_ids
                and not (group_ids & {a.id for a in p.antagonistic_plants})
            ]

    @staticmethod
    def assign_trees_to_groups(
        groups: list[CompanionGroup], trees: list[Plant]
    ) -> None:
        """
        For each companion group, rank the selected trees by how many plants
        in the group list them as a companion — excluding any tree that appears
        in any group plant's antagonistic list.  Assigns sorted list in-place.
        """
        tree_ids = {t.id for t in trees}
        trees_by_id = {t.id: t for t in trees}

        for group in groups:
            # Collect antagonist IDs across all plants in this group
            antagonist_ids: set[int] = set()
            for plant in group.plants:
                for a in plant.antagonistic_plants:
                    antagonist_ids.add(a.id)

            # Count how many plants in the group mention each tree as a companion
            counts: dict[int, int] = {}
            for plant in group.plants:
                for c in plant.companion_plants:
                    if c.id in tree_ids and c.id not in antagonist_ids:
                        counts[c.id] = counts.get(c.id, 0) + 1

            group.trees_companion = [
                trees_by_id[tid]
                for tid, _ in sorted(counts.items(), key=lambda x: x[1], reverse=True)
            ]

    @staticmethod
    def build_layout(
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
    ) -> FieldLayout:
        return FieldLayout(
            field_length, field_width, pv_system,
            trees=trees,
            shadow_groups=shadow_groups, sun_groups=sun_groups,
            non_tree_plants=non_tree_plants,
            shadow_ungrouped=shadow_ungrouped, sun_ungrouped=sun_ungrouped,
            neutral_plants=neutral_plants,
        ).build()
