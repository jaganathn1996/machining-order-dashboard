"""Create, load, validate, and save the part machining order workbook."""

from __future__ import annotations

from datetime import date, timedelta
from io import BytesIO
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from parts import PARTS, ensure_part_photos

PHOTO_BY_PART = {part["number"]: part["file"] for part in PARTS}

SHEET_NAME = "Orders"
EDITOR_COLUMNS = [
    "APM NO",
    "PO Date",
    "PO Number",
    "Part Number",
    "Part Photo",
    "Qty",
    "Dispatch Date",
    "Specification",
    "Risk",
    "RM Size",
    "Action Qty",
    "RM Status",
    "Process",
    "Tools & Accessories",
    "Special Process & Instruments",
    "Inserts",
    "Enquiry",
    "Program Status",
    "Planning",
    "Machining Status",
    "Review",
    "Deviation",
    "Customer",
    "Completed Status",
    "RMA Status",
    "Is Aerospace Order",
]
TEXT_COLUMNS = [
    column
    for column in EDITOR_COLUMNS
    if column not in {"PO Date", "Dispatch Date", "Qty", "Action Qty"}
]
DATE_COLUMNS = ["PO Date", "Dispatch Date"]
COUNT_COLUMNS = ["Qty", "Action Qty"]
RISKS = ["High", "Medium", "Low"]
PROGRAM_STATUSES = ["Completed", "Incomplete", "NA"]
PLANNING_OPTIONS = [
    "In-house",
    "In-house completed",
    "Out",
    "Out completed",
    "Turning in-house",
    "Turning in-house completed",
    "Turning out",
    "Turning out completed",
    "Milling in-house",
    "Milling in-house completed",
    "Milling out",
    "Milling out completed",
]
COMPLETED_STATUSES = ["Not started", "In progress", "Completed", "On hold"]
YES_NO = ["Yes", "No"]
COMPLETED_COLORS = {
    "Not started": "#4C78A8",
    "In progress": "#F58518",
    "Completed": "#54A24B",
    "On hold": "#E45756",
}
RISK_COLORS = {"High": "#E45756", "Medium": "#F58518", "Low": "#4C78A8"}
AEROSPACE_BLUE = "D6EAF8"

ROOT = Path(__file__).resolve().parent
DEFAULT_WORKBOOK = ROOT / "data" / "part_machining_orders.xlsx"
CUSTOMERS = [
    "Apex Aerospace",
    "Northline Auto",
    "Harbor Medical",
    "Vertex Robotics",
    "Summit Energy",
    "Precision Rail",
]


def _planning(process: str, done: bool, outside: bool) -> str:
    turning = "Turning" in process
    milling = "Milling" in process
    if turning and not milling:
        label = "Turning out" if outside else "Turning in-house"
    elif milling and not turning:
        label = "Milling out" if outside else "Milling in-house"
    else:
        label = "Out" if outside else "In-house"
    return f"{label} completed" if done else label


