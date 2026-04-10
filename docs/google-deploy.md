# Magnio Google Stack Deploy

Target project: `magnio-rtdb`

## Stack

- Frontend: Firebase Hosting
- Backend: Cloud Run
- Lead ops data: Firebase Realtime Database
- Chat analytics data: Firestore
- Secrets: Secret Manager

Magnio on Google Cloud is not just the `/chat` surface. The deployed stack also supports:

- website lead capture through `/lead`
- admin lead triage through `/#admin`
- Resend-based admin and lead emails
- Cal.com webhook ingestion through `/webhooks/calcom`
- Firestore-backed chat evaluation logging

This setup does not require GitHub first. You can deploy directly from your local checkout with `gcloud run deploy` and `firebase deploy`.

## 1. Backend secrets

Create secrets for:

- `MAGNIO_OPENROUTER_API_KEY`
- `RESEND_API_KEY`
- `CALCOM_WEBHOOK_SECRET`
- `SLACK_WEBHOOK_URL`
- `TASKS_API_TOKEN`

Recommended values:

- `MAGNIO_CHAT_ANALYTICS_BACKEND=firestore`
- `MAGNIO_CHAT_JUDGE_MODEL=openai/gpt-5.1`
- `MAGNIO_CHAT_ADVISOR_MODEL=anthropic/claude-sonnet-4.6`
- `MAGNIO_CHAT_JUDGE_PROVIDER=openrouter`
- `MAGNIO_CHAT_ADVISOR_PROVIDER=openrouter`
- `GOOGLE_CLOUD_PROJECT=magnio-rtdb`
- `GOOGLE_CLOUD_LOCATION=global`
- `CORS_ALLOW_ORIGINS=https://magnio-rtdb.web.app,https://magnio.io,https://www.magnio.io`
- `FIREBASE_DATABASE_URL=https://magnio-rtdb-default-rtdb.firebaseio.com/`
- `RESEND_FROM_EMAIL=hello@magnio.io`
- `RESEND_TO_EMAIL=hello@magnio.io`
- `RESEND_LEAD_AUTOREPLY_ENABLED=1`
- `MAGNIO_ENV=prod`

## 2. Build and deploy API to Cloud Run

First-time setup:

```bash
gcloud config set project magnio-rtdb
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com firebasehosting.googleapis.com aiplatform.googleapis.com
```

Create required secrets:

```bash
printf '%s' 'YOUR_OPENROUTER_KEY' | gcloud secrets create MAGNIO_OPENROUTER_API_KEY --data-file=-
printf '%s' 'YOUR_RESEND_KEY' | gcloud secrets create RESEND_API_KEY --data-file=-
printf '%s' 'YOUR_CALCOM_SECRET' | gcloud secrets create CALCOM_WEBHOOK_SECRET --data-file=-
printf '%s' 'YOUR_TASKS_API_TOKEN' | gcloud secrets create TASKS_API_TOKEN --data-file=-
```

If the secret already exists, update it:

```bash
printf '%s' 'YOUR_OPENROUTER_KEY' | gcloud secrets versions add MAGNIO_OPENROUTER_API_KEY --data-file=-
printf '%s' 'YOUR_RESEND_KEY' | gcloud secrets versions add RESEND_API_KEY --data-file=-
printf '%s' 'YOUR_CALCOM_SECRET' | gcloud secrets versions add CALCOM_WEBHOOK_SECRET --data-file=-
printf '%s' 'YOUR_TASKS_API_TOKEN' | gcloud secrets versions add TASKS_API_TOKEN --data-file=-
```

Use a runtime service account with access to:

- Firestore
- Realtime Database
- Vertex AI User
- Secret Manager secret accessor

