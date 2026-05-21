"""Load AWS_EXPERIMENTS_* config from a local .env file into os.environ."""


import os
import pathlib


DEFAULT_CONFIG_PATH = pathlib.Path(".env")
CONFIG_PREFIX = "AWS_EXPERIMENTS_"


def load_experiments_config(path: pathlib.Path = DEFAULT_CONFIG_PATH) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key.startswith(CONFIG_PREFIX):
            continue
        os.environ.setdefault(key, value.strip().strip("'\""))


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"{name} is required in .env or the environment")
    return value
