"""
Lightweight subject detection — runs in parallel with main AI call.
Uses gpt-4o-mini only. Never blocks or changes the main response.
"""
import json
from services.ai_router import openai_client, get_model

SUBJECT_MAP = {
    "Mathematics":            ["Algebra","Calculus","Geometry","Trigonometry","Statistics",
                               "Number Theory","Linear Algebra","Differential Equations","Probability"],
    "Physics":                ["Mechanics","Thermodynamics","Electromagnetism","Quantum Physics",
                               "Optics","Relativity","Fluid Dynamics","Nuclear Physics"],
    "Chemistry":              ["Organic Chemistry","Inorganic Chemistry","Physical Chemistry",
                               "Biochemistry","Analytical Chemistry","Electrochemistry"],
    "Biology":                ["Cell Biology","Genetics","Ecology","Anatomy","Microbiology",
                               "Evolution","Neuroscience","Botany"],
    "Computer Science":       ["Programming","Algorithms","Data Structures","Machine Learning",
                               "Networking","Databases","Operating Systems","Cybersecurity"],
    "History":                ["Ancient History","Medieval History","Modern History",
                               "World War","Civilizations"],
    "Geography":              ["Physical Geography","Human Geography","Climatology","Cartography"],
    "Economics":              ["Microeconomics","Macroeconomics","Finance","Game Theory","Econometrics"],
    "Literature":             ["Poetry","Fiction","Drama","Literary Analysis","Rhetoric"],
    "Language & Linguistics": ["Grammar","Phonetics","Semantics","Writing","Morphology"],
    "Philosophy":             ["Ethics","Logic","Epistemology","Metaphysics","Political Philosophy"],
    "Psychology":             ["Cognitive Psychology","Behavioral Psychology",
                               "Developmental Psychology","Social Psychology"],
    "Engineering":            ["Mechanical","Electrical","Civil","Chemical","Software Engineering"],
    "Medicine & Health":      ["Anatomy","Pharmacology","Pathology","Nutrition","Public Health"],
    "Business":               ["Marketing","Management","Accounting","Entrepreneurship","Strategy"],
    "Art & Design":           ["Art History","Drawing","Color Theory","Typography","Architecture"],
    "Music":                  ["Music Theory","Harmony","Rhythm","Composition","Instruments"],
    "Law":                    ["Constitutional Law","Criminal Law","Contract Law","International Law"],
    "Environmental Science":  ["Climate Science","Ecosystems","Conservation","Sustainability"],
    "Other":                  ["General Knowledge","Interdisciplinary"],
}

SUBJECT_NAMES = list(SUBJECT_MAP.keys())

SUBJECT_ICONS = {
    "Mathematics":            "📐",
    "Physics":                "⚛️",
    "Chemistry":              "🧪",
    "Biology":                "🧬",
    "Computer Science":       "💻",
    "History":                "📜",
    "Geography":              "🌍",
    "Economics":              "📈",
    "Literature":             "📖",
    "Language & Linguistics": "🗣️",
    "Philosophy":             "🤔",
    "Psychology":             "🧠",
    "Engineering":            "⚙️",
    "Medicine & Health":      "🏥",
    "Business":               "💼",
    "Art & Design":           "🎨",
    "Music":                  "🎵",
    "Law":                    "⚖️",
    "Environmental Science":  "🌱",
    "Other":                  "📚",
}

_SYSTEM = (
    "You are a subject classifier for an educational platform.\n"
    "Given text or an image, identify the academic subject and subtopic.\n"
    "Return ONLY valid JSON. No explanation. No markdown.\n"
    'Format: {"subject": "Physics", "subtopic": "Newton\'s Laws", "confidence": 0.95}\n'
    f"Subject must be one of: {', '.join(SUBJECT_NAMES)}\n"
    "If unsure, set confidence below 0.6 and subject to \"Other\"."
)


async def detect_subject(
    text: str = "",
    image_url: str | None = None,
    pdf_excerpt: str = "",
) -> dict:
    """
    Run in parallel with main chat call via asyncio.gather().
    Returns {"subject", "subtopic", "confidence"} or {} on any failure.
    """
    content_text = (text or pdf_excerpt)[:800]
    if not content_text and not image_url:
        return {}

    try:
        if image_url:
            user_content = [
                {"type": "image_url", "image_url": {"url": image_url, "detail": "low"}},
                {"type": "text", "text": content_text or "What academic subject is shown?"},
            ]
        else:
            user_content = content_text

        resp = await openai_client.chat.completions.create(
            model=get_model("subject_detection"),
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user",   "content": user_content},
            ],
            max_tokens=80,
            temperature=0,
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content)
        if data.get("subject") not in SUBJECT_MAP:
            data["subject"] = "Other"
        data["icon"] = SUBJECT_ICONS.get(data["subject"], "📚")
        return data
    except Exception:
        return {}
