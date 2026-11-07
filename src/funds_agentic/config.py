"""Portable TOML configuration, with explicit CLI overrides."""
from __future__ import annotations
import argparse
import os
import socket
import re
from pathlib import Path
import tomllib
from .models import Config

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_ROOT / "configuration" / "settings.toml"

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Collect and validate Trustnet funds and sectors; CSV only")
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    src = p.add_mutually_exclusive_group()
    src.add_argument("--input", dest="input_path")
    src.add_argument("--gsheet-url")
    src.add_argument("--gdrive-id")
    p.add_argument("--output", dest="output_dir")
    p.add_argument("--sheet")
    p.add_argument("--row-start", type=int)
    p.add_argument("--col-url")
    p.add_argument("--col-hold")
    p.add_argument("--col-holding")
    p.add_argument("--retries-per-url", type=int, help="Total attempts per navigation")
    p.add_argument("--nav-timeout", dest="nav_timeout_sec", type=int)
    p.add_argument("--limit", type=int, help="Verification subset; never publishes compatibility exports")
    p.add_argument("--check", action="store_true", help="Validate settings and input without opening a browser")
    p.add_argument("--no-legacy-columns", dest="legacy_columns", action="store_false", default=None)
    group = p.add_mutually_exclusive_group()
    group.add_argument("--headless", dest="headless", action="store_true", default=None)
    group.add_argument("--no-headless", dest="headless", action="store_false")
    return p

def load_config(args: argparse.Namespace) -> Config:
    path = args.config.resolve()
    if not path.is_file():
        raise ValueError(f"Configuration file not found: {path}")
    settings = tomllib.loads(path.read_text(encoding="utf-8-sig"))
    shared_root = (path.parent / settings.get("shared_root", ".")).resolve()
    values = dict(settings.get("scraper", {}))
    machine_id = os.environ.get("FUNDS_COMPUTER_ID") or socket.gethostname()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", machine_id):
        raise ValueError("Invalid computer identifier")
    machine = path.parent / "machines" / f"{machine_id.lower()}.local.toml"
    if machine.is_file():
        local = tomllib.loads(machine.read_text(encoding="utf-8-sig"))
        if "shared_root" in local:
            shared_root = (path.parent / local["shared_root"]).resolve()
        values.update(local.get("scraper", {}))
    cli = {k: v for k, v in vars(args).items() if k not in {"config", "check"} and v is not None}
    if any(k in cli for k in ("input_path", "gsheet_url", "gdrive_id")):
        for key in ("input_path", "gsheet_url", "gdrive_id"):
            values.pop(key, None)
    values.update(cli)
    # All relative data paths, including CLI overrides, are relative to shared_root.
    for key in ("input_path", "output_dir"):
        if values.get(key):
            values[key] = (shared_root / values[key]).resolve()
    return Config.model_validate(values)
