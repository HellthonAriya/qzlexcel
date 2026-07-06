import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
EXCEL_PATH = os.getenv("EXCEL_PATH", "data/source.xlsx").strip()
DB_PATH = os.getenv("DB_PATH", "data/state.db").strip()
PAGE_SIZE = int(os.getenv("PAGE_SIZE", "5"))
TMP_DIR = os.path.join(os.path.dirname(DB_PATH) or ".", "tmp")

ALLOWED_USER_IDS = {
    int(uid)
    for uid in os.getenv("ALLOWED_USER_IDS", "").replace(" ", "").split(",")
    if uid
}


def is_allowed(user_id: int) -> bool:
    if not ALLOWED_USER_IDS:
        return True
    return user_id in ALLOWED_USER_IDS
