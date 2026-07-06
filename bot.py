import logging
import os
import sys

from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from app import config
from app.data_store import DataStore
from app.handlers import cmd_export, cmd_reload, cmd_reset_status, cmd_start, on_callback, on_text
from app.storage import StateStore

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


def main():
    if not config.BOT_TOKEN:
        sys.exit("BOT_TOKEN تنظیم نشده است. فایل .env را بررسی کنید.")

    if not os.path.exists(config.EXCEL_PATH):
        sys.exit(f"فایل اکسل یافت نشد: {config.EXCEL_PATH}")

    state_store = StateStore(config.DB_PATH)
    store = DataStore(config.EXCEL_PATH, state_store, config.TMP_DIR)

    application = ApplicationBuilder().token(config.BOT_TOKEN).build()
    application.bot_data["store"] = store
    application.bot_data["state_store"] = state_store

    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("export", cmd_export))
    application.add_handler(CommandHandler("reload", cmd_reload))
    application.add_handler(CommandHandler("reset_status", cmd_reset_status))
    application.add_handler(CallbackQueryHandler(on_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    logger.info("Bot started.")
    application.run_polling()


if __name__ == "__main__":
    main()
