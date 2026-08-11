"""Pydantic models for the multi-modal lesson segment pipeline."""
from typing import Literal, Optional

from pydantic import BaseModel, Field

SegmentType = Literal["manim", "image", "video"]
SegmentStatus = Literal["pending", "generating", "rendered", "failed"]


class Segment(BaseModel):
    id: str
    order: int
    type: SegmentType
    target_duration_seconds: float
    actual_duration_seconds: Optional[float] = None
    subject_area: str
    # Denormalized from the parent Storyboard so any renderer can produce a
    # correctly-sized clip from just a Segment, without needing the Storyboard
    # object too — the compositor (Sprint 4) needs every clip at one consistent
    # resolution/fps to concat without a surprise re-encode.
    aspect_ratio: str = "16:9"
    narration_text: str
    generation_prompt: str

    # References another segment's `id` in the SAME storyboard whose generated
    # asset should be passed as a style/composition reference. Resolved to a
    # real local file/asset at render time (segments render in order, so by
    # the time segment N renders, any earlier segment it references already
    # has a real asset) — never a literal URL at storyboard-generation time,
    # because no assets exist yet when the storyboard is written.
    style_reference_segment_id: Optional[str] = None

    # Populated by the renderers, never by the storyboard step.
    source_asset_url: Optional[str] = None   # still image / SVG, whatever QA validates
    clip_url: Optional[str] = None           # final N-second mp4 fed to the compositor
    generated_code: Optional[str] = None     # manim segments only — the actual rendered Python

    # Set by unified Manim codegen (orchestrator pre-generation pass) so
    # ManimRenderer.render() knows which class to render from the shared file
    # without re-parsing the code. None means single-segment path was used.
    generated_class_name: Optional[str] = None

    language: str = "en"

    status: SegmentStatus = "pending"
    retry_count: int = 0
    error_message: Optional[str] = None
    prompt_hash: Optional[str] = None        # cache key for asset_manifest (Sprint 2+)


class Storyboard(BaseModel):
    lesson_id: str
    target_duration_seconds: int
    subject_area: str
    aspect_ratio: str = "16:9"
    language: str = "en"
    segments: list[Segment] = Field(default_factory=list)
