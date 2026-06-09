from app.plants_db import plants_cursor, fetch_relations
from app.models.plant import Plant


class PlantService:

    @staticmethod
    def get_all() -> list[Plant]:
        """
        Fetch all plants and attach their companion and antagonistic plant lists.
        Three flat queries joined in Python to avoid the N+1 problem — same shape
        as before, only the source changed: companions/antagonists now come from
        the single `plant_relations` table (is_companion = true / false).
        """
        with plants_cursor() as cur:
            cur.execute("SELECT * FROM plants WHERE approved ORDER BY id")
            plant_rows = cur.fetchall()

            companion_rows  = fetch_relations(cur, True)    # is_companion = true
            antagonist_rows = fetch_relations(cur, False)   # is_companion = false

        # Build relation maps  { owner_plant_id -> [Plant, ...] }
        companions_map: dict[int, list[Plant]] = {}
        for row in companion_rows:
            companions_map.setdefault(row["owner_id"], []).append(Plant.from_db_row(row))

        antagonists_map: dict[int, list[Plant]] = {}
        for row in antagonist_rows:
            antagonists_map.setdefault(row["owner_id"], []).append(Plant.from_db_row(row))

        # Assemble final Plant objects with relations attached
        plants: list[Plant] = []
        for row in plant_rows:
            plant = Plant.from_db_row(row)
            plant.companion_plants = companions_map.get(plant.id, [])
            plant.antagonistic_plants = antagonists_map.get(plant.id, [])
            plants.append(plant)

        return plants
