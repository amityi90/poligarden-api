from flask import Flask, request, jsonify
from .routes.plants import plants_bp
from .routes.pv import pv_bp
from .routes.field import field_bp
from .routes.pdf import pdf_bp


def create_app():
    app = Flask(__name__)

    # Manual CORS — more reliable than flask-cors for preflight handling.
    # Every response gets the allow-origin header; OPTIONS preflights get 200.
    @app.after_request
    def add_cors_headers(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, PUT, DELETE"
        return response

    @app.before_request
    def handle_preflight():
        if request.method == "OPTIONS":
            return "", 200

    app.register_blueprint(plants_bp)
    app.register_blueprint(pv_bp)
    app.register_blueprint(field_bp)
    app.register_blueprint(pdf_bp)

    return app
