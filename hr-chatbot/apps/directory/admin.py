from django.contrib import admin

from apps.directory.models import AccessAuditLog, Employee, Holiday, LeaveBalance, LeaveRequest


class LeaveBalanceInline(admin.TabularInline):
    model = LeaveBalance
    extra = 0


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("employee_code", "user", "department", "location", "date_of_joining", "confirmation_date")
    search_fields = ("employee_code", "user__first_name", "user__last_name", "department")
    inlines = [LeaveBalanceInline]


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ("employee", "leave_type", "start_date", "end_date", "days", "status")
    list_filter = ("leave_type", "status")


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ("date", "name")


@admin.register(AccessAuditLog)
class AccessAuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "employee", "tool_name")
    readonly_fields = ("created_at", "employee", "tool_name")
