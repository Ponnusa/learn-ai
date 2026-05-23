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
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_LEARNER_PRICE_ID: str = ""
    STRIPE_PRO_PRICE_ID: str = ""
    FRONTEND_URL: str = "http://localhost:3000"
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
