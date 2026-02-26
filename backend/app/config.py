from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import List, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .quality_controls import QualitySettings

EntryTF = Literal["15m", "1h", "4h", "1d"]


class SetupsConfig(BaseModel):
    continuation: bool
    retest: bool
    fakeout: bool
    setup_candle: bool


class LevelOverrides(BaseModel):
    add: List[float] = Field(default_factory=list)
    disable: List[float] = Field(default_factory=list)


class LevelsConfig(BaseModel):
    auto: bool
    max_levels: int = Field(ge=1)
    cluster_tol_pct: float = Field(gt=0, lt=1)
    overrides: LevelOverrides


class SymbolConfig(BaseModel):
    symbol: str = Field(min_length=1)
    enabled: bool
    entry_tfs: List[EntryTF] = Field(min_length=1)
    setups: SetupsConfig
    levels: LevelsConfig

    @field_validator("symbol", mode="before")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip().upper()
        return value

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Z0-9]{6,}", value):
            raise ValueError("symbol must match ^[A-Z0-9]{6,}$")
        return value

    @field_validator("entry_tfs")
    @classmethod
    def unique_entry_tfs(cls, value: List[EntryTF]) -> List[EntryTF]:
        if len(set(value)) != len(value):
            raise ValueError("entry_tfs must be unique")
        return value


class GlobalConfig(BaseModel):
    max_alerts_per_symbol_per_day: int = Field(ge=1)
    cooldown_minutes: int = Field(ge=0)


class WatchlistConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    symbols: List[SymbolConfig] = Field(min_length=1)
    global_: GlobalConfig = Field(alias="global")
    quality: QualitySettings = Field(default_factory=QualitySettings)


DEFAULT_LOCAL_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def get_data_dir() -> Path:
    env_dir = os.getenv("DATA_DIR")
    if env_dir:
        return Path(env_dir)
    return DEFAULT_LOCAL_DATA_DIR


def get_watchlist_path() -> Path:
    path = os.getenv("WATCHLIST_PATH")
    if path:
        candidate = Path(path)
        if candidate.exists():
            return candidate
        fallback = DEFAULT_LOCAL_DATA_DIR / "watchlist.json"
        if fallback.exists():
            return fallback
        return candidate
    return get_data_dir() / "watchlist.json"


def load_watchlist(path: Path | None = None) -> WatchlistConfig:
    path = path or get_watchlist_path()
    data = json.loads(path.read_text(encoding="utf-8"))
    return WatchlistConfig.model_validate(data)


def save_watchlist(data: dict, path: Path | None = None) -> WatchlistConfig:
    path = path or get_watchlist_path()
    config = WatchlistConfig.model_validate(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(config.model_dump(by_alias=True), indent=2)
    with tempfile.NamedTemporaryFile("w", delete=False, dir=path.parent, encoding="utf-8") as tmp:
        tmp.write(payload)
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, path)
    return config


def get_poll_seconds() -> int:
    return int(os.getenv("POLL_SECONDS", "15"))


def get_poller_start_paused() -> bool:
    flag = os.getenv("POLLER_START_PAUSED")
    if flag is None:
        return False
    return flag.lower() in {"1", "true", "yes"}


def telegram_enabled() -> bool:
    flag = os.getenv("TELEGRAM_ENABLED")
    if flag is not None:
        return flag.lower() in {"1", "true", "yes"}
    return bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"))
