from flask import Blueprint, jsonify
from app.services.plant_service import PlantService

plants_bp = Blueprint("plants", __name__)


@plants_bp.get("/all_plants")
def get_all_plants():
    plants = PlantService.get_all()
    return jsonify([p.to_dict() for p in plants])
