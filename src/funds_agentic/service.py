"""Ordinary typed functions compose the collection and publishing workflow."""
from __future__ import annotations
import time
from .collection import browser_session, collect_fund, collect_sectors
from .inputs import load_inputs
from .models import Config, RunMeta, RunResult
from .publishing import output_lock, publish_result, write_manifest
from .utils.logging_setup import setup_logger

logger = setup_logger()

def validate_coverage(result: RunResult) -> None:
    sector_names = {row.name for row in result.sectors}
    unavailable = {"ia unclassified", "ia not yet assigned"}
    excluded = sorted({fund.sector for fund in result.funds if fund.sector and fund.sector.casefold() in unavailable})
    if excluded:
        result.warnings.append("Source supplies no IA sector comparison for: " + ", ".join(excluded))
    missing = sorted({fund.sector for fund in result.funds if fund.sector and fund.sector.startswith("IA ") and fund.sector.casefold() not in unavailable and fund.sector not in sector_names})
    outside = sorted({fund.sector for fund in result.funds if fund.sector and not fund.sector.startswith("IA ")})
    if outside:
        result.warnings.append("Sector comparison unavailable outside the IA universe: " + ", ".join(outside))
    unidentified = [fund.name for fund in result.funds if not fund.sector]
    if missing:
        result.errors.append("Missing sectors required by funds: " + ", ".join(missing))
    if unidentified:
        result.errors.append("Sector identification failed: " + ", ".join(unidentified))
    if len(result.funds) != result.requested:
        result.errors.append(f"Incomplete funds: {len(result.funds)}/{result.requested}")
    if not result.sectors:
        result.errors.append("Sector collection is empty")

def run(cfg: Config) -> RunResult:
    result = RunResult(meta=RunMeta.now())
    started = time.monotonic()
    try:
        records = load_inputs(cfg)
        result.requested = len(records)
        if cfg.limit:
            records = records[:cfg.limit]
            result.requested = len(records)
            result.warnings.append("Verification subset: compatibility exports will not be published")
        with output_lock(cfg.output_dir):
            try:
                with browser_session(cfg) as context:
                    try:
                        result.sectors = collect_sectors(context, cfg)
                    except Exception as exc:
                        result.errors.append(f"Sector collection failed: {exc}")
                    for index, rec in enumerate(records, 1):
                        try:
                            result.funds.append(collect_fund(context, rec, cfg))
                            logger.info("fund_collected", extra={"kv": {"completed": index, "total": len(records), "url": rec.url}})
                        except Exception as exc:
                            result.errors.append(f"Fund collection failed for {rec.url}: {exc}")
                            logger.warning("fund_failed", extra={"kv": {"completed": index, "total": len(records), "url": rec.url, "error": str(exc)}})
            except Exception as exc:
                result.errors.append(f"Browser session failed: {exc}")
            validate_coverage(result)
            result.status = "partial" if result.errors or cfg.limit else "success"
            if not result.funds and not result.sectors:
                result.status = "failed"
            result.duration_sec = round(time.monotonic() - started, 2)
            try:
                publish_result(result, cfg)
            except Exception as exc:
                result.status = "failed"
                result.errors.append(f"CSV publication failed: {exc}")
                if result.snapshot_dir:
                    write_manifest(result)
    except Exception as exc:
        result.status = "failed"
        result.errors.append(str(exc))
    result.duration_sec = round(time.monotonic() - started, 2)
    logger.info("run_finished", extra={"kv": {"run_id": result.meta.run_id, "status": result.status,
        "funds": len(result.funds), "requested": result.requested, "sectors": len(result.sectors),
        "duration_sec": result.duration_sec, "snapshot": result.snapshot_dir}})
    return result
