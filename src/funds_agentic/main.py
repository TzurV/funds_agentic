"""CLI adapter; the application service also accepts Config directly."""
from __future__ import annotations
import json
import sys
from .config import build_parser, load_config
from .inputs import load_inputs
from .service import run

def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = load_config(args)
        if args.check:
            records = load_inputs(config)
            print(json.dumps({"status": "ready", "input_funds": len(records), "output_dir": str(config.output_dir)}, indent=2))
            return 0
        result = run(config)
        print(result.model_dump_json(indent=2, exclude={"funds", "sectors"}))
        return {"success": 0, "partial": 2, "failed": 1}[result.status]
    except (ValueError, OSError) as exc:
        print(f"Configuration/input error: {exc}", file=sys.stderr)
        return 1

def cli() -> None:
    raise SystemExit(main())

if __name__ == "__main__":
    cli()
