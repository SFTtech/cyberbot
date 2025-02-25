import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, field_validator


class StorageConfig(BaseModel):
    database_path: Path
    cryptostate_path: Path

    def set_paths(self, basedir: Path):
        self.database_path = basedir / self.database_path
        if not self.database_path.parent.is_dir():
            raise ValueError(f"not a directory: {self.database_path!r}")

        self.cryptostate_path = basedir / self.cryptostate_path
        if not self.cryptostate_path.is_dir():
            raise ValueError(f"not a directory: {self.cryptostate_path!r}")


class MatrixConfig(BaseModel):
    # must be full mxid because nio.Client.restore_login wants the full id.
    # even though we look it up shortly after with a whoami request.
    user: str
    password: str
    homeserver: str
    deviceid: str | None

    @field_validator('user')
    def name_must_be_full_mxid(cls, val):
        if not re.match(r'@[^:]+:.+', val):
            raise ValueError('user must be the full matrix id @user:server.lol')
        return val


class BotConfig(BaseModel):
    name: str
    rooms_allowed: list[str]
    admins: list[str]


class Config(BaseModel):
    storage: StorageConfig
    matrix: MatrixConfig
    bot: BotConfig

    # for external plugins to load
    load_modules: list[str]

    # modulename -> kv-config
    config: dict[str, dict[str, Any]]


def read_config(config: os.PathLike) -> Config:
    config_path = Path(config)

    with open(config_path, "r") as config_file:
        content = yaml.safe_load(config_file)
        cfg = Config(**content)

        # make relative to config files' directory
        cfg.storage.set_paths(config_path.parent)
        return cfg
