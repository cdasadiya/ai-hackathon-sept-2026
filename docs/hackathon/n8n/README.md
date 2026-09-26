# Nexus Health n8n workflow

Import **`nexus-blood-report-agent.json`** into [hackathonsept2026.app.n8n.cloud](https://hackathonsept2026.app.n8n.cloud/home/workflows).

## Import

1. Sign in to n8n Cloud.
2. **Workflows** → **Add workflow** → **⋮** → **Import from File** → select `nexus-blood-report-agent.json`.
3. Follow the yellow **Setup Notes** sticky on the canvas.

## Credentials

| Credential | Used on | Setup |
|------------|---------|--------|
| **Header Auth** (`Django → n8n Webhook Bearer`) | Webhook node | Name: `Authorization`, Value: `Bearer <same as Django Admin n8n_webhook_secret>` |
| **Google Gemini(PaLM) API** | Gemini Analyze HTTP | API key from [Google AI Studio](https://aistudio.google.com/) |
| *(inline header)* | Django Callback | Replace `REPLACE_CALLBACK_TOKEN` with Django Admin `n8n_callback_token` |

## Django Admin (production)

| Field | Value |
|-------|--------|
| `n8n_blood_report_webhook_url` | **Production** URL from Webhook node (workflow must be **Active**) |
| `n8n_webhook_secret` | Same secret as Webhook Header Auth (without duplicating `Bearer` twice — Django sends `Bearer <secret>`) |
| `n8n_callback_token` | Same token as Django Callback node header |

## Test

1. Wake Render: open `/healthz/`.
2. Upload a **synthetic** lab PDF as demo patient.
3. In n8n **Executions**, confirm success.
4. Doctor appointment → `n8n_status` **DONE** and AI summary visible.

## Production webhook URL shape

`https://hackathonsept2026.app.n8n.cloud/webhook/nexus-blood-report`

(Test URL uses `/webhook-test/` — do not put that in Django Admin.)
