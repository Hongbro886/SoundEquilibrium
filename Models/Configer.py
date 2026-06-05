import Models.System
from types import SimpleNamespace
import json

CONFIG_PATH = Models.System.get_app_dir() / "config.json"


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return SimpleNamespace(**data)

def save_config(config):
    if isinstance(config, SimpleNamespace):
        config = vars(config)

    with CONFIG_PATH.open("w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