```bash
gcloud run deploy magnio-api \
  --image gcr.io/magnio-rtdb/magnio-api \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --port 8080 \
  --cpu 1 \
  --memory 1Gi \
  --min-instances 0 \
  --max-instances 5 \
  --timeout 120s \
  --service-account firebase-adminsdk-fbsvc@magnio-rtdb.iam.gserviceaccount.com \
  --set-env-vars "^~^MAGNIO_CHAT_ANALYTICS_BACKEND=firestore~MAGNIO_CHAT_JUDGE_MODEL=openai/gpt-5.1~MAGNIO_CHAT_ADVISOR_MODEL=anthropic/claude-sonnet-4.6~MAGNIO_CHAT_JUDGE_PROVIDER=openrouter~MAGNIO_CHAT_ADVISOR_PROVIDER=openrouter~GOOGLE_CLOUD_PROJECT=magnio-rtdb~GOOGLE_CLOUD_LOCATION=global~CORS_ALLOW_ORIGINS=https://magnio-rtdb.web.app,https://magnio.io,https://www.magnio.io,http://localhost:5173~FIREBASE_DATABASE_URL=https://magnio-rtdb-default-rtdb.firebaseio.com/~RESEND_FROM_EMAIL=hello@magnio.io~RESEND_TO_EMAIL=hello@magnio.io~RESEND_LEAD_AUTOREPLY_ENABLED=1~MAGNIO_ENV=prod" \
  --set-secrets MAGNIO_OPENROUTER_API_KEY=MAGNIO_OPENROUTER_API_KEY:latest,RESEND_API_KEY=RESEND_API_KEY:latest,CALCOM_WEBHOOK_SECRET=CALCOM_WEBHOOK_SECRET:latest,TASKS_API_TOKEN=TASKS_API_TOKEN:latest,SLACK_WEBHOOK_URL=SLACK_WEBHOOK_URL:latest
```

To switch the advisory path and the judge to Vertex AI for demos or interviews, update these env vars and redeploy:

```bash
MAGNIO_CHAT_ADVISOR_PROVIDER=vertex
MAGNIO_CHAT_JUDGE_PROVIDER=vertex
MAGNIO_CHAT_VERTEX_ADVISOR_MODEL=gemini-2.5-flash
MAGNIO_CHAT_VERTEX_JUDGE_MODEL=gemini-2.5-flash
GOOGLE_CLOUD_PROJECT=magnio-rtdb
GOOGLE_CLOUD_LOCATION=global
```

That change keeps the original OpenRouter arena implementation in the codebase so you can switch back without reverting code.

## 3. Verify backend

```bash
curl https://magnio.io/api/chat/health
```

Expect:

- `ok: true`
- `openrouterConfigured: true`
- `analyticsDbPath: firestore`

Lead workflow checks:

```bash
curl -sS https://magnio.io/admin/leads?limit=5 -H 'x-task-token: YOUR_TASKS_API_TOKEN'
```

Expect:

- `200 OK`
- lead rows load successfully

Webhook check:

- configure Cal.com to call `https://magnio.io/webhooks/calcom`
- set the matching `CALCOM_WEBHOOK_SECRET`

## 4. Deploy frontend to Firebase Hosting

Build:

```bash
npm install
npm run build
```

Deploy:

```bash
firebase use magnio-rtdb
firebase deploy --only hosting
```

Before building, update `.env.production` to use the same-domain backend:

```env
VITE_API_BASE_URL=https://magnio.io
```

## 5. Domains

Point:

- `magnio.io`
- `www.magnio.io`

to Firebase Hosting.

Keep API behind the same domain through Hosting rewrites.

## 6. Post-deploy checks

- `/`
- `/chat`
- `/#admin`
- backend `/api/chat/health`
- one lead form submission
- one admin panel load with `TASKS_API_TOKEN`
- one Resend delivery check
- one Cal.com webhook test
- one Arena run
- one Advisor run
- one review submission
- Firestore write confirmation

## 7. Recommended next hardening

- Cloud Run service account with least privilege
- Secret Manager for all runtime secrets
- Budget alert in Google Cloud
- Log-based alert for repeated lead email failures
- Log-based alert for repeated Cal.com signature failures
- Log-based alert for repeated `All arena model calls failed`