def build_sample(today: date | None = None) -> pd.DataFrame:
    """Build a stable sample of shop orders using the shop column list."""
    ensure_part_photos()
    today = today or date.today()
    enquiries = [
        "None",
        "None",
        "Confirm datum B on revision D",
        "None",
        "Customer asked for a material cert with the shipment",
        "None",
    ]
    reviews = [
        "",
        "First article accepted",
        "",
        "Hold shipment until the CMM report is attached",
        "",
        "Tool wear noted on the last two pieces",
    ]
    reject_rows = {6, 14, 20}
    rma_rows = {3, 10, 16}
    completed_rows = {0, 2, 5, 8, 11, 13, 17, 19}
    hold_rows = {22, 23}
    not_started_rows = {1, 4, 7}
    rows = []
    for index in range(24):
        part = PARTS[index % len(PARTS)]
        po_date = date(2026, 6, 2) + timedelta(days=index * 4)
        if index in completed_rows:
            completed = "Completed"
        elif index in hold_rows:
            completed = "On hold"
        elif index in not_started_rows:
            completed = "Not started"
        else:
            completed = "In progress"
        if completed == "Completed":
            dispatch = min(po_date + timedelta(days=18), today - timedelta(days=2))
        elif index % 2 == 0:
            dispatch = today - timedelta(days=4 + (index % 5) * 3)
        else:
            dispatch = today + timedelta(days=8 + (index % 12))
        if po_date > dispatch:
            po_date = dispatch - timedelta(days=14)
        qty = (8, 12, 4, 20, 16, 10, 24, 6)[index % 8]
        if index in reject_rows:
            machining = (
                "Internal reject: bore out of tolerance",
                "Internal reject: thread depth short",
                "Internal reject: sealing face tool mark",
            )[index % 3]
            deviation = (
                "Bore +0.04 mm on 3 pieces",
                "M6 thread depth short by 0.4 mm",
                "Tool mark across the sealing face",
            )[index % 3]
        elif index == 9:
            machining = "Finish pass complete; deburr pending"
            deviation = "OD +0.02 mm on 1 piece, accepted by review"
        elif completed == "Completed":
            machining = "All stages complete"
            deviation = ""
        elif completed == "Not started":
            machining = "Not started"
            deviation = ""
        else:
            machining = "Facing complete; finish pass in progress"
            deviation = ""
        if completed == "Completed":
            program = "Completed"
            rm_status = f"Ordered {po_date.strftime('%d %b %Y')}; Received {(po_date + timedelta(days=8)).strftime('%d %b %Y')}"
        elif completed == "Not started":
            program = "NA"
            rm_status = "Not ordered"
        elif index % 5 == 0:
            program = "Completed"
            rm_status = f"Ordered {po_date.strftime('%d %b %Y')}; Received {(po_date + timedelta(days=6)).strftime('%d %b %Y')}"
        elif index % 2 == 0:
            program = "Incomplete"
            rm_status = f"Ordered {po_date.strftime('%d %b %Y')}; awaiting receipt"
        else:
            program = "Incomplete"
            rm_status = f"Ordered {po_date.strftime('%d %b %Y')}; Received {(po_date + timedelta(days=9)).strftime('%d %b %Y')}"
        aerospace = "Yes" if index % 3 == 0 else "No"
        risk = "High" if aerospace == "Yes" or index in reject_rows else RISKS[index % 3]
        rows.append(
            {
                "APM NO": f"APM-{26041 + index}",
                "PO Date": po_date,
                "PO Number": f"PO-{45021 + index // 2}",
                "Part Number": part["number"],
                "Part Photo": part["file"],
                "Qty": qty,
                "Dispatch Date": dispatch,
                "Specification": part["spec"],
                "Risk": risk,
                "RM Size": part["rm"],
                "Action Qty": qty + (index % 3),
                "RM Status": rm_status,
                "Process": part["process"],
                "Tools & Accessories": part["tools"],
                "Special Process & Instruments": part["special"],
                "Inserts": part["inserts"],
                "Enquiry": enquiries[index % len(enquiries)],
                "Program Status": program,
                "Planning": _planning(part["process"], completed == "Completed", index % 4 == 1),
                "Machining Status": machining,
                "Review": "Customer rejected the lot; remanufacture required"
                if index in rma_rows
                else reviews[index % len(reviews)],
                "Deviation": deviation,
                "Customer": CUSTOMERS[index % len(CUSTOMERS)],
                "Completed Status": completed,
                "RMA Status": "Yes" if index in rma_rows else "No",
                "Is Aerospace Order": aerospace,
            }
        )
    return pd.DataFrame(rows, columns=EDITOR_COLUMNS)


CHOICE_FIELDS = {
    "Risk": {value.lower(): value for value in RISKS},
    "Program Status": {
        "completed": "Completed",
        "incomplete": "Incomplete",
        "na": "NA",
        "n/a": "NA",
    },
    "Completed Status": {value.lower(): value for value in COMPLETED_STATUSES},
    "RMA Status": {"yes": "Yes", "no": "No", "y": "Yes", "n": "No"},
    "Is Aerospace Order": {"yes": "Yes", "no": "No", "y": "Yes", "n": "No"},
}


