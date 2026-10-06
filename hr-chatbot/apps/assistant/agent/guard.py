from __future__ import annotations

import re

from apps.directory.models import Employee


def refusal_reason(employee: Employee, message: str) -> str | None:
    text = message.lower()
    if re.search(r"\b(all employees|every employee|everyone's|list employees|other employees)\b", text):
        if re.search(r"\b(balance|leave|salary|profile|history|record)\b", text):
            return (
                "I can only look at your own HR record. I can't list or compare other employees' leave or personal data."
            )
    for other in Employee.objects.exclude(pk=employee.pk).select_related("user"):
        markers = [
            other.employee_code.lower(),
            other.user.first_name.lower(),
            other.user.last_name.lower(),
            other.user.get_full_name().lower(),
        ]
        if any(marker and marker in text for marker in markers):
            if re.search(r"\b(balance|leave|salary|profile|history|eligible|record|details)\b", text):
                return (
                    "I can only look up leave and profile details on your own record. "
                    "I can't retrieve another employee's information."
                )
    if re.search(r"\b(diagnos(?:e|is)|prescription|symptoms)\b", text):
        return (
            "I can't collect or interpret medical details. I can explain the sick-leave rule and your own sick-leave balance."
        )
    return None
