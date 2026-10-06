from __future__ import annotations

import json
from datetime import date

from apps.directory.leave_rules import LeaveRuleError, normalize_leave_type
from apps.directory.models import Employee
from apps.directory.services import (
    balances_payload,
    calculation_payload,
    eligibility_payload,
    history_payload,
    holidays_payload,
    profile_payload,
    record_access,
)
from apps.assistant.agent.vector_store import search_policies


def build_tools(employee: Employee, trace: list[dict]):
    from crewai.tools import tool

    employee_id = employee.pk

    def remember(name: str, arguments: dict, payload: dict) -> str:
        text = json.dumps(payload)
        trace.append(
            {
                "kind": "tool",
                "title": name,
                "detail": json.dumps(arguments),
                "result": text[:2000],
            }
        )
        return text

    def current() -> Employee:
        return Employee.objects.select_related("user").get(pk=employee_id)

    @tool("Get my leave balances")
    def get_my_leave_balances(year: int = 0) -> str:
        """Read the signed-in employee's leave balances from Postgres. Pass 0 to use the current year."""
        chosen = None if year == 0 else year
        return remember("get_my_leave_balances", {"year": chosen or date.today().year}, balances_payload(current(), chosen))

    @tool("Get my profile")
    def get_my_profile(include_contact: bool = False) -> str:
        """Read the signed-in employee's job profile, joining date, and confirmation status from Postgres. Set include_contact to true only when the employee asks for their work email."""
        return remember(
            "get_my_profile",
            {"include_contact": include_contact},
            profile_payload(current(), include_contact=include_contact),
        )

    @tool("Get my leave history")
    def get_my_leave_history(limit: int = 8) -> str:
        """Read the signed-in employee's most recent leave requests from Postgres. limit is how many requests to return, from 1 to 20."""
        limit = max(1, min(limit, 20))
        return remember("get_my_leave_history", {"limit": limit}, history_payload(current(), limit=limit))

    @tool("List company holidays")
    def list_company_holidays(year: int = 0) -> str:
        """List company holidays from Postgres. Pass 0 for upcoming holidays, or a year such as 2026."""
        record_access(current(), "list_company_holidays")
        chosen = None if year == 0 else year
        return remember("list_company_holidays", {"year": chosen}, holidays_payload(chosen))

    @tool("Calculate leave days")
    def calculate_leave_days(leave_type: str, start_date: str, end_date: str) -> str:
        """Calculate deductible leave days for a date range using Northstar's weekend, holiday, and sandwich rules."""
        record_access(current(), "calculate_leave_days")
        arguments = {"leave_type": leave_type, "start_date": start_date, "end_date": end_date}
        try:
            start = date.fromisoformat(start_date[:10])
            end = date.fromisoformat(end_date[:10])
            normalize_leave_type(leave_type)
            payload = calculation_payload(leave_type, start, end)
        except (LeaveRuleError, ValueError) as exc:
            payload = {"error": str(exc)}
        return remember("calculate_leave_days", arguments, payload)

    @tool("Check leave eligibility")
    def check_leave_eligibility(
        leave_type: str,
        start_date: str,
        end_date: str,
        is_emergency: bool = False,
    ) -> str:
        """Check whether the signed-in employee can take this leave. Uses Postgres balances and the leave rules. Dates are YYYY-MM-DD."""
        arguments = {
            "leave_type": leave_type,
            "start_date": start_date,
            "end_date": end_date,
            "is_emergency": is_emergency,
        }
        try:
            start = date.fromisoformat(start_date[:10])
            end = date.fromisoformat(end_date[:10])
            payload = eligibility_payload(current(), leave_type, start, end, is_emergency=is_emergency)
        except (LeaveRuleError, ValueError) as exc:
            payload = {"error": str(exc)}
        return remember("check_leave_eligibility", arguments, payload)

    @tool("Search HR policies")
    def search_hr_policies(query: str) -> str:
        """Search the HR policy vector database. Use this for policy, benefits, work-from-home, conduct, and leave-rule questions."""
        record_access(current(), "search_hr_policies")
        return remember("search_hr_policies", {"query": query}, search_policies(query))

    return [
        get_my_leave_balances,
        get_my_profile,
        get_my_leave_history,
        list_company_holidays,
        calculate_leave_days,
        check_leave_eligibility,
        search_hr_policies,
    ]
