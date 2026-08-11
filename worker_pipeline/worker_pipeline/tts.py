"""
Narration TTS for image/video segments.

Manim segments already get narration baked in via manim_voiceover's
AzureService running INSIDE the Docker render (learnai/worker.py's docker run
passes AZURE_SPEECH_KEY/AZURE_SPEECH_REGION into the container, renamed to
AZURE_SUBSCRIPTION_KEY/AZURE_SERVICE_REGION for manim_voiceover's benefit —
see worker.py's docker cmd construction). Image and video segments' clips
(Ken Burns / Veo) don't go through Manim at all, so they need their own
narration step — this module calls Azure Speech directly, using the SAME
voice, so the narrator doesn't change between a Manim segment and an image
segment in the same lesson.

Env vars here use the CANONICAL outer-app names (AZURE_SPEECH_KEY /
AZURE_SPEECH_REGION), not the Docker-container-renamed
AZURE_SUBSCRIPTION_KEY/AZURE_SERVICE_REGION — this code runs outside Docker.

Deliberate design note: TTS failure is meant to be the one true hard-fail
case in this pipeline (per the retry/degrade policy in orchestrator.py) —
there is no silent "ship it without narration" fallback anywhere. This falls
out naturally rather than needing special-case code: orchestrator.py's
held-frame degrade path ALSO calls generate_narration_audio(), so if Azure
Speech is genuinely down, the degrade path fails too and the failure
correctly propagates all the way up instead of being swallowed.

NOTE ON VERIFICATION: like the Gemini calls elsewhere in this pipeline, the
azure-cognitiveservices-speech call shape below is written from the SDK's
documented shape but UNVERIFIED against a live call — no AZURE_SPEECH_KEY is
set on this dev machine.
"""
import logging
import os
import subprocess

logger = logging.getLogger(__name__)

AZURE_SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY")
AZURE_SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION", "swedencentral")
AZURE_VOICE_NAME = os.getenv("AZURE_VOICE_NAME", "en-US-JennyNeural")

LANGUAGE_VOICE_MAP: dict = {
    "en": "en-US-JennyNeural",
    "fi": "fi-FI-NooraNeural",
    "sv": "sv-SE-SofieNeural",
    "de": "de-DE-KatjaNeural",
    "fr": "fr-FR-DeniseNeural",
    "es": "es-ES-ElviraNeural",
    "it": "it-IT-ElsaNeural",
    "nl": "nl-NL-ColetteNeural",
    "pt": "pt-PT-RaquelNeural",
    "ar": "ar-SA-ZariyahNeural",
    "zh": "zh-CN-XiaoxiaoNeural",
    "ja": "ja-JP-NanamiNeural",
    "ko": "ko-KR-SunHiNeural",
    "ru": "ru-RU-SvetlanaNeural",
    "pl": "pl-PL-ZofiaNeural",
    "tr": "tr-TR-EmelNeural",
    "hi": "hi-IN-SwaraNeural",
}


def voice_for_language(lang: str) -> str:
    base = lang.split("-")[0].lower() if lang else "en"
    return LANGUAGE_VOICE_MAP.get(base, AZURE_VOICE_NAME)


def generate_narration_audio(text: str, output_path: str, voice_name: str = AZURE_VOICE_NAME) -> None:
    """
    Synthesize `text` to speech and write it to output_path (wav).
    Raises if credentials are missing or synthesis fails — never writes a
    silent/placeholder audio file, per the hard-fail design above.
    """
    if not AZURE_SPEECH_KEY:
        raise RuntimeError("AZURE_SPEECH_KEY not set — cannot generate narration audio")

    import azure.cognitiveservices.speech as speechsdk

    speech_config = speechsdk.SpeechConfig(subscription=AZURE_SPEECH_KEY, region=AZURE_SPEECH_REGION)
    speech_config.speech_synthesis_voice_name = voice_name
    audio_config = speechsdk.audio.AudioOutputConfig(filename=output_path)
    synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)

    result = synthesizer.speak_text_async(text).get()
    if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
        cancellation = getattr(result, "cancellation_details", None)
        reason = cancellation.reason if cancellation else result.reason
        raise RuntimeError(f"Azure TTS synthesis failed: {reason}")
    if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        raise RuntimeError("Azure TTS produced an empty audio file")


def get_media_duration(path: str) -> float:
    """ffprobe-based duration lookup (works for audio or video files),
    mirroring learnai/worker.py's get_video_duration()."""
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    except FileNotFoundError:
        raise RuntimeError("ffprobe not found on PATH — required to measure media duration")
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError(f"Failed to get media duration: {result.stderr}")
    return float(result.stdout.strip())


def mux_audio_onto_video(video_path: str, audio_path: str, output_path: str) -> None:
    """
    Replace video_path's audio track (silent Ken Burns track, or whatever Veo
    generated) with audio_path, trimming to the shorter of the two via
    -shortest so neither track runs past the other's end.
    """
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path, "-i", audio_path,
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
        "-shortest",
        output_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except FileNotFoundError:
        raise RuntimeError("ffmpeg not found on PATH — required to mux narration audio")
    if result.returncode != 0:
        raise RuntimeError(f"Failed to mux narration audio:\n{result.stderr[-500:]}")
    if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        raise RuntimeError("Muxed output is missing or empty")
