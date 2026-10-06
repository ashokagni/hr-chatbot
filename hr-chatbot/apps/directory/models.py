from django.conf import settings
from django.db import models


class Employee(models.Model):
    class ParentalTrack(models.TextChoices):
        MATERNITY = "maternity", "Maternity"
        PATERNITY = "paternity", "Paternity"
        NONE = "none", "None"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="employee",
    )
    employee_code = models.CharField(max_length=20, unique=True)
    department = models.CharField(max_length=80)
    job_title = models.CharField(max_length=80)
    location = models.CharField(max_length=80)
    date_of_joining = models.DateField()
    confirmation_date = models.DateField(null=True, blank=True)
    parental_leave_track = models.CharField(
        max_length=20,
        choices=ParentalTrack.choices,
        default=ParentalTrack.NONE,
    )
    manager_name = models.CharField(max_length=120, blank=True)

    def __str__(self) -> str:
        return f"{self.employee_code} {self.user.get_full_name()}"


class LeaveBalance(models.Model):
    employee = models.ForeignKey(Employee, related_name="leave_balances", on_delete=models.CASCADE)
    leave_type = models.CharField(max_length=8)
    year = models.PositiveIntegerField()
    entitled = models.DecimalField(max_digits=6, decimal_places=1)
    used = models.DecimalField(max_digits=6, decimal_places=1, default=0)
    pending = models.DecimalField(max_digits=6, decimal_places=1, default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "leave_type", "year"],
                name="unique_leave_balance",
            )
        ]

    @property
    def remaining(self):
        return self.entitled - self.used - self.pending


class LeaveRequest(models.Model):
    class Status(models.TextChoices):
        APPROVED = "approved", "Approved"
        PENDING = "pending", "Pending"
        REJECTED = "rejected", "Rejected"

    employee = models.ForeignKey(Employee, related_name="leave_requests", on_delete=models.CASCADE)
    leave_type = models.CharField(max_length=8)
    start_date = models.DateField()
    end_date = models.DateField()
    days = models.DecimalField(max_digits=6, decimal_places=1)
    status = models.CharField(max_length=20, choices=Status.choices)

    class Meta:
        ordering = ["-start_date"]


class Holiday(models.Model):
    date = models.DateField(unique=True)
    name = models.CharField(max_length=80)

    class Meta:
        ordering = ["date"]

    def __str__(self) -> str:
        return f"{self.date.isoformat()} {self.name}"


class AccessAuditLog(models.Model):
    employee = models.ForeignKey(Employee, related_name="access_logs", on_delete=models.CASCADE)
    tool_name = models.CharField(max_length=80)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
