from app.db import get_db
from app.models.plant import Plant


class PlantService:

    @staticmethod
    def get_all() -> list[Plant]:
        """
        Fetch all plants from the DB and attach their companion and
        antagonistic plant lists. Uses 3 flat queries joined in Python
        to avoid the N+1 problem.
        """
        db = get_db()

        # 1. All plants
        plant_rows = db.table("plants").select("*").execute().data

        # 2. All companion links with the related plant's full data
        companion_rows = (
            db.table("companion_plants")
            .select("plant_id, companion:companion_plant_id(*)")
            .execute()
            .data
        )

        # 3. All antagonist links with the related plant's full data
        antagonist_rows = (
            db.table("antagonistic_plants")
            .select("plant_id, antagonist:antagonistic_plant_id(*)")
            .execute()
            .data
        )

        # Build relation maps  { plant_id -> [Plant, ...] }
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

        # Assemble final Plant objects with relations attached
        plants: list[Plant] = []
        for row in plant_rows:
            plant = Plant.from_db_row(row)
            plant.companion_plants = companions_map.get(plant.id, [])
            plant.antagonistic_plants = antagonists_map.get(plant.id, [])
            plants.append(plant)

        return plants
