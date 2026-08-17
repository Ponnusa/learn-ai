"""
Fix: re-render a video with the correct TTS language.

For single-scene videos: patches the voice string in videos.generated_code and re-queues.
For storyboard videos:   busts the segment cache (deletes generated_assets rows),
                         resets all segments to pending with the correct language,
                         and re-queues.

Usage:
  python video_fi_audiofix.py            # auto-finds latest video
  python video_fi_audiofix.py 171        # target a specific video ID
  python video_fi_audiofix.py 171 fi     # override language (default: read from DB)
"""
import asyncio
import asyncpg
import os
import re
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

LANG_VOICE_MAP = {
    "fi": ("fi-FI-NooraNeural", "fi"),
    "sv": ("sv-SE-SofieNeural", "sv"),
    "es": ("es-ES-ElviraNeural", "es"),
    "ta": ("ta-IN-PallaviNeural", "ta"),
    "en": ("en-US-JennyNeural", "en"),
}
EN_AZURE_VOICE = "en-US-JennyNeural"


def patch_code(code: str, target_lang: str) -> tuple[str, int]:
    azure_voice, gtts_lang = LANG_VOICE_MAP[target_lang]
    before = code
    code = re.sub(rf'voice="{re.escape(EN_AZURE_VOICE)}"', f'voice="{azure_voice}"', code)
    code = re.sub(r'lang="en"', f'lang="{gtts_lang}"', code)
    n = sum(1 for a, b in zip(before, code) if a != b)  # rough diff count
    return code, (0 if code == before else 1)


async def main():
    video_id_arg  = int(sys.argv[1]) if len(sys.argv) > 1 else None
    lang_override = sys.argv[2] if len(sys.argv) > 2 else None

    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    try:
        if video_id_arg:
            row = await conn.fetchrow(
                "SELECT id, language, generated_code, svg_urls FROM videos WHERE id=$1",
                video_id_arg,
            )
        else:
            row = await conn.fetchrow(
                "SELECT id, language, generated_code, svg_urls FROM videos ORDER BY created_at DESC LIMIT 1"
            )

        if not row:
            print("No video found.")
            return

        video_id = row["id"]
        language  = lang_override or row["language"] or "en"
        code      = row["generated_code"] or ""
        svg_urls  = row["svg_urls"] or {}

        print(f"Video {video_id}  language={language!r}  code_len={len(code)}")

        if language not in LANG_VOICE_MAP or language == "en":
            print(f"Language '{language}' does not need a voice fix. Use language override arg if wrong.")
            return

        # ── Detect pipeline type ──────────────────────────────────────────────
        segments = await conn.fetch(
            "SELECT segment_id, prompt_hash FROM video_segments WHERE video_id=$1",
            video_id,
        )
        is_storyboard = len(segments) > 0
        print(f"Pipeline: {'storyboard (%d segments)' % len(segments) if is_storyboard else 'single-scene'}")

        if is_storyboard:
            # ── Bust the segment cache ────────────────────────────────────────
            hashes = [s["prompt_hash"] for s in segments if s["prompt_hash"]]
            if hashes:
                deleted = await conn.execute(
                    f"DELETE FROM generated_assets WHERE prompt_hash = ANY($1::text[])",
                    hashes,
                )
                print(f"Deleted {deleted} cached asset(s) from generated_assets")

            # Reset all segments — worker will re-generate code + re-render
            await conn.execute(
                """UPDATE video_segments SET
                     language=$1,
                     status='pending',
                     clip_url=NULL,
                     generated_code=NULL,
                     generated_class_name=NULL,
                     prompt_hash=NULL,
                     error_message=NULL,
                     retry_count=0,
                     updated_at=NOW()
                   WHERE video_id=$2""",
                language, video_id,
            )
            print(f"Reset {len(segments)} segment(s) to pending with language={language!r}")

        else:
            # Single-scene: patch voice in videos.generated_code
            patched, changed = patch_code(code, language)
            if not changed:
                print("No English voice strings found in generated_code — code may already be correct.")
            else:
                azure_voice, gtts_lang = LANG_VOICE_MAP[language]
                print(f"Patched voice → {azure_voice} / lang={gtts_lang!r}")
                await conn.execute(
                    "UPDATE videos SET generated_code=$1, updated_at=NOW() WHERE id=$2",
                    patched, video_id,
                )

        # ── Re-queue the video ────────────────────────────────────────────────
        await conn.execute(
            "UPDATE videos SET status='queued', error_message=NULL, updated_at=NOW() WHERE id=$1",
            video_id,
        )
        print(f"Video {video_id} → status=queued")

        # ── Trigger Cloud Run renderer ────────────────────────────────────────
        cloud_run_url = os.environ.get("CLOUD_RUN_VIDEO_URL", "")
        token         = os.environ.get("CLOUD_RUN_SECRET", "")
        if cloud_run_url:
            resp = requests.post(
                cloud_run_url,
                json={"job_id": video_id, "svg_urls": svg_urls},
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                timeout=10,
            )
            print(f"Cloud Run triggered: {resp.status_code} {resp.text[:200]}")
        else:
            print("CLOUD_RUN_VIDEO_URL not set — worker will pick up via polling.")

    finally:
        await conn.close()


asyncio.run(main())
