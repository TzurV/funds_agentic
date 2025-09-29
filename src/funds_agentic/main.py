# --- add at the top (new imports)
import argparse
import sys

from funds_agentic.graph import build_graph
from funds_agentic.utils.logging_setup import setup_logger

logger = setup_logger()


def _parse_vis_args(argv):
    """Parse ONLY the visualization flags and return (vis_args, remaining)."""
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--graph-out", type=str, default=None)
    p.add_argument("--graph-format", type=str,
                   default="png", choices=["png", "mermaid"])
    vis_args, remaining = p.parse_known_args(argv)
    return vis_args, remaining


def _save_graph_visual(app, out_path: str, fmt: str):
    g = app.get_graph()
    if fmt == "png":
        # Mermaid PNG export (writes to file)
        g.draw_mermaid_png(output_file_path=out_path)
        logger.info("graph_exported", extra={
                    "kv": {"path": out_path, "format": "png"}})
    else:
        # Mermaid text export
        mermaid = g.draw_mermaid()  # returns Mermaid syntax as str
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(mermaid)
        logger.info("graph_exported", extra={
                    "kv": {"path": out_path, "format": "mermaid"}})


def cli() -> None:
    # 1) Parse & REMOVE visualization flags from argv
    vis, remaining = _parse_vis_args(sys.argv[1:])
    # <- remove vis flags so config_node won't see them
    sys.argv = [sys.argv[0]] + remaining

    # 2) Build compiled graph
    app = build_graph()

    # 3) Optionally save graph visualization before running
    if vis.graph_out:
        _save_graph_visual(app, vis.graph_out, vis.graph_format)

    # 4) Run pipeline
    result = app.invoke({})
    state = result.get("state", {})
    funds_csv = state.get("funds_csv_path")
    sectors_csv = state.get("sectors_csv_path")
    failed = state.get("failed_urls", [])
    logger.info("run_complete", extra={"kv": {
        "funds_csv": funds_csv,
        "sectors_csv": sectors_csv,
        "failed_urls": len(failed),
    }})


if __name__ == "__main__":
    cli()
