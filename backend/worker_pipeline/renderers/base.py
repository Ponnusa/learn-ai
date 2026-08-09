"""Shared renderer contract — every modality (manim/image/video) implements this
so the compositor (Sprint 4) can treat their output identically regardless of
which tool produced it."""
from abc import ABC, abstractmethod

from ..asset_manifest import AssetRef
from ..schema import Segment


class Renderer(ABC):
    @abstractmethod
    def render(self, segment: Segment) -> AssetRef:
        """
        Render `segment` and return the AssetRef for its final clip.

        Implementations MUST mutate `segment` in place (status, clip_url,
        source_asset_url, actual_duration_seconds, error_message, retry_count)
        so a caller holding the same Segment object can persist it directly —
        this mirrors how the DB row gets updated once ported to the worker
        (Sprint 6), where the segment IS the DB row.
        """
        raise NotImplementedError
