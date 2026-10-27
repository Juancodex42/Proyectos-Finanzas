"""
Unified Blueprint registrar for Nexus Quant Terminal.
"""
from flask import Flask
from .data_routes import data_bp
from .backtest_routes import backtest_bp
from .plan_routes import plan_bp
from .smart import smart_bp
from .genetic_routes import genetic_bp
from .export_routes import export_bp
from .execution_routes import execution_bp


def register_routes(app: Flask) -> None:
    """Registra todos los Blueprints modulares en la aplicación Flask."""
    app.register_blueprint(data_bp)
    app.register_blueprint(backtest_bp)
    app.register_blueprint(plan_bp)
    app.register_blueprint(smart_bp)
    app.register_blueprint(genetic_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(execution_bp)


register_blueprints = register_routes

__all__ = [
    'register_routes',
    'register_blueprints',
    'data_bp',
    'backtest_bp',
    'plan_bp',
    'smart_bp',
    'genetic_bp',
    'export_bp',
    'execution_bp',
]

