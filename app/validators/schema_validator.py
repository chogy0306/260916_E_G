from app.services.mapping_service import SYNONYMS, missing_required_fields


def check(mapping):
    """Raises a user-facing message listing acceptable column names when a
    required system field (employee_id, employee_name) isn't mapped."""
    missing = missing_required_fields(mapping)
    if not missing:
        return

    lines = []
    for field in missing:
        aliases = ", ".join(SYNONYMS.get(field, []))
        lines.append(f"'{field}' 컬럼을 찾을 수 없습니다. 다음 중 하나를 지정해주세요: {aliases}")
    raise ValueError(" / ".join(lines))
