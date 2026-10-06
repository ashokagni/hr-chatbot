from django.core.management.base import BaseCommand

from apps.assistant.agent.vector_store import index_policies


class Command(BaseCommand):
    help = "Embed HR policy markdown into the local Chroma vector database."

    def handle(self, *args, **options):
        count = index_policies()
        self.stdout.write(self.style.SUCCESS(f"Indexed {count} policy sections."))
