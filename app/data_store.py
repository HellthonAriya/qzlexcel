import os
import re
import time

from app import excel_data
from app.excel_data import Status


def compute_stats(records):
    phone = {s: 0 for s in Status}
    attendance = {s: 0 for s in Status}
    for rec in records:
        phone[rec.phone_status] += 1
        attendance[rec.attendance_status] += 1
    return {"phone": phone, "attendance": attendance, "total": len(records)}


class DataStore:
    def __init__(self, excel_path, state_store, tmp_dir):
        self.excel_path = excel_path
        self.state_store = state_store
        self.tmp_dir = tmp_dir
        os.makedirs(tmp_dir, exist_ok=True)
        self.records_by_sheet = {}
        self.sheet_labels = {}
        self.reload()

    def reload(self):
        operator_col = self.state_store.get_config("operator_column_override")
        records_by_sheet, sheet_labels = excel_data.load_workbook_records(
            self.excel_path, operator_col_letter=operator_col
        )
        overrides = self.state_store.load_all()
        for key, records in records_by_sheet.items():
            for row, rec in records.items():
                override = overrides.get((key, row))
                if not override:
                    continue
                phone_status, attendance_status = override
                if phone_status:
                    rec.phone_status = Status[phone_status]
                if attendance_status:
                    rec.attendance_status = Status[attendance_status]
        self.records_by_sheet = records_by_sheet
        self.sheet_labels = sheet_labels

    def sheet_items(self):
        return list(self.sheet_labels.items())

    def sheet_label(self, sheet_key):
        return self.sheet_labels.get(sheet_key, sheet_key)

    def get_records(self, sheet_key):
        return list(self.records_by_sheet.get(sheet_key, {}).values())

    def get_record(self, sheet_key, row):
        return self.records_by_sheet.get(sheet_key, {}).get(row)

    def toggle_phone_status(self, sheet_key, row):
        rec = self.get_record(sheet_key, row)
        if not rec:
            return None
        rec.phone_status = excel_data.next_status(rec.phone_status)
        self.state_store.set_status(sheet_key, row, phone_status=rec.phone_status.name)
        return rec

    def toggle_attendance_status(self, sheet_key, row):
        rec = self.get_record(sheet_key, row)
        if not rec:
            return None
        rec.attendance_status = excel_data.next_status(rec.attendance_status)
        self.state_store.set_status(sheet_key, row, attendance_status=rec.attendance_status.name)
        return rec

    @staticmethod
    def _matches(rec, query, qdigits):
        name = str(rec.full_name or "")
        if query in name:
            return True
        if qdigits:
            phones = (rec.home_phone, rec.student_phone, rec.mother_phone, rec.father_phone)
            if any(phone is not None and qdigits in re.sub(r"\D", "", str(phone)) for phone in phones):
                return True
        return False

    def search(self, sheet_key, query):
        query = (query or "").strip()
        if not query:
            return self.get_records(sheet_key)
        qdigits = re.sub(r"\D", "", query)
        return [rec for rec in self.get_records(sheet_key) if self._matches(rec, query, qdigits)]

    def search_all(self, query):
        query = (query or "").strip()
        if not query:
            return []
        qdigits = re.sub(r"\D", "", query)
        results = []
        for key in self.sheet_labels:
            results.extend(rec for rec in self.get_records(key) if self._matches(rec, query, qdigits))
        return results

    def get_operator_column_override(self):
        return self.state_store.get_config("operator_column_override")

    def set_operator_column_override(self, letter):
        self.state_store.set_config("operator_column_override", letter.upper() if letter else None)
        self.reload()

    def list_operators(self):
        seen = set()
        result = []
        for key in self.sheet_labels:
            for rec in self.get_records(key):
                if rec.operator and rec.operator not in seen:
                    seen.add(rec.operator)
                    result.append(rec.operator)
        result.sort()
        return result

    def stats(self, sheet_key):
        return compute_stats(self.get_records(sheet_key))

    def stats_all(self):
        return {key: compute_stats(records.values()) for key, records in self.records_by_sheet.items()}

    def export(self):
        out_path = os.path.join(self.tmp_dir, f"export_{int(time.time())}.xlsx")
        return excel_data.export_workbook(
            self.excel_path, self.records_by_sheet, self.sheet_labels, out_path
        )
