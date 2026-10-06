from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import transaction

from apps.directory.leave_rules import calculate_leave_days
from apps.directory.models import Employee, LeaveBalance, LeaveRequest
from apps.directory.services import seed_holidays

DEMO_PASSWORD = "Northstar#2026"

PEOPLE = [
    {
        "username": "priya.sharma",
        "first_name": "Priya",
        "last_name": "Sharma",
        "email": "priya.sharma@northstar.example",
        "employee_code": "NS1042",
        "department": "Engineering",
        "job_title": "Senior Software Engineer",
        "location": "Bengaluru",
        "date_of_joining": date(2024, 3, 15),
        "confirmation_date": date(2024, 9, 15),
        "parental_leave_track": Employee.ParentalTrack.MATERNITY,
        "manager_name": "Rahul Deshmukh",
        "is_staff": False,
        "entitlements": {"CL": 8, "SL": 8, "EL": 18, "OH": 2, "ML": 182, "PL": 0},
        "requests": [
            ("CL", date(2026, 1, 12), date(2026, 1, 13), LeaveRequest.Status.APPROVED),
            ("CL", date(2026, 2, 10), date(2026, 2, 10), LeaveRequest.Status.APPROVED),
            ("SL", date(2026, 4, 6), date(2026, 4, 6), LeaveRequest.Status.APPROVED),
            ("OH", date(2026, 3, 20), date(2026, 3, 20), LeaveRequest.Status.APPROVED),
            ("EL", date(2026, 8, 17), date(2026, 8, 21), LeaveRequest.Status.APPROVED),
            ("EL", date(2026, 12, 1), date(2026, 12, 2), LeaveRequest.Status.PENDING),
        ],
    },
    {
        "username": "arjun.mehta",
        "first_name": "Arjun",
        "last_name": "Mehta",
        "email": "arjun.mehta@northstar.example",
        "employee_code": "NS1188",
        "department": "Product",
        "job_title": "Associate Product Manager",
        "location": "Hyderabad",
        "date_of_joining": date(2026, 7, 20),
        "confirmation_date": None,
        "parental_leave_track": Employee.ParentalTrack.PATERNITY,
        "manager_name": "Sana Qureshi",
        "is_staff": False,
        "entitlements": {"CL": 2, "SL": 2, "EL": 0, "OH": 0, "ML": 0, "PL": 10},
        "requests": [
            ("CL", date(2026, 9, 1), date(2026, 9, 1), LeaveRequest.Status.APPROVED),
        ],
    },
    {
        "username": "neha.iyer",
        "first_name": "Neha",
        "last_name": "Iyer",
        "email": "neha.iyer@northstar.example",
        "employee_code": "NS1008",
        "department": "People",
        "job_title": "HR Business Partner",
        "location": "Mumbai",
        "date_of_joining": date(2022, 1, 10),
        "confirmation_date": date(2022, 7, 10),
        "parental_leave_track": Employee.ParentalTrack.NONE,
        "manager_name": "Kavita Rao",
        "is_staff": True,
        "entitlements": {"CL": 8, "SL": 8, "EL": 18, "OH": 2, "ML": 0, "PL": 0},
        "requests": [
            ("CL", date(2026, 2, 2), date(2026, 2, 2), LeaveRequest.Status.APPROVED),
            ("EL", date(2026, 8, 17), date(2026, 8, 20), LeaveRequest.Status.APPROVED),
        ],
    },
]


@transaction.atomic
def load_demo_data() -> None:
    seed_holidays()
    from apps.directory.models import Holiday

    holiday_dates = set(Holiday.objects.values_list("date", flat=True))
    for person in PEOPLE:
        user, _created = User.objects.get_or_create(
            username=person["username"],
            defaults={"email": person["email"]},
        )
        user.email = person["email"]
        user.first_name = person["first_name"]
        user.last_name = person["last_name"]
        user.is_staff = person["is_staff"]
        user.is_superuser = person["is_staff"]
        user.set_password(DEMO_PASSWORD)
        user.save()

        employee, _created = Employee.objects.update_or_create(
            user=user,
            defaults={
                "employee_code": person["employee_code"],
                "department": person["department"],
                "job_title": person["job_title"],
                "location": person["location"],
                "date_of_joining": person["date_of_joining"],
                "confirmation_date": person["confirmation_date"],
                "parental_leave_track": person["parental_leave_track"],
                "manager_name": person["manager_name"],
            },
        )
        employee.leave_requests.all().delete()
        employee.leave_balances.all().delete()

        used = {code: Decimal("0") for code in person["entitlements"]}
        pending = {code: Decimal("0") for code in person["entitlements"]}
        for leave_type, start, end, status in person["requests"]:
            days = calculate_leave_days(leave_type, start, end, holiday_dates).deducted_days
            LeaveRequest.objects.create(
                employee=employee,
                leave_type=leave_type,
                start_date=start,
                end_date=end,
                days=days,
                status=status,
            )
            year_bucket = used if status == LeaveRequest.Status.APPROVED else pending
            if status != LeaveRequest.Status.REJECTED:
                year_bucket[leave_type] += days

        for leave_type, entitled in person["entitlements"].items():
            LeaveBalance.objects.create(
                employee=employee,
                leave_type=leave_type,
                year=2026,
                entitled=Decimal(entitled),
                used=used[leave_type],
                pending=pending[leave_type],
            )
