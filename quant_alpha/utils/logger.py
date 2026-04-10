import logging
import logging.config
import yaml
from pathlib import Path

def setup_logging(config_path: str = "config/logging.yaml") -> None:
    p = Path(config_path)
    if not p.exists():
        logging.basicConfig(level=logging.INFO)
        return
    with p.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    logging.config.dictConfig(cfg)

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
