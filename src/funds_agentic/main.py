# --- add at the top (new imports)
import argparse
import sys

from funds_agentic.graph import build_graph
from funds_agentic.utils.logging_setup import setup_logger

logger = setup_logger()


def _parse_vis_args(argv):
    """
    Parse just our visualization flags up-front, then leave the rest of the args
    intact for the in-graph argparse (config_node) to consume as before.
    """
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--graph-out", type=str, default=None,
                   help="If set, save a LangGraph visualization to this path (e.g., graph.png or graph.mmd).")
    p.add_argument("--graph-format", type=str, default="png", choices=["png", "mermaid"],
                   help="Visualization format: png (image) or mermaid (text). Default: png.")
    # Only parse known flags we care about; leave the rest in sys.argv as-is
    args, _ = p.parse_known_args(argv)
    return args


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
    # 1) Parse visualization opts first (doesn't consume other args)
    vis = _parse_vis_args(sys.argv[1:])

    # 2) Build compiled graph (unchanged)
    app = build_graph()

    # 3) If requested, save visualization before running
    if vis.graph_out:
        _save_graph_visual(app, vis.graph_out, vis.graph_format)

    # 4) Run the pipeline (unchanged)
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
