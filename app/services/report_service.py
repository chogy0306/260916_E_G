from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.services.mapping_service import field_label

SEVERITY_LABELS = {"ERROR": "오류", "WARNING": "경고", "REVIEW": "확인필요", "NORMAL": "정상"}
STATUS_LABELS = {
    "NEW": "신규",
    "REVIEWING": "검토중",
    "CONFIRMED": "오류 확정",
    "FALSE_POSITIVE": "정상(오탐)",
    "RESOLVED": "해결됨",
}
# (background, text) hex pairs, matching the web UI's severity-dot colors.
# openpyxl defaults a bare 6-digit hex to alpha 00 (fully transparent), so
# every color must carry an explicit "FF" alpha prefix to actually show up.
SEVERITY_COLORS = {
    "ERROR": ("FFFDECEB", "FFC8372C"),
    "WARNING": ("FFFDF1E2", "FFB96F0C"),
    "REVIEW": ("FFFDF7E0", "FF9C7C0A"),
    "NORMAL": ("FFE9F7EF", "FF1F8A4E"),
}
RANK_TO_SEVERITY = ["ERROR", "WARNING", "REVIEW", "NORMAL"]

HEADERS = [
    "직원ID", "직원명", "부서", "검증항목", "등급", "전월값", "이번달값",
    "변동률(%)", "탐지사유", "AI 분석", "처리상태", "메모",
]
WRAP_COLUMNS = (9, 10, 12)  # 탐지사유, AI 분석, 메모
AMOUNT_COLUMNS = (6, 7)  # 전월값, 이번달값


def _category_label(r):
    if r.field_name:
        return f"{r.category} ({field_label(r.field_name)})"
    return r.category


def _group_summary_text(group):
    counts = {}
    for r in group["results"]:
        counts[r.severity] = counts.get(r.severity, 0) + 1
    if not counts:
        return "정상 (이상 없음)"
    return " · ".join(
        f"{SEVERITY_LABELS[s]} {counts[s]}건" for s in ("ERROR", "WARNING", "REVIEW") if counts.get(s)
    )


def _paint_row(ws, row, num_cols, bg, fg, bold):
    for col in range(1, num_cols + 1):
        cell = ws.cell(row=row, column=col)
        cell.fill = PatternFill("solid", fgColor=bg)
        if bold:
            cell.font = Font(bold=True, color=fg)


def _write_group_header(ws, row, num_cols, employee_id, employee_name, department, summary_text, severity):
    bg, fg = SEVERITY_COLORS[severity]
    ws.cell(row=row, column=1, value=employee_id or "")
    ws.cell(row=row, column=2, value=employee_name or "")
    ws.cell(row=row, column=3, value=department or "")
    ws.cell(row=row, column=4, value=summary_text)
    _paint_row(ws, row, num_cols, bg, fg, bold=True)


def _write_detail_row(ws, row, employee_id, employee_name, department, r):
    values = [
        employee_id or "",
        employee_name or "",
        department or "",
        _category_label(r),
        SEVERITY_LABELS.get(r.severity, r.severity),
        float(r.previous_value) if r.previous_value is not None else None,
        float(r.current_value) if r.current_value is not None else None,
        round(r.change_rate, 1) if r.change_rate is not None else None,
        r.message,
        r.ai_analysis.summary if r.ai_analysis else "",
        STATUS_LABELS.get(r.status, r.status),
        "; ".join(n.note for n in r.notes) if r.notes else "",
    ]
    for col, value in enumerate(values, start=1):
        ws.cell(row=row, column=col, value=value)

    sev_bg, sev_fg = SEVERITY_COLORS.get(r.severity, ("FFFFFFFF", "FF000000"))
    sev_cell = ws.cell(row=row, column=5)
    sev_cell.fill = PatternFill("solid", fgColor=sev_bg)
    sev_cell.font = Font(color=sev_fg, bold=True)

    for col in AMOUNT_COLUMNS:
        ws.cell(row=row, column=col).number_format = "#,##0"
    for col in WRAP_COLUMNS:
        ws.cell(row=row, column=col).alignment = Alignment(wrap_text=True, vertical="top")

    ws.row_dimensions[row].outlineLevel = 1


def build_results_excel(groups, unassigned):
    """groups/unassigned: the same structures _group_by_employee() produces.

    Each employee gets one bold, color-coded summary row followed by their
    detail rows, collapsed into an Excel row group (the +/- outline control)
    so the whole sheet can be skimmed at a glance and expanded on demand.
    """
    num_cols = len(HEADERS)
    wb = Workbook()
    ws = wb.active
    ws.title = "검증결과"

    ws.append(HEADERS)
    _paint_row(ws, 1, num_cols, "FF333132", "FFFFFFFF", bold=True)
    for col in range(1, num_cols + 1):
        ws.cell(row=1, column=col).alignment = Alignment(vertical="center")

    # Collapse arrow sits above each group's detail rows, next to the summary row.
    ws.sheet_properties.outlinePr.summaryBelow = False

    row = 2
    for group in groups:
        rank = group.get("rank", 3)
        severity = RANK_TO_SEVERITY[rank] if rank < len(RANK_TO_SEVERITY) else "NORMAL"
        _write_group_header(
            ws, row, num_cols,
            group.get("employee_id"), group.get("employee_name"), group.get("department"),
            _group_summary_text(group), severity,
        )
        row += 1
        for r in group["results"]:
            _write_detail_row(ws, row, group.get("employee_id"), group.get("employee_name"), group.get("department"), r)
            row += 1

    if unassigned:
        _write_group_header(ws, row, num_cols, "", "인원 변동", "", f"확인필요 {len(unassigned)}건", "REVIEW")
        row += 1
        for r in unassigned:
            _write_detail_row(ws, row, "", "", "", r)
            row += 1

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(num_cols)}{max(row - 1, 1)}"

    widths = [12, 10, 10, 26, 10, 14, 14, 10, 46, 40, 12, 24]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer
