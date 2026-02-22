# common/config.py
import os, json, logging
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN") or ""
if not BOT_TOKEN:
    raise SystemExit("BOT_TOKEN not set")

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    TASK_CONFIG = json.load(f)

def get_task_config(kind: str) -> dict:
    if kind not in TASK_CONFIG:
        raise KeyError(f"Unknown task type: {kind}")
    return TASK_CONFIG[kind]

def get_config_emoji(kind: str) -> str:
    """Return the emoji defined for this kind in config.json, or '' if none."""
    return TASK_CONFIG.get(kind, {}).get("emoji", "")

def get_shopping_digest_schedule() -> tuple[int, int]:
    cfg = TASK_CONFIG["buy"]
    return int(cfg["shopping_digest_day"]), int(cfg["shopping_digest_hour"])

logging.basicConfig(
    level=os.getenv("LOGLEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("recuerdabot")
