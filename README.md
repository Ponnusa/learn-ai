# Learn-AI

AI-powered visual learning platform. Learn anything, visually.

## Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14 (App Router) + Tailwind + TypeScript |
| Backend | FastAPI (Python) |
| Database | Neon PostgreSQL |
| Storage | Cloudflare R2 |
| Video rendering | GCP Cloud Run (shared with AnimLearn) |
| Auth | Magic link (Resend) + Google OAuth |
| Payments | Stripe |
| Deploy | Vercel (frontend) + Railway (backend) |

## Getting Started

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
cp .env.example .env            # fill in values
uvicorn main:app --reload --port 8000
```

Run migration once against Neon DB:
```bash
psql $DATABASE_URL -f migrations/001_initial.sql
```

### Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local   # set NEXT_PUBLIC_API_URL
npm run dev
```

## Adding a Language

1. Create `frontend/translations/xx.ts` (copy `en.ts`, translate values)
2. Add import + entry in `frontend/translations/index.ts`
3. Add to `LanguageCode` union type

## Enabling Video for a New Subject

```sql
UPDATE feature_flags
SET enabled = TRUE
WHERE feature = 'video_generation' AND subject = 'Biology';
```

## Changing Tier Limits

```sql
-- e.g. give free users 5 videos/day instead of 3
UPDATE tier_config
SET value_int = 5
WHERE tier = 'free' AND feature = 'videos_daily';
```
Changes apply within 5 minutes (cache TTL).

## Syncing AI Prompts from AnimLearn

AnimLearn is the source of truth for all Manim/teaching prompts.
When a prompt is improved in AnimLearn, copy it into:
- `backend/services/manim.py`   (Manim pipeline)
- `backend/services/prompt_builder.py`  (CHAT_SYSTEM_PROMPT, QUIZ_GENERATION_PROMPT)
