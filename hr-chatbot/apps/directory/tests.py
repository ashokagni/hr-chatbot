import json
import shutil
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.contrib.auth.models import User
from django.test import Client, TestCase, SimpleTestCase

from apps.assistant.agent.guard import refusal_reason
from apps.assistant.agent.vector_store import chunk_markdown, index_policies, release_vector_store, search_policies
from apps.directory.company_calendar import HOLIDAYS
from apps.directory.demo_data import DEMO_PASSWORD, load_demo_data
from apps.directory.leave_rules import BalanceFacts, EmployeeFacts, calculate_leave_days, check_eligibility
from apps.directory.models import Employee
from apps.directory.services import balances_payload


HOLIDAY_DATES = {day for day, _name in HOLIDAYS}
AS_OF = date(2026, 10, 5)


class LeaveCalculationTests(SimpleTestCase):
    def test_earned_leave_sandwich_across_year_end(self):
        calculation = calculate_leave_days("EL", date(2026, 12, 22), date(2027, 1, 2), HOLIDAY_DATES)
        self.assertEqual(calculation.deducted_days, Decimal("10"))
        self.assertEqual(len(calculation.working_days), 7)
        self.assertEqual(len(calculation.sandwich_days), 3)

    def test_sick_leave_does_not_sandwich(self):
        calculation = calculate_leave_days("SL", date(2026, 12, 22), date(2027, 1, 2), HOLIDAY_DATES)
        self.assertEqual(calculation.deducted_days, Decimal("7"))
        self.assertEqual(calculation.sandwich_days, [])

    def test_maternity_counts_calendar_days(self):
        calculation = calculate_leave_days("maternity leave", date(2026, 12, 22), date(2027, 1, 2), HOLIDAY_DATES)
        self.assertEqual(calculation.deducted_days, Decimal("12"))

    def test_confirmed_employee_can_take_four_earned_leave_days(self):
        decision = check_eligibility(
            EmployeeFacts(date(2024, 3, 15), date(2024, 9, 15), "maternity"),
            "EL",
            date(2026, 11, 10),
            date(2026, 11, 13),
            HOLIDAY_DATES,
            BalanceFacts(Decimal("18"), Decimal("5"), Decimal("2")),
            AS_OF,
        )
        self.assertTrue(decision.eligible)
        self.assertEqual(decision.calculation.deducted_days, Decimal("4"))

    def test_probation_blocks_earned_leave(self):
        decision = check_eligibility(
            EmployeeFacts(date(2026, 7, 20), None, "paternity"),
            "EL",
            date(2026, 11, 10),
            date(2026, 11, 13),
            HOLIDAY_DATES,
            BalanceFacts(Decimal("0"), Decimal("0"), Decimal("0")),
            AS_OF,
        )
        self.assertFalse(decision.eligible)
        self.assertTrue(any("probation" in reason.lower() for reason in decision.reasons))

    def test_casual_leave_rejects_more_than_three_working_days(self):
        decision = check_eligibility(
            EmployeeFacts(date(2024, 3, 15), date(2024, 9, 15), "maternity"),
            "casual",
            date(2026, 11, 10),
            date(2026, 11, 13),
            HOLIDAY_DATES,
            BalanceFacts(Decimal("8"), Decimal("0"), Decimal("0")),
            AS_OF,
        )
        self.assertFalse(decision.eligible)

    def test_insufficient_balance_is_rejected(self):
        decision = check_eligibility(
            EmployeeFacts(date(2024, 3, 15), date(2024, 9, 15), "maternity"),
            "EL",
            date(2026, 11, 10),
            date(2026, 11, 13),
            HOLIDAY_DATES,
            BalanceFacts(Decimal("8"), Decimal("6"), Decimal("0")),
            AS_OF,
        )
        self.assertFalse(decision.eligible)
        self.assertTrue(any("remain" in reason for reason in decision.reasons))


class PolicyLibraryTests(SimpleTestCase):
    def test_holiday_document_matches_the_database_calendar(self):
        from django.conf import settings

        text = (Path(settings.POLICIES_DIR) / "holiday-and-attendance.md").read_text(encoding="utf-8")
        for day, name in HOLIDAYS:
            self.assertIn(day.isoformat(), text)
            self.assertIn(name, text)

    def test_work_from_home_sections_are_searchable_chunks(self):
        from django.conf import settings

        chunks = chunk_markdown(Path(settings.POLICIES_DIR) / "work-from-home-policy.md")
        combined = "\n".join(chunk["text"] for chunk in chunks).lower()
        self.assertIn("two days", combined)
        self.assertTrue(any(chunk["section"] == "Weekly limit" for chunk in chunks))


class VectorSearchTests(SimpleTestCase):
    def test_chroma_search_returns_the_work_from_home_policy(self):
        folder = Path(tempfile.mkdtemp())
        try:
            count = index_policies(persist_dir=folder)
            self.assertGreater(count, 5)
            result = search_policies("how many days a week can I work from home", persist_dir=folder)
            self.assertIn("work from home", json.dumps(result).lower())
        finally:
            release_vector_store()
            shutil.rmtree(folder, ignore_errors=True)


class EmployeeRecordTests(TestCase):
    def setUp(self):
        load_demo_data()
        self.priya = Employee.objects.get(employee_code="NS1042")
        self.arjun = Employee.objects.get(employee_code="NS1188")

    def test_seeded_balances_match_leave_history(self):
        payload = balances_payload(self.priya, 2026)
        balances = {row["leave_type"]: row for row in payload["balances"]}
        self.assertEqual(balances["EL"]["remaining"], 11)
        self.assertEqual(balances["CL"]["remaining"], 5)
        self.assertEqual(balances["SL"]["remaining"], 7)
        self.assertEqual(balances["OH"]["remaining"], 1)
        self.assertNotIn("NS1188", json.dumps(payload))

    def test_guard_blocks_another_employees_record(self):
        reason = refusal_reason(self.priya, "What is Arjun Mehta's leave balance?")
        self.assertIsNotNone(reason)
        self.assertIsNone(refusal_reason(self.priya, "What is my leave balance?"))

    def test_chat_requires_login_and_reports_a_missing_model(self):
        client = Client()
        blocked = client.get("/chat/")
        self.assertEqual(blocked.status_code, 302)
        user = User.objects.get(username="priya.sharma")
        client.force_login(user)
        page = client.get("/chat/")
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Priya Sharma")
        response = client.post(
            "/api/chat/",
            data=json.dumps({"message": "What is my leave balance?"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("language model", response.json()["answer"].lower())

    def test_demo_password_can_sign_in(self):
        client = Client()
        response = client.post("/", {"username": "arjun.mehta", "password": DEMO_PASSWORD})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/chat/")
