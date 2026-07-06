import logging
import os
import re
import time

from telegram import Update
from telegram.ext import ContextTypes

from app import config, excel_data
from app.data_store import DataStore
from app.keyboards import (
    COLUMN_FIELD_LABELS,
    col_prompt_keyboard,
    confirm_replace_keyboard,
    full_stats_text,
    page_keyboard,
    page_text,
    root_menu_keyboard,
    search_prompt_keyboard,
    settings_keyboard,
    stats_back_keyboard,
)

logger = logging.getLogger(__name__)

NO_FILE_MESSAGE = (
    "⚠️ هنوز هیچ فایل اکسلی ثبت نشده است.\n"
    "فایل اکسل موردنظر (فرمت xlsx) را همین‌جا برای ربات ارسال کنید تا ثبت شود."
)


def _store(context: ContextTypes.DEFAULT_TYPE):
    return context.bot_data.get("store")


async def _deny(update: Update):
    if update.callback_query:
        await update.callback_query.answer("⛔️ شما اجازه دسترسی به این ربات را ندارید.", show_alert=True)
    elif update.message:
        await update.message.reply_text("⛔️ شما اجازه دسترسی به این ربات را ندارید.")


def _check_access(user_id: int) -> bool:
    return config.is_allowed(user_id)


def _ensure_operator_loaded(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    if "selected_operator" not in context.user_data:
        state_store = context.bot_data.get("state_store")
        context.user_data["selected_operator"] = state_store.get_selected_operator(user_id) if state_store else None


def _settings_view(store, context: ContextTypes.DEFAULT_TYPE):
    operators = store.list_operators()
    context.user_data["operator_choices"] = operators
    selected = context.user_data.get("selected_operator")
    col_overrides = store.get_column_overrides()
    text = "⚙️ تنظیمات\nنام ادمین (اپراتور) خودتان را انتخاب کنید تا موارد مربوط به شما در لیست‌ها با رنگ آبی مشخص شود:"
    if selected:
        text = f"⚙️ تنظیمات\nادمین انتخاب‌شده: «{selected}»\n\n" + text
    keyboard = settings_keyboard(operators, selected, col_overrides)
    return text, keyboard


def _render(context: ContextTypes.DEFAULT_TYPE):
    store = _store(context)
    view = context.user_data
    page = view.get("page", 0)
    query = view.get("query")
    selected_operator = view.get("selected_operator")

    if view.get("global"):
        all_records = store.search_all(query)
        total = len(all_records)
        start = page * config.PAGE_SIZE
        page_records = all_records[start : start + config.PAGE_SIZE]
        text = page_text(
            page_records, total, page, config.PAGE_SIZE, query, sheet_labels=dict(store.sheet_items())
        )
        keyboard = page_keyboard(
            page_records, page, total, config.PAGE_SIZE, True, mode="global", selected_operator=selected_operator
        )
        return text, keyboard

    sheet_key = view.get("sheet")
    all_records = store.search(sheet_key, query) if query else store.get_records(sheet_key)
    total = len(all_records)
    start = page * config.PAGE_SIZE
    page_records = all_records[start : start + config.PAGE_SIZE]
    sheet_stats = store.stats(sheet_key)
    sheet_name = store.sheet_label(sheet_key)

    text = page_text(page_records, total, page, config.PAGE_SIZE, query, sheet_stats, sheet_name=sheet_name)
    keyboard = page_keyboard(
        page_records, page, total, config.PAGE_SIZE, bool(query), selected_operator=selected_operator
    )
    return text, keyboard


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _check_access(update.effective_user.id):
        await _deny(update)
        return
    user_id = update.effective_user.id
    context.user_data.clear()
    _ensure_operator_loaded(context, user_id)
    store = _store(context)
    if store is None:
        await update.message.reply_text(NO_FILE_MESSAGE)
        return
    await update.message.reply_text(
        "به ربات مدیریت پیگیری دانش‌آموزان خوش آمدید.\nرشته موردنظر را انتخاب کنید:",
        reply_markup=root_menu_keyboard(store.sheet_items()),
    )


async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _check_access(update.effective_user.id):
        await _deny(update)
        return
    _ensure_operator_loaded(context, update.effective_user.id)
    store = _store(context)
    if store is None:
        await update.message.reply_text(NO_FILE_MESSAGE)
        return
    text, keyboard = _settings_view(store, context)
    await update.message.reply_text(text, reply_markup=keyboard)


async def cmd_export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _check_access(update.effective_user.id):
        await _deny(update)
        return
    if _store(context) is None:
        await update.message.reply_text(NO_FILE_MESSAGE)
        return
    await _send_export(update.effective_chat.id, context)


async def cmd_reload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _check_access(update.effective_user.id):
        await _deny(update)
        return
    store = _store(context)
    if store is None:
        if os.path.exists(config.EXCEL_PATH):
            context.bot_data["store"] = DataStore(
                config.EXCEL_PATH, context.bot_data["state_store"], config.TMP_DIR
            )
            await update.message.reply_text("✅ فایل اکسل بارگذاری شد.")
        else:
            await update.message.reply_text(NO_FILE_MESSAGE)
        return
    store.reload()
    await update.message.reply_text("✅ فایل اکسل مجدداً بارگذاری شد.")


async def cmd_reset_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _check_access(update.effective_user.id):
        await _deny(update)
        return
    context.bot_data["state_store"].clear()
    store = _store(context)
    if store is not None:
        store.reload()
    await update.message.reply_text("✅ همه وضعیت‌های ثبت‌شده پاک شد.")


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _check_access(update.effective_user.id):
        await _deny(update)
        return
    store = _store(context)
    if store is None:
        await update.message.reply_text(NO_FILE_MESSAGE)
        return
    text = full_stats_text(store.stats_all(), store.sheet_items())
    has_list = bool(context.user_data.get("sheet")) or bool(context.user_data.get("global"))
    keyboard = stats_back_keyboard(has_list)
    await update.message.reply_text(text, reply_markup=keyboard)


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


def _discard_pending_upload(context: ContextTypes.DEFAULT_TYPE):
    pending = context.user_data.pop("pending_excel_path", None)
    if pending and os.path.exists(pending):
        try:
            os.remove(pending)
        except OSError:
            pass


async def on_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _check_access(update.effective_user.id):
        await _deny(update)
        return

    document = update.message.document
    if document is None:
        return

    filename = document.file_name or ""
    is_xlsx = filename.lower().endswith(".xlsx") or document.mime_type == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    if not is_xlsx:
        await update.message.reply_text("فقط فایل اکسل با فرمت xlsx پذیرفته می‌شود.")
        return

    os.makedirs(config.TMP_DIR, exist_ok=True)
    tmp_path = os.path.join(
        config.TMP_DIR, f"upload_{update.effective_user.id}_{int(time.time())}.xlsx"
    )
    tg_file = await context.bot.get_file(document.file_id)
    await tg_file.download_to_drive(tmp_path)

    state_store = context.bot_data["state_store"]
    col_overrides = {
        field: state_store.get_config(f"{field}_column_override") for field in excel_data.OVERRIDABLE_FIELDS
    }
    try:
        records, sheet_labels = excel_data.load_workbook_records(tmp_path, col_overrides=col_overrides)
    except Exception:
        os.remove(tmp_path)
        await update.message.reply_text("❌ این فایل اکسل قابل خواندن نیست یا فرمت آن معتبر نیست.")
        return

    if not sheet_labels:
        os.remove(tmp_path)
        await update.message.reply_text(
            "❌ هیچ شیتی با ستون نام یا ردیف در این فایل پیدا نشد؛ فرمت فایل را بررسی کنید."
        )
        return

    _discard_pending_upload(context)
    context.user_data["pending_excel_path"] = tmp_path

    counts = {sheet_labels[key]: len(records[key]) for key in sheet_labels}
    total = sum(counts.values())
    lines = ["📥 فایل اکسل دریافت شد.", "شیت‌های شناسایی‌شده:"]
    for label, count in counts.items():
        lines.append(f"- {label}: {count} ردیف")
    lines.append(f"جمع کل: {total}")
    lines.append("")
    lines.append(
        "⚠️ با تأیید، این فایل جایگزین فایل فعلی می‌شود و همه‌ی وضعیت‌های ثبت‌شده تا این لحظه پاک خواهد شد. ادامه می‌دهید؟"
    )
    await update.message.reply_text("\n".join(lines), reply_markup=confirm_replace_keyboard())


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not _check_access(update.effective_user.id):
        await _deny(update)
        return
    _ensure_operator_loaded(context, update.effective_user.id)

    data = query.data

    if data == "noop":
        await query.answer()
        return

    if data == "loadxlsx:confirm":
        pending = context.user_data.pop("pending_excel_path", None)
        if not pending or not os.path.exists(pending):
            await query.answer()
            await query.edit_message_text("⚠️ فایل موردنظر دیگر در دسترس نیست. دوباره ارسال کنید.")
            return
        os.makedirs(os.path.dirname(config.EXCEL_PATH) or ".", exist_ok=True)
        os.replace(pending, config.EXCEL_PATH)
        state_store = context.bot_data["state_store"]
        state_store.clear()
        context.bot_data["store"] = DataStore(config.EXCEL_PATH, state_store, config.TMP_DIR)
        await query.answer("فایل جایگزین شد.")
        await query.edit_message_text(
            "✅ فایل اکسل با موفقیت ثبت شد. برای شروع /start را بزنید."
        )
        return

    if data == "loadxlsx:cancel":
        _discard_pending_upload(context)
        await query.answer()
        await query.edit_message_text("❌ لغو شد.")
        return

    if data == "menu:root":
        context.user_data.clear()
        store = _store(context)
        await query.answer()
        if store is None:
            await query.edit_message_text(NO_FILE_MESSAGE)
        else:
            await query.edit_message_text(
                "رشته موردنظر را انتخاب کنید:", reply_markup=root_menu_keyboard(store.sheet_items())
            )
        return

    if _store(context) is None:
        await query.answer(NO_FILE_MESSAGE, show_alert=True)
        return

    if data == "settings:open":
        store = _store(context)
        await query.answer()
        text, keyboard = _settings_view(store, context)
        await query.edit_message_text(text, reply_markup=keyboard)
        return

    if data.startswith("settings:op:"):
        idx = int(data.split(":")[2])
        choices = context.user_data.get("operator_choices") or []
        if idx < 0 or idx >= len(choices):
            await query.answer("این گزینه دیگر معتبر نیست.", show_alert=True)
            return
        operator = choices[idx]
        context.user_data["selected_operator"] = operator
        context.bot_data["state_store"].set_selected_operator(update.effective_user.id, operator)
        await query.answer(f"ادمین «{operator}» انتخاب شد.")
        text, keyboard = _settings_view(_store(context), context)
        await query.edit_message_text(text, reply_markup=keyboard)
        return

    if data == "settings:clear":
        context.user_data["selected_operator"] = None
        context.bot_data["state_store"].set_selected_operator(update.effective_user.id, None)
        await query.answer("انتخاب پاک شد.")
        text, keyboard = _settings_view(_store(context), context)
        await query.edit_message_text(text, reply_markup=keyboard)
        return

    if data.startswith("settings:col:"):
        _, _, field, action = data.split(":")
        if action == "start":
            context.user_data["awaiting_col_field"] = field
            await query.answer()
            label = COLUMN_FIELD_LABELS.get(field, field)
            await query.edit_message_text(
                f"🔧 حرف ستون «{label}» را بفرستید (مثلاً A یا B).\n"
                "برای بازگشت به تشخیص خودکار بر اساس نام هدر، عبارت «خودکار» را بفرستید.",
                reply_markup=col_prompt_keyboard(field),
            )
            return
        if action == "cancel":
            context.user_data["awaiting_col_field"] = None
            await query.answer()
            text, keyboard = _settings_view(_store(context), context)
            await query.edit_message_text(text, reply_markup=keyboard)
            return

    if data == "stats":
        store = _store(context)
        await query.answer()
        text = full_stats_text(store.stats_all(), store.sheet_items())
        has_list = bool(context.user_data.get("sheet")) or bool(context.user_data.get("global"))
        keyboard = stats_back_keyboard(has_list)
        await query.edit_message_text(text, reply_markup=keyboard)
        return

    if data == "stats:back":
        await query.answer()
        if context.user_data.get("sheet") or context.user_data.get("global"):
            text, keyboard = _render(context)
        else:
            store = _store(context)
            text, keyboard = "رشته موردنظر را انتخاب کنید:", root_menu_keyboard(store.sheet_items())
        await query.edit_message_text(text, reply_markup=keyboard)
        return

    if data.startswith("menu:"):
        sheet_key = data.split(":")[1]
        context.user_data["sheet"] = sheet_key
        context.user_data["page"] = 0
        context.user_data["query"] = None
        context.user_data["global"] = False
        await query.answer()
        text, keyboard = _render(context)
        await query.edit_message_text(text, reply_markup=keyboard)
        return

    if data.startswith("nav:"):
        action = data.split(":")[1]
        store = _store(context)
        if context.user_data.get("global"):
            all_records = store.search_all(context.user_data.get("query"))
        else:
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
        context.user_data["search_scope"] = "sheet"
        await query.answer()
        await query.edit_message_text(
            "🔎 نام یا شماره تلفن موردنظر برای جستجو را ارسال کنید:",
            reply_markup=search_prompt_keyboard(),
        )
        return

    if data == "search:global:start":
        context.user_data["awaiting_search"] = True
        context.user_data["search_scope"] = "global"
        context.user_data["global"] = True
        await query.answer()
        await query.edit_message_text(
            "🔎 نام یا شماره تلفن موردنظر را برای جستجو در همه‌ی شیت‌ها ارسال کنید:",
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

    if data == "search:global:clear":
        store = _store(context)
        context.user_data.clear()
        await query.answer()
        await query.edit_message_text(
            "رشته موردنظر را انتخاب کنید:", reply_markup=root_menu_keyboard(store.sheet_items())
        )
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
    _ensure_operator_loaded(context, update.effective_user.id)

    awaiting_field = context.user_data.get("awaiting_col_field")
    if awaiting_field:
        context.user_data["awaiting_col_field"] = None
        store = _store(context)
        if store is None:
            await update.message.reply_text(NO_FILE_MESSAGE)
            return
        label = COLUMN_FIELD_LABELS.get(awaiting_field, awaiting_field)
        text_in = update.message.text.strip()
        if text_in in ("خودکار", "auto", "0"):
            store.set_column_override(awaiting_field, None)
            await update.message.reply_text(f"↩️ ستون «{label}» به تشخیص خودکار بازگشت و فایل مجدداً خوانده شد.")
        elif re.fullmatch(r"[A-Za-z]{1,2}", text_in):
            store.set_column_override(awaiting_field, text_in)
            await update.message.reply_text(
                f"✅ ستون {text_in.upper()} برای «{label}» تنظیم شد و فایل مجدداً خوانده شد."
            )
        else:
            await update.message.reply_text(
                "❌ ورودی نامعتبر است. یک حرف ستون مثل A یا B بفرستید، یا «خودکار» برای بازگشت به تشخیص خودکار."
            )
            return
        text, keyboard = _settings_view(store, context)
        await update.message.reply_text(text, reply_markup=keyboard)
        return

    if not context.user_data.get("awaiting_search"):
        return

    store = _store(context)
    if store is None:
        await update.message.reply_text(NO_FILE_MESSAGE)
        return

    if context.user_data.get("search_scope") == "global":
        context.user_data["awaiting_search"] = False
        context.user_data["global"] = True
        context.user_data["query"] = update.message.text.strip()
        context.user_data["page"] = 0
        text, keyboard = _render(context)
        await update.message.reply_text(text, reply_markup=keyboard)
        return

    if not context.user_data.get("sheet"):
        await update.message.reply_text(
            "ابتدا یک رشته را انتخاب کنید:", reply_markup=root_menu_keyboard(store.sheet_items())
        )
        return

    context.user_data["awaiting_search"] = False
    context.user_data["query"] = update.message.text.strip()
    context.user_data["page"] = 0
    text, keyboard = _render(context)
    await update.message.reply_text(text, reply_markup=keyboard)
