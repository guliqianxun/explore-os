"""Bootstrap topic taxonomy from paper keywords."""

from __future__ import annotations

from collections import Counter

from django.core.management.base import BaseCommand

from apps.explore.models import ExploreTopic
from apps.papers.models import Paper, PaperBrief


class Command(BaseCommand):
    help = "Seed ExploreTopic from paper.keywords + brief.keywords."

    def handle(self, *args, **options):
        keyword_counter: Counter = Counter()

        # Collect from Paper.keywords
        for paper in Paper.objects.exclude(keywords__exact=[]).only("keywords", "abstract"):
            for kw in paper.keywords or []:
                keyword_counter[kw.lower().strip()] += 1

        # Collect from PaperBrief.keywords
        for brief in PaperBrief.objects.exclude(keywords__exact=[]).only("keywords"):
            for kw in brief.keywords or []:
                keyword_counter[kw.lower().strip()] += 1

        created = 0
        for keyword, count in keyword_counter.most_common(200):
            topic_id = keyword.replace(" ", "-").replace("_", "-")
            _, is_new = ExploreTopic.objects.get_or_create(
                topic_id=topic_id,
                defaults={
                    "name": keyword,
                    "aliases": [],
                    "source": "keyword",
                },
            )
            if is_new:
                created += 1

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {created} new topics (from {len(keyword_counter)} unique keywords)"
        ))
