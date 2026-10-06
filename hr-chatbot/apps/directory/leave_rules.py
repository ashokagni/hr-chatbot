from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

class LeaveRuleError(ValueError):
    pass


@dataclass(frozen=True)
class EmployeeFacts:
    date_of_joining: date
    confirmation_date: date | None
    parental_leave_track: str


@dataclass(frozen=True)
class BalanceFacts:
    entitled: Decimal
    used: Decimal
    pending: Decimal

    @property
    def remaining(self) -> Decimal:
        return self.entitled - self.used - self.pending


@dataclass
class LeaveCalculation:
    leave_type: str
    leave_name: str
    start_date: date
    end_date: date
    unit: str
    deducted_days: Decimal
    working_days: list[date] = field(default_factory=list)
    sandwich_days: list[date] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "leave_type": self.leave_type,
            "leave_name": self.leave_name,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "unit": self.unit,
            "deducted_days": _num(self.deducted_days),
            "working_days": [day.isoformat() for day in self.working_days],
            "sandwich_days": [day.isoformat() for day in self.sandwich_days],
            "notes": self.notes,
        }


@dataclass
class EligibilityDecision:
    eligible: bool
    reasons: list[str]
    warnings: list[str]
    calculation: LeaveCalculation | None
    balance_remaining: Decimal | None
    balance_after: Decimal | None

    def as_dict(self) -> dict:
        return {
            "eligible": self.eligible,
            "reasons": self.reasons,
            "warnings": self.warnings,
            "balance_remaining": _num(self.balance_remaining),
            "balance_after": _num(self.balance_after),
            "calculation": None if self.calculation is None else self.calculation.as_dict(),
        }


LEAVE_CATALOG: dict[str, dict] = {
    "CL": {
        "name": "Casual Leave",
        "unit": "working",
        "sandwich": True,
        "max_working_days": 3,
        "min_notice_days": 1,
        "notice_when_working_days_exceed": None,
        "requires_confirmation": False,
        "uses_balance": True,
    },
    "SL": {
        "name": "Sick Leave",
        "unit": "working",
        "sandwich": False,
        "max_working_days": None,
        "min_notice_days": 0,
        "notice_when_working_days_exceed": None,
        "requires_confirmation": False,
        "uses_balance": True,
    },
    "EL": {
        "name": "Earned Leave",
        "unit": "working",
        "sandwich": True,
        "max_working_days": 15,
        "min_notice_days": 0,
        "notice_when_working_days_exceed": (3, 7),
        "requires_confirmation": True,
        "uses_balance": True,
    },
    "OH": {
        "name": "Optional Holiday",
        "unit": "working",
        "sandwich": False,
        "max_working_days": 1,
        "min_notice_days": 1,
        "notice_when_working_days_exceed": None,
        "requires_confirmation": True,
        "uses_balance": True,
    },
    "PL": {
        "name": "Paternity Leave",
        "unit": "working",
        "sandwich": False,
        "max_working_days": 10,
        "min_notice_days": 7,
        "notice_when_working_days_exceed": None,
        "requires_confirmation": True,
        "uses_balance": True,
        "parental_track": "paternity",
    },
    "ML": {
        "name": "Maternity Leave",
        "unit": "calendar",
        "sandwich": False,
        "max_calendar_days": 182,
        "min_service_days": 80,
        "min_notice_days": 0,
        "recommended_notice_days": 56,
        "requires_confirmation": False,
        "uses_balance": True,
        "parental_track": "maternity",
    },
}

ALIASES = {
    "cl": "CL",
    "casual": "CL",
    "casual leave": "CL",
    "sl": "SL",
    "sick": "SL",
    "sick leave": "SL",
    "el": "EL",
    "earned": "EL",
    "earned leave": "EL",
    "privilege": "EL",
    "privilege leave": "EL",
    "oh": "OH",
    "optional": "OH",
    "optional holiday": "OH",
    "pl": "PL",
    "paternity": "PL",
    "paternity leave": "PL",
    "ml": "ML",
    "maternity": "ML",
    "maternity leave": "ML",
}


def normalize_leave_type(value: str) -> str:
    key = " ".join(value.strip().lower().replace("_", " ").split())
    if key in ALIASES:
        return ALIASES[key]
    upper = value.strip().upper()
    if upper in LEAVE_CATALOG:
        return upper
    known = ", ".join(LEAVE_CATALOG)
    raise LeaveRuleError(f"Unknown leave type '{value}'. Use one of: {known}.")


def calculate_leave_days(
    leave_type: str,
    start: date,
    end: date,
    holidays: set[date],
) -> LeaveCalculation:
    code = normalize_leave_type(leave_type)
    if end < start:
        raise LeaveRuleError("The end date must be on or after the start date.")
    if (end - start).days > 366:
        raise LeaveRuleError("Choose a date range of one year or less.")

    rule = LEAVE_CATALOG[code]
    days = _inclusive_days(start, end)
    if rule["unit"] == "calendar":
        calculation = LeaveCalculation(
            leave_type=code,
            leave_name=rule["name"],
            start_date=start,
            end_date=end,
            unit="calendar_day",
            deducted_days=Decimal(len(days)),
            working_days=[day for day in days if not _is_non_working(day, holidays)],
            notes=["Maternity leave counts every calendar day, including weekends and holidays."],
        )
        return calculation

    working_days = [day for day in days if not _is_non_working(day, holidays)]
    sandwich_days: list[date] = []
    if rule["sandwich"] and working_days:
        first, last = working_days[0], working_days[-1]
        sandwich_days = [
            day for day in days if first < day < last and _is_non_working(day, holidays)
        ]
    notes = [
        "Weekends and company holidays are not deducted on their own.",
    ]
    if rule["sandwich"]:
        notes.append(
            "The sandwich rule counts a weekend or holiday only when it falls strictly "
            "between the first and last working day of this request."
        )
    else:
        notes.append(f"{rule['name']} does not use the sandwich rule.")
    return LeaveCalculation(
        leave_type=code,
        leave_name=rule["name"],
        start_date=start,
        end_date=end,
        unit="working_day_with_sandwich" if rule["sandwich"] else "working_day",
        deducted_days=Decimal(len(working_days) + len(sandwich_days)),
        working_days=working_days,
        sandwich_days=sandwich_days,
        notes=notes,
    )


