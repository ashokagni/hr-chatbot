from __future__ import annotations

from datetime import date
from decimal import Decimal

from apps.directory.company_calendar import HOLIDAYS
from apps.directory.leave_rules import (
    LEAVE_CATALOG,
    BalanceFacts,
    EmployeeFacts,
    LeaveRuleError,
    calculate_leave_days,
    check_eligibility,
    normalize_leave_type,
)
from apps.directory.models import AccessAuditLog, Employee, Holiday, LeaveBalance, LeaveRequest


def record_access(employee: Employee, tool_name: str) -> None:
    AccessAuditLog.objects.create(employee=employee, tool_name=tool_name)


def balances_payload(employee: Employee, year: int | None = None) -> dict:
    record_access(employee, "get_my_leave_balances")
    year = year or date.today().year
    rows = employee.leave_balances.filter(year=year).order_by("leave_type")
    return {
        "employee_code": employee.employee_code,
        "employee_name": employee.user.get_full_name(),
        "year": year,
        "balances": [
            {
                "leave_type": row.leave_type,
                "leave_name": LEAVE_CATALOG.get(row.leave_type, {}).get("name", row.leave_type),
                "entitled": _num(row.entitled),
                "used": _num(row.used),
                "pending": _num(row.pending),
                "remaining": _num(row.remaining),
            }
            for row in rows
        ],
    }


def profile_payload(employee: Employee, include_contact: bool = False) -> dict:
    record_access(employee, "get_my_profile")
    confirmed = employee.confirmation_date is not None and employee.confirmation_date <= date.today()
    payload = {
        "employee_code": employee.employee_code,
        "name": employee.user.get_full_name(),
        "department": employee.department,
        "job_title": employee.job_title,
        "location": employee.location,
        "manager_name": employee.manager_name,
        "date_of_joining": employee.date_of_joining.isoformat(),
        "confirmation_date": None if employee.confirmation_date is None else employee.confirmation_date.isoformat(),
        "employment_state": "confirmed" if confirmed else "probation",
        "parental_leave_track": employee.parental_leave_track,
    }
    if include_contact:
        payload["email"] = employee.user.email
    return payload


def history_payload(employee: Employee, limit: int = 8) -> dict:
    record_access(employee, "get_my_leave_history")
    rows = employee.leave_requests.all()[:limit]
    return {
        "employee_code": employee.employee_code,
        "requests": [
            {
                "leave_type": row.leave_type,
                "start_date": row.start_date.isoformat(),
                "end_date": row.end_date.isoformat(),
                "days": _num(row.days),
                "status": row.status,
            }
            for row in rows
        ],
    }


def holidays_payload(year: int | None = None, as_of: date | None = None) -> dict:
    as_of = as_of or date.today()
    if year:
        rows = Holiday.objects.filter(date__year=year)
        scope = str(year)
    else:
        rows = Holiday.objects.filter(date__gte=as_of)[:8]
        scope = f"upcoming from {as_of.isoformat()}"
    return {
        "scope": scope,
        "holidays": [{"date": row.date.isoformat(), "name": row.name} for row in rows],
    }


def calculation_payload(leave_type: str, start: date, end: date) -> dict:
    holidays = set(Holiday.objects.values_list("date", flat=True))
    calculation = calculate_leave_days(leave_type, start, end, holidays)
    return calculation.as_dict()


def eligibility_payload(
    employee: Employee,
    leave_type: str,
    start: date,
    end: date,
    as_of: date | None = None,
    is_emergency: bool = False,
) -> dict:
    record_access(employee, "check_leave_eligibility")
    as_of = as_of or date.today()
    code = normalize_leave_type(leave_type)
    balance_row = employee.leave_balances.filter(leave_type=code, year=start.year).first()
    balance = None
    if balance_row is not None:
        balance = BalanceFacts(balance_row.entitled, balance_row.used, balance_row.pending)
    decision = check_eligibility(
        employee=_facts(employee),
        leave_type=code,
        start=start,
        end=end,
        holidays=set(Holiday.objects.values_list("date", flat=True)),
        balance=balance,
        as_of=as_of,
        is_emergency=is_emergency,
    )
    payload = decision.as_dict()
    payload["employee_code"] = employee.employee_code
    payload["as_of"] = as_of.isoformat()
    return payload


def _facts(employee: Employee) -> EmployeeFacts:
    return EmployeeFacts(
        date_of_joining=employee.date_of_joining,
        confirmation_date=employee.confirmation_date,
        parental_leave_track=employee.parental_leave_track,
    )


def _num(value: Decimal) -> int | float:
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def seed_holidays() -> None:
    Holiday.objects.all().delete()
    Holiday.objects.bulk_create([Holiday(date=day, name=name) for day, name in HOLIDAYS])


__all__ = [
    "LeaveRuleError",
    "balances_payload",
    "calculation_payload",
    "eligibility_payload",
    "history_payload",
    "holidays_payload",
    "profile_payload",
    "seed_holidays",
]
