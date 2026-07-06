import logging
import os
import sys


def _check_ptb_version():
    try:
        import telegram
    except ImportError:
        sys.exit("کتابخانه‌ی python-telegram-bot نصب نیست. اجرا کنید:\n  pip install -r requirements.txt")
    if not hasattr(telegram, "CopyTextButton"):
        sys.exit(
            "نسخه‌ی نصب‌شده‌ی python-telegram-bot قدیمی است و از دکمه‌ی کپی متن پشتیبانی نمی‌کند.\n"
            "این دستور را اجرا کنید و دوباره امتحان کنید:\n"
            '  pip install --upgrade "python-telegram-bot>=21.3"'
        )


_check_ptb_version()

from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from app import config
from app.data_store import DataStore
from app.handlers import (
    cmd_export,
    cmd_reload,
    cmd_reset_status,
    cmd_start,
    on_callback,
    on_document,
    on_text,
)
from app.storage import StateStore

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


def main():
    if not config.BOT_TOKEN:
        sys.exit("BOT_TOKEN تنظیم نشده است. فایل .env را بررسی کنید.")

    state_store = StateStore(config.DB_PATH)
    store = None
    if os.path.exists(config.EXCEL_PATH):
        store = DataStore(config.EXCEL_PATH, state_store, config.TMP_DIR)
    else:
        logger.warning(
            "فایل اکسل در مسیر %s یافت نشد. منتظر ارسال فایل از طریق تلگرام می‌مانم.",
            config.EXCEL_PATH,
        )

    application = ApplicationBuilder().token(config.BOT_TOKEN).build()
    application.bot_data["store"] = store
    application.bot_data["state_store"] = state_store

    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("export", cmd_export))
    application.add_handler(CommandHandler("reload", cmd_reload))
    application.add_handler(CommandHandler("reset_status", cmd_reset_status))
    application.add_handler(CallbackQueryHandler(on_callback))
    application.add_handler(MessageHandler(filters.Document.ALL, on_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    logger.info("Bot started.")
    application.run_polling()


if __name__ == "__main__":
    main()
