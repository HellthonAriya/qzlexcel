import math

from telegram import CopyTextButton, InlineKeyboardButton, InlineKeyboardMarkup

from app.excel_data import (
    ATTEND_STATUS_TEXT,
    PHONE_STATUS_TEXT,
    STATUS_ICON,
    Status,
    format_phone,
    sheet_emoji,
)


def root_menu_keyboard(sheet_items):
    rows = []
    for idx, (key, name) in enumerate(sheet_items):
        rows.append([InlineKeyboardButton(f"{sheet_emoji(idx)} {name}", callback_data=f"menu:{key}")])
    rows.append([InlineKeyboardButton("📊 آمار کلی", callback_data="stats")])
    rows.append([InlineKeyboardButton("📤 خروجی کامل اکسل", callback_data="export")])
    return InlineKeyboardMarkup(rows)


def _display_status(text_map, status):
    label = text_map[status] or "ثبت نشده"
    return f"{STATUS_ICON[status]} {label}"


def _redif_prefix(redif):
    return f"ردیف {redif} — " if redif is not None else ""


def _stats_line(stats):
    p = stats["phone"]
    a = stats["attendance"]
    return (
        f"📞 پاسخگویی: ✅ {p[Status.CHECK]}  ❌ {p[Status.CROSS]}  🔶 {p[Status.OTHER]}  ⬜ {p[Status.EMPTY]}\n"
        f"👥 حضور: ✅ {a[Status.CHECK]}  ❌ {a[Status.CROSS]}  🔶 {a[Status.OTHER]}  ⬜ {a[Status.EMPTY]}"
    )


def full_stats_text(stats_by_sheet, sheet_items):
    lines = ["📊 آمار کلی", "━━━━━━━━━━━━━━━━━━━━━━"]
    grand_phone = {s: 0 for s in Status}
    grand_attendance = {s: 0 for s in Status}
    grand_total = 0

    for idx, (key, name) in enumerate(sheet_items):
        stats = stats_by_sheet.get(key)
        if not stats:
            continue
        lines.append(f"{sheet_emoji(idx)} {name} ({stats['total']} نفر)")
        lines.append(_stats_line(stats))
        lines.append("")
        for s in Status:
            grand_phone[s] += stats["phone"][s]
            grand_attendance[s] += stats["attendance"][s]
        grand_total += stats["total"]

    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"جمع کل ({grand_total} نفر)")
    lines.append(_stats_line({"phone": grand_phone, "attendance": grand_attendance, "total": grand_total}))
    return "\n".join(lines)


def page_text(sheet_key, sheet_name, page_records, total_count, page, page_size, query=None, sheet_stats=None):
    lines = [f"📚 رشته: {sheet_name}"]
    if query:
        lines.append(f"🔎 جستجو: «{query}»")
    if sheet_stats:
        lines.append(_stats_line(sheet_stats))

    if not page_records:
        lines.append("📄 نتیجه‌ای یافت نشد.")
        return "\n".join(lines)

    first_redif = page_records[0].redif
    last_redif = page_records[-1].redif
    if first_redif is not None and last_redif is not None:
        lines.append(f"📄 نمایش ردیف {first_redif} تا {last_redif} (از {total_count} مورد)")
    else:
        lines.append(f"📄 نمایش {len(page_records)} مورد (از {total_count} مورد)")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    start_index = page * page_size
    for i, rec in enumerate(page_records, start=start_index + 1):
        hidden_note = " 🔴 (مخفی)" if rec.hidden else ""
        lines.append(f"{i}) {_redif_prefix(rec.redif)}{rec.full_name or 'نامشخص'}{hidden_note}")
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
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    return "\n".join(lines)


def _short_name(name, limit=28):
    name = str(name or "نامشخص")
    return name if len(name) <= limit else name[: limit - 1] + "…"


def page_keyboard(sheet_key, page_records, page, total_count, page_size, in_search):
    rows = []
    total_pages = max(1, math.ceil(total_count / page_size))

    for idx, rec in enumerate(page_records):
        if idx > 0:
            rows.append([InlineKeyboardButton("➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖", callback_data="noop")])

        style = "danger" if rec.hidden else None
        name_label = f"👤 {_redif_prefix(rec.redif)}{_short_name(rec.full_name)}"
        if rec.hidden:
            name_label += " 🔴"
        rows.append([InlineKeyboardButton(name_label, callback_data="noop", style=style)])

        phone_row = []
        student_phone = format_phone(rec.student_phone)
        if student_phone:
            label = ("🔵 " if rec.highlight_student else "☎️ ") + "خودش"
            phone_row.append(
                InlineKeyboardButton(label, copy_text=CopyTextButton(text=student_phone), style=style)
            )
        mother_phone = format_phone(rec.mother_phone)
        if mother_phone:
            label = ("🔵 " if rec.highlight_mother else "👩 ") + "مادر"
            phone_row.append(
                InlineKeyboardButton(label, copy_text=CopyTextButton(text=mother_phone), style=style)
            )
        father_phone = format_phone(rec.father_phone)
        if father_phone:
            label = ("🔵 " if rec.highlight_father else "👨 ") + "پدر"
            phone_row.append(
                InlineKeyboardButton(label, copy_text=CopyTextButton(text=father_phone), style=style)
            )
        if phone_row:
            rows.append(phone_row)

        rows.append(
            [
                InlineKeyboardButton(
                    f"پاسخگویی {STATUS_ICON[rec.phone_status]}",
                    callback_data=f"tg:{sheet_key}:{rec.row}:p",
                    style=style,
                ),
                InlineKeyboardButton(
                    f"حضور {STATUS_ICON[rec.attendance_status]}",
                    callback_data=f"tg:{sheet_key}:{rec.row}:a",
                    style=style,
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
    rows.append(bottom_row)
    rows.append(
        [
            InlineKeyboardButton("📊 آمار کلی", callback_data="stats"),
            InlineKeyboardButton("📤 خروجی اکسل", callback_data="export"),
        ]
    )
    rows.append([InlineKeyboardButton("🏠 انتخاب رشته", callback_data="menu:root")])

    return InlineKeyboardMarkup(rows)


def stats_back_keyboard(has_sheet):
    rows = []
    if has_sheet:
        rows.append([InlineKeyboardButton("🔙 بازگشت به لیست", callback_data="stats:back")])
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
