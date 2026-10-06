from django.core.management.base import BaseCommand

from apps.directory.demo_data import DEMO_PASSWORD, load_demo_data


class Command(BaseCommand):
    help = "Load fictional Northstar employees, leave balances, and holidays into Postgres."

    def handle(self, *args, **options):
        load_demo_data()
        self.stdout.write(self.style.SUCCESS(f"Demo data loaded. Password for every demo account: {DEMO_PASSWORD}"))
