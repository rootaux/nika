import os
import threading

import yaml
from schema.config_schema import ConfigSchema


class ConfigProvider:
    _config: ConfigSchema | None = None
    _path: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "crtConfig.yml")
    _lock: threading.Lock = threading.Lock()

    @classmethod
    def configure(cls, path: str):
        cls._path = path

    @classmethod
    def _load(cls) -> ConfigSchema:
        with open(cls._path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        return ConfigSchema.parse_obj(raw)

    @classmethod
    def get_config(cls) -> ConfigSchema:
        if cls._config is None:
            with cls._lock:
                if cls._config is None:
                    cls._config = cls._load()
        return cls._config
