import logging
import os

from telegram import Update
from telegram.ext import ContextTypes

from app import config
from app.keyboards import page_keyboard, page_text, root_menu_keyboard, search_prompt_keyboard

logger = logging.getLogger(__name__)


def _store(context: ContextTypes.DEFAULT_TYPE):
    return context.bot_data["store"]


async def _deny(update: Update):
    if update.callback_query:
        await update.callback_query.answer("⛔️ شما اجازه دسترسی به این ربات را ندارید.", show_alert=True)
    elif update.message:
        await update.message.reply_text("⛔️ شما اجازه دسترسی به این ربات را ندارید.")


def _check_access(user_id: int) -> bool:
    return config.is_allowed(user_id)


def _render(context: ContextTypes.DEFAULT_TYPE):
    store = _store(context)
    view = context.user_data
    sheet_key = view.get("sheet")
    page = view.get("page", 0)
    query = view.get("query")

    all_records = store.search(sheet_key, query) if query else store.get_records(sheet_key)
    total = len(all_records)
    start = page * config.PAGE_SIZE
    page_records = all_records[start : start + config.PAGE_SIZE]

    text = page_text(sheet_key, page_records, total, page, config.PAGE_SIZE, query)
    keyboard = page_keyboard(sheet_key, page_records, page, total, config.PAGE_SIZE, bool(query))
    return text, keyboard


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _check_access(update.effective_user.id):
        await _deny(update)
        return
    context.user_data.clear()
    await update.message.reply_text(
        "به ربات مدیریت پیگیری دانش‌آموزان خوش آمدید.\nرشته موردنظر را انتخاب کنید:",
        reply_markup=root_menu_keyboard(),
    )


async def cmd_export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _check_access(update.effective_user.id):
        await _deny(update)
        return
    await _send_export(update.effective_chat.id, context)


async def cmd_reload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _check_access(update.effective_user.id):
        await _deny(update)
        return
    _store(context).reload()
    await update.message.reply_text("✅ فایل اکسل مجدداً بارگذاری شد.")


async def cmd_reset_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _check_access(update.effective_user.id):
        await _deny(update)
        return
    context.bot_data["state_store"].clear()
    _store(context).reload()
    await update.message.reply_text("✅ همه وضعیت‌های ثبت‌شده پاک شد.")


async def _send_export(chat_id, context: ContextTypes.DEFAULT_TYPE):
    store = _store(context)
    path = store.export()
    try:
        with open(path, "rb") as f:
            await context.bot.send_document(
                chat_id=chat_id,
                document=f,
                filename=os.path.basename(path),
                caption="📤 فایل خروجی اکسل با آخرین تغییرات",
            )
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not _check_access(update.effective_user.id):
        await _deny(update)
        return

    data = query.data

    if data == "noop":
        await query.answer()
        return

    if data == "menu:root":
        context.user_data.clear()
        await query.answer()
        await query.edit_message_text(
            "رشته موردنظر را انتخاب کنید:", reply_markup=root_menu_keyboard()
        )
        return

    if data.startswith("menu:"):
        sheet_key = data.split(":")[1]
        context.user_data["sheet"] = sheet_key
        context.user_data["page"] = 0
        context.user_data["query"] = None
        await query.answer()
        text, keyboard = _render(context)
        await query.edit_message_text(text, reply_markup=keyboard)
        return

    if data.startswith("nav:"):
        action = data.split(":")[1]
        store = _store(context)
        sheet_key = context.user_data.get("sheet")
        search_query = context.user_data.get("query")
        all_records = store.search(sheet_key, search_query) if search_query else store.get_records(sheet_key)
        total_pages = max(1, -(-len(all_records) // config.PAGE_SIZE))
        page = context.user_data.get("page", 0)
        if action == "prev":
            page = max(0, page - 1)
        elif action == "next":
            page = min(total_pages - 1, page + 1)
        elif action == "first":
            page = 0
        elif action == "last":
            page = total_pages - 1
        context.user_data["page"] = page
        await query.answer()
        text, keyboard = _render(context)
        await query.edit_message_text(text, reply_markup=keyboard)
        return

    if data.startswith("tg:"):
        _, sheet_key, row_s, field = data.split(":")
        row = int(row_s)
        store = _store(context)
        if field == "p":
            store.toggle_phone_status(sheet_key, row)
        else:
            store.toggle_attendance_status(sheet_key, row)
        await query.answer()
        text, keyboard = _render(context)
        await query.edit_message_text(text, reply_markup=keyboard)
        return

    if data == "search:start":
        context.user_data["awaiting_search"] = True
        await query.answer()
        await query.edit_message_text(
            "🔎 نام یا شماره تلفن موردنظر برای جستجو را ارسال کنید:",
            reply_markup=search_prompt_keyboard(),
        )
        return

    if data == "search:cancel":
        context.user_data["awaiting_search"] = False
        await query.answer()
        text, keyboard = _render(context)
        await query.edit_message_text(text, reply_markup=keyboard)
        return

    if data == "search:clear":
        context.user_data["query"] = None
        context.user_data["page"] = 0
        await query.answer()
        text, keyboard = _render(context)
        await query.edit_message_text(text, reply_markup=keyboard)
        return

    if data == "export":
        await query.answer("در حال آماده‌سازی فایل خروجی...")
        await _send_export(update.effective_chat.id, context)
        return

    await query.answer()


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _check_access(update.effective_user.id):
        await _deny(update)
        return

    if not context.user_data.get("awaiting_search"):
        return

    if not context.user_data.get("sheet"):
        await update.message.reply_text(
            "ابتدا یک رشته را انتخاب کنید:", reply_markup=root_menu_keyboard()
        )
        return

    context.user_data["awaiting_search"] = False
    context.user_data["query"] = update.message.text.strip()
    context.user_data["page"] = 0
    text, keyboard = _render(context)
    await update.message.reply_text(text, reply_markup=keyboard)
