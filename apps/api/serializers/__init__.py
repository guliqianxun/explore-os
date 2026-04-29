"""ft-022 + ft-034 P0-6: DRF serializers — split into sub-modules.

Old single-file ``apps/api/serializers.py`` was 184 lines; ft-034 P0-6 splits
it into per-domain modules (papers / claims / materials / jobs / equations /
subscriptions) and re-exports them here for backwards-compat. External
``from apps.api.serializers import XxxSerializer`` keeps working.
"""
from __future__ import annotations

from apps.api.serializers.claims import (
    ClaimEvidenceSerializer,
    ClaimSerializer,
    CounterSignalSerializer,
)
from apps.api.serializers.equations import EquationSerializer
from apps.api.serializers.jobs import JobSerializer
from apps.api.serializers.materials import (
    CitationSerializer,
    FigureSerializer,
    SectionSerializer,
    TableSerializer,
)
from apps.api.serializers.papers import (
    BacklinkSerializer,
    CommentSerializer,
    PaperListItemSerializer,
)
from apps.api.serializers.subscriptions import SubscriptionSerializer

__all__ = [
    # claims
    "ClaimEvidenceSerializer",
    "ClaimSerializer",
    "CounterSignalSerializer",
    # materials
    "CitationSerializer",
    "EquationSerializer",
    "FigureSerializer",
    "SectionSerializer",
    "TableSerializer",
    # papers / user_*
    "BacklinkSerializer",
    "CommentSerializer",
    "PaperListItemSerializer",
    # jobs
    "JobSerializer",
    # subscriptions
    "SubscriptionSerializer",
]
