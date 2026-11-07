"""CSV snapshots, completion metadata, and recoverable compatibility exports."""
from __future__ import annotations
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import socket
from .models import Config, RunResult

FUNDS_COLUMNS = ["date", "fundName", "Quartile", "FERisk", "3m", "6m", "1y", "3y", "5y",
                 "url", "Hold", "Holding%", "Sector", "SectorUrl", "price"]
SECTORS_COLUMNS = ["date", "sectorName", "1m", "3m", "6m", "1y", "3y", "5y"]

@contextmanager
def output_lock(directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    lock = directory / ".funds-agentic.lock"
    try:
        handle = lock.open("x", encoding="utf-8")
    except FileExistsError as exc:
        raise RuntimeError(f"An output lock exists: {lock}. Check its owner before removing a stale lock.") from exc
    try:
        with handle:
            json.dump({"pid": os.getpid(), "computer": socket.gethostname()}, handle)
        yield
    finally:
        lock.unlink(missing_ok=True)

def atomic_json(path: Path, data: dict) -> None:
    temporary = path.with_name(path.name + ".tmp")
    try:
        temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)

def write_manifest(result: RunResult) -> None:
    data = result.model_dump(mode="json", exclude={"funds", "sectors"})
    data["collected_funds"] = len(result.funds)
    data["collected_sectors"] = len(result.sectors)
    data["fund_source_dates"] = {row.url: row.source_date for row in result.funds}
    data["fund_price_dates"] = {row.url: row.price_date for row in result.funds}
    data["fund_price_units"] = {row.url: row.price_unit for row in result.funds}
    data["fund_warnings"] = {row.url: row.warnings for row in result.funds if row.warnings}
    data["sector_source_dates"] = sorted({row.source_date for row in result.sectors if row.source_date})
    atomic_json(Path(result.snapshot_dir) / "run.json", data)

def publish_result(result: RunResult, cfg: Config) -> None:
    import pandas as pd
    root = cfg.output_dir
    stage = root / ".staging" / result.meta.run_id
    destination = root / "runs" / result.meta.run_id
    stage.mkdir(parents=True, exist_ok=False)
    destination.parent.mkdir(parents=True, exist_ok=True)
    funds = [{"date": result.meta.timestamp, "fundName": r.name, "Quartile": r.quartile,
              "FERisk": r.fe_risk, **r.performance, "url": r.url, "Hold": r.hold,
              "Holding%": r.holding_pct, "Sector": r.sector, "SectorUrl": r.sector_url, "price": r.price}
             for r in result.funds]
    sectors = [{"date": result.meta.timestamp, "sectorName": r.name, **r.performance} for r in result.sectors]
    names = [f"{result.meta.run_date}_funds.csv", f"{result.meta.run_date}_sectors.csv"]
    for rows, columns, name in zip((funds, sectors), (FUNDS_COLUMNS, SECTORS_COLUMNS), names):
        pd.DataFrame(rows, columns=columns).to_csv(stage / name, index=True, float_format="%.2f")
    os.replace(stage, destination)
    result.snapshot_dir = str(destination)
    result.funds_csv, result.sectors_csv = (str(destination / name) for name in names)
    write_manifest(result)
    if result.status != "success":
        return
    # Immutable run directory + latest.json identify the coherent dataset. The two
    # legacy CSV aliases themselves cannot be replaced as a single transaction.
    backup = destination / "previous-exports"
    backup.mkdir()
    existed = {}
    temporaries = []
    changed = []
    try:
        for name in names:
            target = root / name
            existed[name] = target.exists()
            if existed[name]:
                shutil.copy2(target, backup / name)
            temporary = root / f".{result.meta.run_id}-{name}.tmp"
            temporaries.append(temporary)
            shutil.copyfile(destination / name, temporary)
        for name, temporary in zip(names, temporaries):
            os.replace(temporary, root / name)
            changed.append(name)
        atomic_json(root / "latest.json", {"run_id": result.meta.run_id,
            "snapshot": str(destination.relative_to(root)), "funds_csv": names[0], "sectors_csv": names[1]})
    except Exception:
        for name in changed:
            target = root / name
            if existed[name]:
                recovery = root / f".{result.meta.run_id}-{name}.recovery"
                shutil.copyfile(backup / name, recovery)
                os.replace(recovery, target)
            else:
                target.unlink(missing_ok=True)
        raise
    finally:
        for temporary in temporaries:
            temporary.unlink(missing_ok=True)
