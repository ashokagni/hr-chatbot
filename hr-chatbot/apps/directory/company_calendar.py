from datetime import date

# Northstar's published holiday list. The same dates are seeded into Postgres
# and repeated in policies/holiday-and-attendance.md so retrieval and the
# holiday tool stay aligned.
HOLIDAYS: list[tuple[date, str]] = [
    (date(2026, 1, 1), "New Year"),
    (date(2026, 1, 26), "Republic Day"),
    (date(2026, 3, 4), "Holi"),
    (date(2026, 5, 1), "Labour Day"),
    (date(2026, 8, 15), "Independence Day"),
    (date(2026, 10, 2), "Gandhi Jayanti"),
    (date(2026, 10, 20), "Dussehra"),
    (date(2026, 11, 9), "Diwali"),
    (date(2026, 12, 25), "Christmas"),
    (date(2027, 1, 1), "New Year"),
    (date(2027, 1, 26), "Republic Day"),
]
