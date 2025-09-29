import logging
import sys


class KeyValueFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = {
            "level": record.levelname,
            "msg": record.getMessage(),
        }
        # Merge extra fields if present
        if hasattr(record, "kv") and isinstance(record.kv, dict):
            base.update(record.kv)
        return " ".join(f"{k}={repr(v)}" if isinstance(v, str) else f"{k}={v}" for k, v in base.items())


def setup_logger(name: str = "funds_agentic", level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(KeyValueFormatter())
        logger.addHandler(handler)
    logger.propagate = False
    return logger