def check_eligibility(
    employee: EmployeeFacts,
    leave_type: str,
    start: date,
    end: date,
    holidays: set[date],
    balance: BalanceFacts | None,
    as_of: date,
    is_emergency: bool = False,
) -> EligibilityDecision:
    code = normalize_leave_type(leave_type)
    rule = LEAVE_CATALOG[code]
    calculation = calculate_leave_days(code, start, end, holidays)
    reasons: list[str] = []
    warnings: list[str] = []

    if calculation.deducted_days == 0:
        reasons.append("Those dates do not include a deductible leave day.")

    required_track = rule.get("parental_track")
    if required_track and employee.parental_leave_track != required_track:
        reasons.append(
            f"{rule['name']} is available only when the employee record is marked for {required_track} leave."
        )

    confirmed = _is_confirmed(employee, start)
    if rule["requires_confirmation"] and not confirmed:
        reasons.append(f"{rule['name']} is available after confirmation. This employee is still in probation.")

    min_service = rule.get("min_service_days")
    if min_service is not None:
        service_days = (start - employee.date_of_joining).days
        if service_days < min_service:
            reasons.append(
                f"{rule['name']} requires at least {min_service} days of service before the start date. "
                f"Service on that date would be {service_days} days."
            )

    max_working = rule.get("max_working_days")
    if max_working is not None and len(calculation.working_days) > max_working:
        reasons.append(
            f"One {rule['name']} request can cover at most {max_working} working day"
            f"{'' if max_working == 1 else 's'}."
        )
    max_calendar = rule.get("max_calendar_days")
    if max_calendar is not None and calculation.deducted_days > max_calendar:
        reasons.append(f"{rule['name']} cannot exceed {max_calendar} calendar days in one request.")

    if code == "SL":
        if start < as_of - timedelta(days=2):
            reasons.append("Sick leave can be regularized only up to 2 calendar days after it starts.")
        if len(calculation.working_days) > 2:
            warnings.append(
                "More than 2 consecutive working days of sick leave need a medical certificate sent to HR, not to this assistant."
            )
    elif start < as_of:
        reasons.append("This leave type cannot start in the past.")

    notice_days = (start - as_of).days
    extra_notice = rule.get("notice_when_working_days_exceed")
    if extra_notice and len(calculation.working_days) > extra_notice[0] and notice_days < extra_notice[1]:
        threshold, required = extra_notice
        reasons.append(
            f"{rule['name']} of more than {threshold} working days needs {required} calendar days of notice. "
            f"This request has {max(notice_days, 0)}."
        )
    elif rule["min_notice_days"] and notice_days < rule["min_notice_days"]:
        if code == "CL" and is_emergency:
            warnings.append("Emergency casual leave still needs the manager's confirmation.")
        else:
            reasons.append(
                f"{rule['name']} needs at least {rule['min_notice_days']} calendar day"
                f"{'' if rule['min_notice_days'] == 1 else 's'} of notice."
            )

    recommended = rule.get("recommended_notice_days")
    if recommended and notice_days < recommended:
        warnings.append(
            f"Please inform HR at least {recommended} days before maternity leave when the date is known."
        )

    remaining: Decimal | None = None
    balance_after: Decimal | None = None
    if rule["uses_balance"]:
        if balance is None:
            reasons.append(f"No {rule['name']} balance is stored for {start.year}.")
        else:
            remaining = balance.remaining
            balance_after = remaining - calculation.deducted_days
            if calculation.deducted_days > remaining:
                reasons.append(
                    f"This request needs {_num(calculation.deducted_days)} day(s), "
                    f"but only {_num(remaining)} remain "
                    f"({_num(balance.entitled)} entitled, {_num(balance.used)} used, {_num(balance.pending)} pending)."
                )

    return EligibilityDecision(
        eligible=not reasons,
        reasons=reasons or [f"The request meets the {rule['name']} rules and the available balance."],
        warnings=warnings,
        calculation=calculation,
        balance_remaining=remaining,
        balance_after=balance_after if not reasons else balance_after,
    )


def _is_confirmed(employee: EmployeeFacts, on_date: date) -> bool:
    return employee.confirmation_date is not None and employee.confirmation_date <= on_date


def _inclusive_days(start: date, end: date) -> list[date]:
    days = []
    current = start
    while current <= end:
        days.append(current)
        current += timedelta(days=1)
    return days


def _is_non_working(day: date, holidays: set[date]) -> bool:
    return day.weekday() >= 5 or day in holidays


def _num(value: Decimal | None) -> int | float | None:
    if value is None:
        return None
    if value == value.to_integral_value():
        return int(value)
    return float(value)
