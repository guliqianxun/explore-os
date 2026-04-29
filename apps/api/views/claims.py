"""Claim list view (per paper)."""
from __future__ import annotations

from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api.serializers import ClaimSerializer
from apps.interpret.models import Claim


class ClaimsView(APIView):
    def get(self, request, arxiv_id: str):
        claims = (
            Claim.objects.filter(paper_arxiv_id=arxiv_id)
            .prefetch_related("evidences", "counter_signals")
            .order_by("claim_id")
        )
        return Response(ClaimSerializer(claims, many=True).data)
