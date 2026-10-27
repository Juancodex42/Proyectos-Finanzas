"""Backward compatibility facade for services.config_service."""
from services.config_service import (
    BASE_DIR,
    CONFIG_FILE,
    DEFAULT_MAPPINGS,
    current_config,
    load_config,
    save_config,
    get_column,
    get_date_format,
    update_mapping,
    BACKEND_DIR,
    ENV_FILE,
    get_env_keys,
    set_env_keys,
)

__all__ = [
    "BASE_DIR",
    "CONFIG_FILE",
    "DEFAULT_MAPPINGS",
    "current_config",
    "load_config",
    "save_config",
    "get_column",
    "get_date_format",
    "update_mapping",
    "BACKEND_DIR",
    "ENV_FILE",
    "get_env_keys",
    "set_env_keys",
]