def _clean_text(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "none", "nat"}:
        return ""
    return text


def _canonicalize(column: str, value: str) -> str:
    if column not in CHOICE_FIELDS or value == "":
        return value
    return CHOICE_FIELDS[column].get(value.lower(), value)


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for column in TEXT_COLUMNS:
        if column not in out:
            continue
        out[column] = [_canonicalize(column, _clean_text(value)) for value in out[column]]
    for column in COUNT_COLUMNS:
        out[column] = pd.to_numeric(out[column], errors="coerce")
    for column in DATE_COLUMNS:
        out[column] = pd.to_datetime(out[column], errors="coerce")
    return out


def for_editor(df: pd.DataFrame) -> pd.DataFrame:
    """Types the grid can edit: datetimes, floats, and text with no mixed blanks."""
    out = normalize(df)
    for column, default in (
        ("Risk", "Medium"),
        ("Program Status", "Incomplete"),
        ("Completed Status", "Not started"),
        ("RMA Status", "No"),
        ("Is Aerospace Order", "No"),
    ):
        out[column] = [value if value else default for value in out[column]]
    out["Part Photo"] = [
        photo
        if photo.startswith("assets/")
        else PHOTO_BY_PART.get(part_number, "")
        for photo, part_number in zip(out["Part Photo"], out["Part Number"])
    ]
    out["Qty"] = pd.to_numeric(out["Qty"], errors="coerce").astype("float64")
    out["Action Qty"] = pd.to_numeric(out["Action Qty"], errors="coerce").fillna(0).astype("float64")
    for column in DATE_COLUMNS:
        out[column] = pd.to_datetime(out[column], errors="coerce")
    return out[EDITOR_COLUMNS]


def validate(df: pd.DataFrame) -> list[str]:
    out = normalize(df)
    errors: list[str] = []
    if out.empty:
        return ["Add at least one order before saving."]

    missing_id = out["APM NO"].eq("")
    if missing_id.any():
        errors.append("Every row needs an APM NO.")
    duplicates = out.loc[~missing_id, "APM NO"].str.casefold()
    duplicates = out.loc[~missing_id, "APM NO"][duplicates.duplicated()].unique().tolist()
    if duplicates:
        errors.append("Duplicate APM NO: " + ", ".join(duplicates))

    for column in ("PO Number", "Part Number", "Customer", "Process", "Planning"):
        missing = out.loc[out[column].eq("") & ~missing_id, "APM NO"]
        if out[column].eq("").any():
            label = ", ".join(missing.tolist()) or "a row with no APM NO"
            errors.append(f"Every row needs a {column}. Missing on: {label}.")
    qty_fraction = (out["Qty"] - out["Qty"].round()).abs() > 1e-6
    qty_bad = out["Qty"].isna() | (out["Qty"] < 1) | qty_fraction.fillna(False)
    if qty_bad.any():
        errors.append("Qty must be a whole number of at least 1.")
    action_fraction = (out["Action Qty"] - out["Action Qty"].round()).abs() > 1e-6
    action_bad = out["Action Qty"].isna() | (out["Action Qty"] < 0) | action_fraction.fillna(False)
    if action_bad.any():
        errors.append("Action Qty must be a whole number of zero or more.")
    if out["PO Date"].isna().any() or out["Dispatch Date"].isna().any():
        errors.append("Every row needs a PO date and a dispatch date.")
    comparable = out["PO Date"].notna() & out["Dispatch Date"].notna() & ~missing_id
    bad_dates = out.loc[comparable & (out["Dispatch Date"] < out["PO Date"]), "APM NO"]
    if not bad_dates.empty:
        errors.append(
            "Dispatch date is before the PO date for: " + ", ".join(bad_dates.tolist())
        )
    rm = out["RM Status"].str.lower()
    material_ordered = rm.ne("") & ~rm.str.contains("not ordered", regex=False) & rm.str.contains(
        "order", regex=False
    )
    missing_action = out.loc[material_ordered & (out["Action Qty"].fillna(0) < 1), "APM NO"]
    if not missing_action.empty:
        errors.append(
            "Action Qty must be at least 1 when raw material is ordered: "
            + ", ".join(missing_action.tolist())
        )
    internal_reject = out["Machining Status"].str.contains("internal reject", case=False, na=False)
    missing_deviation = out.loc[internal_reject & out["Deviation"].eq(""), "APM NO"]
    if not missing_deviation.empty:
        errors.append(
            "Internal reject rows need a Deviation: " + ", ".join(missing_deviation.tolist())
        )
    missing_rma_review = out.loc[
        out["RMA Status"].eq("Yes") & out["Review"].eq(""), "APM NO"
    ]
    if not missing_rma_review.empty:
        errors.append(
            "RMA rows need a Review comment: " + ", ".join(missing_rma_review.tolist())
        )

    choices = {
        "Risk": RISKS,
        "Program Status": PROGRAM_STATUSES,
        "Completed Status": COMPLETED_STATUSES,
        "RMA Status": YES_NO,
        "Is Aerospace Order": YES_NO,
    }
    for column, allowed in choices.items():
        bad = sorted(set(out[column]) - set(allowed))
        if bad:
            errors.append(
                f"{column} must be one of: {', '.join(allowed)}. Found: {', '.join(bad)}."
            )
    return errors


