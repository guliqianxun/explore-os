"""ft-021: RenderArtifact 落库（幂等）.

artifact_id 规则：``<arxiv_id>:graph_<format>``。同 paper + 同 format 多次
``persist_artifact`` 行数不变（``update_or_create`` by primary key）。
"""
from __future__ import annotations

import logging
from pathlib import Path

from apps.render.models import RenderArtifact

log = logging.getLogger(__name__)


def persist_artifact(
    arxiv_id: str,
    fmt: str,
    payload_path: Path | str,
    payload_meta: dict | None = None,
) -> RenderArtifact:
    """落库单条 RenderArtifact，幂等。

    :param fmt: 'excalidraw' / 'svg'
    """
    artifact_id = f"{arxiv_id}:graph_{fmt}"
    artifact_type = f"graph_{fmt}"
    obj, created = RenderArtifact.objects.update_or_create(
        artifact_id=artifact_id,
        defaults={
            "paper_arxiv_id": arxiv_id,
            "artifact_type": artifact_type,
            "payload_path": str(payload_path),
            "payload_meta": payload_meta or {},
        },
    )
    log.info(
        "[render.persist] %s artifact_id=%s path=%s",
        "created" if created else "updated", artifact_id, payload_path,
    )
    return obj
