import difflib
import re

IDENTITY_FIELDS = {"employee_id", "employee_name", "department", "position"}

REQUIRED_FIELDS = {"employee_id", "employee_name"}

EARNING_ITEMS = {"base_salary", "meal_allowance", "position_allowance", "performance_bonus"}
DEDUCTION_ITEMS = {
    "income_tax",
    "pension",
    "health_insurance",
    "long_term_care",
    "employment_insurance",
    "industrial_accident",
}
INSURANCE_ITEMS = {
    "pension",
    "health_insurance",
    "long_term_care",
    "employment_insurance",
    "industrial_accident",
}
TOTAL_FIELDS = {"total_earnings", "total_deductions", "net_salary"}

SYNONYMS = {
    "employee_id": ["사번", "직원번호", "직원id", "employeeid", "empid", "emp_id", "직원ID"],
    "employee_name": ["성명", "이름", "직원명", "name", "employeename"],
    "department": ["부서", "부서명", "department"],
    "position": ["직급", "직책", "position", "직위"],
    "base_salary": ["기본급", "basesalary"],
    "meal_allowance": ["식대", "meal", "mealallowance"],
    "position_allowance": ["직책수당", "positionallowance"],
    "performance_bonus": ["성과급", "성과금", "performancebonus"],
    "total_earnings": ["지급총액", "총지급액", "totalearnings"],
    "income_tax": ["소득세", "incometax"],
    "pension": ["국민연금", "pension"],
    "health_insurance": ["건강보험", "healthinsurance"],
    "long_term_care": ["장기요양보험", "장기요양", "longtermcare"],
    "employment_insurance": ["고용보험", "employmentinsurance"],
    "industrial_accident": ["산재보험", "industrialaccident"],
    "total_deductions": ["공제총액", "총공제액", "totaldeductions"],
    "net_salary": ["실지급액", "netsalary"],
}

FIELD_LABELS = {
    "employee_id": "직원ID",
    "employee_name": "직원명",
    "department": "부서",
    "position": "직급",
    "base_salary": "기본급",
    "meal_allowance": "식대",
    "position_allowance": "직책수당",
    "performance_bonus": "성과급",
    "total_earnings": "총지급액",
    "income_tax": "소득세",
    "pension": "국민연금",
    "health_insurance": "건강보험",
    "long_term_care": "장기요양보험",
    "employment_insurance": "고용보험",
    "industrial_accident": "산재보험",
    "total_deductions": "총공제액",
    "net_salary": "실지급액",
}


def _normalize(text):
    return re.sub(r"[^0-9a-zA-Z가-힣]", "", str(text)).lower()


def suggest_mapping(columns):
    """Returns {excel_column: suggested_system_field_or_None}."""
    lookup = {}
    for field, aliases in SYNONYMS.items():
        for alias in aliases + [field]:
            lookup[_normalize(alias)] = field

    mapping = {}
    normalized_keys = list(lookup.keys())
    for col in columns:
        norm = _normalize(col)
        if norm in lookup:
            mapping[col] = lookup[norm]
            continue
        close = difflib.get_close_matches(norm, normalized_keys, n=1, cutoff=0.8)
        mapping[col] = lookup[close[0]] if close else None
    return mapping


def missing_required_fields(mapping):
    mapped_fields = set(v for v in mapping.values() if v)
    return sorted(REQUIRED_FIELDS - mapped_fields)


def field_label(name):
    return FIELD_LABELS.get(name, name)
