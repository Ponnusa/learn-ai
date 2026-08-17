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
    FRONTEND_URL: str = "http://localhost:3000"
    # Comma-separated extra origins (e.g. old Vercel URL during DNS cutover)
    EXTRA_ALLOWED_ORIGINS: str = ""
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GEMINI_API_KEY: str = ""
    VIDEO_MODEL_PROVIDER: str = "claude"   # "claude" | "gemini"
    GEMINI_MODEL_NAME: str = "gemini-2.5-flash"       # enhanced tier (students)
    GEMINI_MODEL_NAME_LITE: str = "gemini-3.5-flash-lite"  # standard tier (anonymous)
    # Azure OpenAI — set these in EU deployments; when present, all OpenAI calls
    # route through Azure instead of the direct OpenAI API.
    AZURE_OPENAI_ENDPOINT: str = ""
    AZURE_OPENAI_API_KEY: str = ""
    AZURE_OPENAI_API_VERSION: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