def analysis_frame(df: pd.DataFrame, today: date | None = None) -> pd.DataFrame:
    today = today or date.today()
    out = normalize(df)
    out = out.loc[out["APM NO"].ne("")].copy()
    dated = out["Dispatch Date"].notna()
    out["Overdue"] = False
    out.loc[dated, "Overdue"] = (out.loc[dated, "Completed Status"] != "Completed") & (
        out.loc[dated, "Dispatch Date"] < pd.Timestamp(today)
    )
    out["Internal Reject"] = out["Machining Status"].str.contains(
        "internal reject", case=False, na=False
    )
    return out


def load_orders(path: Path) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name=SHEET_NAME, engine="openpyxl")
    missing = [column for column in EDITOR_COLUMNS if column not in raw.columns]
    if missing:
        raise ValueError(
            f"{path.name} is missing columns: {', '.join(missing)}. "
            "Use the sample workbook column names."
        )
    return for_editor(raw)


def _write_sheet(export: pd.DataFrame) -> Workbook:
    workbook = Workbook()
    workbook.properties.title = "Part Machining Orders"
    sheet = workbook.active
    sheet.title = SHEET_NAME
    header_fill = PatternFill("solid", fgColor="1F4E79")
    header_font = Font(bold=True, color="FFFFFF", name="Calibri", size=11)
    stripe = PatternFill("solid", fgColor="F4F7FB")
    aerospace = PatternFill("solid", fgColor=AEROSPACE_BLUE)
    thin = Border(
        left=Side(style="thin", color="D9E2F3"),
        right=Side(style="thin", color="D9E2F3"),
        top=Side(style="thin", color="D9E2F3"),
        bottom=Side(style="thin", color="D9E2F3"),
    )
    widths = {
        "APM NO": 14,
        "PO Date": 14,
        "PO Number": 14,
        "Part Number": 14,
        "Part Photo": 16,
        "Qty": 8,
        "Dispatch Date": 15,
        "Specification": 42,
        "Risk": 12,
        "RM Size": 24,
        "Action Qty": 12,
        "RM Status": 42,
        "Process": 32,
        "Tools & Accessories": 28,
        "Special Process & Instruments": 28,
        "Inserts": 16,
        "Enquiry": 42,
        "Program Status": 16,
        "Planning": 28,
        "Machining Status": 42,
        "Review": 42,
        "Deviation": 36,
        "Customer": 20,
        "Completed Status": 18,
        "RMA Status": 12,
        "Is Aerospace Order": 20,
    }
    wrap_headers = {
        "Specification",
        "RM Status",
        "Process",
        "Tools & Accessories",
        "Special Process & Instruments",
        "Enquiry",
        "Machining Status",
        "Review",
        "Deviation",
    }
    for column_index, name in enumerate(EDITOR_COLUMNS, start=1):
        cell = sheet.cell(1, column_index, name)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        sheet.column_dimensions[get_column_letter(column_index)].width = widths[name]
    sheet.row_dimensions[1].height = 30

    for row_index, record in enumerate(export.itertuples(index=False), start=2):
        values = list(record)
        is_aerospace = values[EDITOR_COLUMNS.index("Is Aerospace Order")] == "Yes"
        photo = values[EDITOR_COLUMNS.index("Part Photo")]
        sheet.row_dimensions[row_index].height = 36
        for column_index, value in enumerate(values, start=1):
            header = EDITOR_COLUMNS[column_index - 1]
            cell = sheet.cell(row_index, column_index, None if pd.isna(value) else value)
            cell.font = Font(name="Calibri", size=11)
            cell.border = thin
            cell.alignment = Alignment(vertical="center", wrap_text=header in wrap_headers)
            if is_aerospace:
                cell.fill = aerospace
            elif row_index % 2 == 0:
                cell.fill = stripe
            if header in DATE_COLUMNS:
                cell.number_format = "YYYY-MM-DD"
            elif header in COUNT_COLUMNS:
                cell.number_format = "#,##0"
        photo_path = ROOT / str(photo)
        if photo_path.exists():
            image = XLImage(str(photo_path))
            image.width = 64
            image.height = 42
            sheet.add_image(image, f"E{row_index}")

    last_row = max(2, len(export) + 1)
    last_column = get_column_letter(len(EDITOR_COLUMNS))
    sheet.auto_filter.ref = f"A1:{last_column}{last_row}"
    sheet.freeze_panes = "A2"
    sheet.page_setup.orientation = "landscape"
    sheet.page_setup.fitToPage = True
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0
    sheet.oddFooter.right.text = "Aerospace orders are shaded light blue"
    return workbook


