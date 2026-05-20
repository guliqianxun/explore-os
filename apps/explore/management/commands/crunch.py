"""Manual crunch trigger."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.explore.crunch import run_crunch


class Command(BaseCommand):
    help = "Run Explore daily crunch: compute A, C, snapshot, detect gaps."

    def add_arguments(self, parser):
        parser.add_argument("--user", type=int, default=1,
                            help="User ID (default: 1 for single-user desktop)")

    def handle(self, *args, **options):
        user_id = options["user"]
        summary = run_crunch(user_id=user_id)
        self.stdout.write(self.style.SUCCESS(
            f"Crunch done: {summary['topics']} topics, "
            f"{summary['gaps_prereq']} prereq gaps, "
            f"{summary['gaps_decay']} decay gaps "
            f"(ts={summary['ts']})"
        ))
