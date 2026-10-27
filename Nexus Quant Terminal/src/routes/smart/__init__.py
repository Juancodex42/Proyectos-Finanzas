"""
Smart Mode modular routes package for Nexus Quant Terminal.
Registers optimizer, monte_carlo, and barbell sub-blueprints under unified smart_bp.
"""
from flask import Blueprint
from .optimizer import optimizer_bp
from .monte_carlo import monte_carlo_bp
from .barbell import barbell_bp

smart_bp = Blueprint('smart', __name__)
smart_bp.register_blueprint(optimizer_bp)
smart_bp.register_blueprint(monte_carlo_bp)
smart_bp.register_blueprint(barbell_bp)

__all__ = [
    'smart_bp',
    'optimizer_bp',
    'monte_carlo_bp',
    'barbell_bp',
]
