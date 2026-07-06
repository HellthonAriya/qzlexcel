import math

from telegram import CopyTextButton, InlineKeyboardButton, InlineKeyboardMarkup

from app.excel_data import (
    ATTEND_STATUS_TEXT,
    PHONE_STATUS_TEXT,
    SHEET_LABELS,
    STATUS_ICON,
    format_phone,
)


def root_menu_keyboard():
    rows = [
        [InlineKeyboardButton("📗 انسانی", callback_data="menu:h")],
        [InlineKeyboardButton("📘 تجربی", callback_data="menu:e")],
        [InlineKeyboardButton("📙 ریاضی", callback_data="menu:m")],
        [InlineKeyboardButton("📤 خروجی کامل اکسل", callback_data="export")],
    ]
    return InlineKeyboardMarkup(rows)


def _display_status(text_map, status):
    label = text_map[status] or "ثبت نشده"
    return f"{STATUS_ICON[status]} {label}"


def page_text(sheet_key, page_records, total_count, page, page_size, query=None):
    lines = [f"📚 رشته: {SHEET_LABELS[sheet_key]}"]
    if query:
        lines.append(f"🔎 جستجو: «{query}»")

    if not page_records:
        lines.append("📄 نتیجه‌ای یافت نشد.")
        return "\n".join(lines)

    first_redif = page_records[0].redif
    last_redif = page_records[-1].redif
    lines.append(f"📄 نمایش ردیف {first_redif} تا {last_redif} (از {total_count} مورد)")
    lines.append("━━━━━━━━━━━━━━")

    start_index = page * page_size
    for i, rec in enumerate(page_records, start=start_index + 1):
        lines.append(f"{i}) ردیف {rec.redif} — {rec.full_name or 'نامشخص'}")
        info_parts = []
        if rec.grade:
            info_parts.append(f"مقطع: {rec.grade}")
        if rec.service_type:
            info_parts.append(f"نوع خدمات: {rec.service_type}")
        if info_parts:
            lines.append(" | ".join(info_parts))
        phone_disp = _display_status(PHONE_STATUS_TEXT, rec.phone_status)
        attend_disp = _display_status(ATTEND_STATUS_TEXT, rec.attendance_status)
        lines.append(f"📞 پاسخگویی: {phone_disp}  |  👥 حضور: {attend_disp}")
        lines.append("━━━━━━━━━━━━━━")

    return "\n".join(lines)


def _short_name(name, limit=28):
    name = str(name or "نامشخص")
    return name if len(name) <= limit else name[: limit - 1] + "…"


def page_keyboard(sheet_key, page_records, page, total_count, page_size, in_search):
    rows = []
    total_pages = max(1, math.ceil(total_count / page_size))

    for idx, rec in enumerate(page_records):
        if idx > 0:
            rows.append([InlineKeyboardButton("➖➖➖➖➖", callback_data="noop")])

        rows.append(
            [
                InlineKeyboardButton(
                    f"👤 ردیف {rec.redif} — {_short_name(rec.full_name)}",
                    callback_data="noop",
                )
            ]
        )

        phone_row = []
        if rec.student_phone:
            phone = format_phone(rec.student_phone)
            label = ("🔵 " if rec.highlight_student else "☎️ ") + "خودش"
            phone_row.append(InlineKeyboardButton(label, copy_text=CopyTextButton(text=phone)))
        if rec.mother_phone:
            phone = format_phone(rec.mother_phone)
            label = ("🔵 " if rec.highlight_mother else "👩 ") + "مادر"
            phone_row.append(InlineKeyboardButton(label, copy_text=CopyTextButton(text=phone)))
        if rec.father_phone:
            phone = format_phone(rec.father_phone)
            label = ("🔵 " if rec.highlight_father else "👨 ") + "پدر"
            phone_row.append(InlineKeyboardButton(label, copy_text=CopyTextButton(text=phone)))
        if phone_row:
            rows.append(phone_row)

        rows.append(
            [
                InlineKeyboardButton(
                    f"پاسخگویی {STATUS_ICON[rec.phone_status]}",
                    callback_data=f"tg:{sheet_key}:{rec.row}:p",
                ),
                InlineKeyboardButton(
                    f"حضور {STATUS_ICON[rec.attendance_status]}",
                    callback_data=f"tg:{sheet_key}:{rec.row}:a",
                ),
            ]
        )

    if page_records:
        rows.append(
            [
                InlineKeyboardButton("⏮", callback_data="nav:first"),
                InlineKeyboardButton("◀️", callback_data="nav:prev"),
                InlineKeyboardButton(f"صفحه {page + 1}/{total_pages}", callback_data="noop"),
                InlineKeyboardButton("▶️", callback_data="nav:next"),
                InlineKeyboardButton("⏭", callback_data="nav:last"),
            ]
        )

    bottom_row = [InlineKeyboardButton("🔎 جستجو", callback_data="search:start")]
    if in_search:
        bottom_row.append(InlineKeyboardButton("✖️ حذف فیلتر", callback_data="search:clear"))
    bottom_row.append(InlineKeyboardButton("📤 خروجی اکسل", callback_data="export"))
    rows.append(bottom_row)
    rows.append([InlineKeyboardButton("🏠 انتخاب رشته", callback_data="menu:root")])

    return InlineKeyboardMarkup(rows)


def search_prompt_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("✖️ انصراف", callback_data="search:cancel")]])


def confirm_replace_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ بله، جایگزین کن", callback_data="loadxlsx:confirm"),
                InlineKeyboardButton("❌ انصراف", callback_data="loadxlsx:cancel"),
            ]
        ]
    )