def to_export_frame(df: pd.DataFrame) -> pd.DataFrame:
    errors = validate(df)
    if errors:
        raise ValueError("\n".join(errors))
    out = normalize(df)
    out["Qty"] = out["Qty"].round().astype(int)
    out["Action Qty"] = out["Action Qty"].round().astype(int)
    for column in DATE_COLUMNS:
        out[column] = [value.date() for value in out[column]]
    return out[EDITOR_COLUMNS]


def save_orders(df: pd.DataFrame, target: Path | BytesIO) -> None:
    workbook = _write_sheet(to_export_frame(df))
    if isinstance(target, Path):
        target.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(target)


def workbook_bytes(df: pd.DataFrame) -> bytes:
    buffer = BytesIO()
    save_orders(df, buffer)
    return buffer.getvalue()


def _schema_mismatch(path: Path) -> bool:
    if not path.exists():
        return True
    try:
        columns = pd.read_excel(path, sheet_name=SHEET_NAME, nrows=0, engine="openpyxl").columns
    except Exception:
        return True
    return any(column not in columns for column in ("APM NO", "Is Aerospace Order", "Part Photo"))


def ensure_workbook(path: Path = DEFAULT_WORKBOOK) -> Path:
    if _schema_mismatch(path):
        save_orders(build_sample(), path)
    return path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Create the sample machining workbook.")
    parser.add_argument("--force", action="store_true", help="Replace an existing workbook.")
    args = parser.parse_args()
    if DEFAULT_WORKBOOK.exists() and not args.force and not _schema_mismatch(DEFAULT_WORKBOOK):
        print(f"Already exists: {DEFAULT_WORKBOOK}")
        print("Pass --force to replace it with a fresh sample.")
    else:
        save_orders(build_sample(), DEFAULT_WORKBOOK)
        print(f"Wrote {DEFAULT_WORKBOOK}")
