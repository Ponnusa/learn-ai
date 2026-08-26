from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    OPENAI_API_KEY: str
    ANTHROPIC_API_KEY: str
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 720
    RESEND_API_KEY: str = ""
    FROM_EMAIL: str = "noreply@learn-ai.com"
    APP_URL: str = "http://localhost:3000"
    # This backend's OWN public URL — distinct from APP_URL above (that's the
    # main frontend's URL, used only for magic-link redirect targets). Needed
    # for building links that must resolve back to this server itself, e.g.
    # the media proxy in developer_api.py.
    BACKEND_PUBLIC_URL: str = "http://localhost:8000"
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = "learnai-storage"
    R2_PUBLIC_URL: str = ""
    CLOUD_RUN_VIDEO_URL: str = ""
    CLOUD_RUN_SECRET: str = ""
    MANIM_VERSION: str = "0.19.2"
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_LEARNER_PRICE_ID: str = ""
    STRIPE_PRO_PRICE_ID: str = ""
    FRONTEND_URL: str = "https://www.learnx-ai.com"
    # Comma-separated extra origins (e.g. old Vercel URL during DNS cutover)
    EXTRA_ALLOWED_ORIGINS: str = ""
    # The video-api app's own URL — the only value MagicLinkRequest.redirect_base
    # is ever honored against (see auth.py); anything else silently falls back
    # to APP_URL, so this can never become an open redirect for the magic link.
    VIDEO_API_URL: str = "http://localhost:3001"
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GEMINI_API_KEY: str = ""
    # Azure OpenAI — set USE_AZURE_OPENAI=true in EU deployments to route all
    # OpenAI calls through Azure instead of the direct OpenAI API.
    USE_AZURE_OPENAI: bool = False
    AZURE_OPENAI_ENDPOINT: str = ""
    AZURE_OPENAI_API_KEY: str = ""
    AZURE_OPENAI_API_VERSION: str = ""
    # Vertex AI Gemini — set USE_VERTEX_GEMINI=true in EU deployments to route all
    # Claude calls through Gemini on Vertex AI (europe-west1) instead of Anthropic.
    # US deployments leave this false and use Claude via Anthropic API.
    USE_VERTEX_GEMINI: bool = False
    VERTEX_PROJECT: str = ""
    VERTEX_LOCATION: str = "europe-west1"
    GOOGLE_SERVICE_ACCOUNT_JSON: str = ""  # full JSON content of the service account key

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
