# Nexus Health n8n workflow

Import **`nexus-blood-report-agent.json`** into [hackathonsept2026.app.n8n.cloud](https://hackathonsept2026.app.n8n.cloud/home/workflows).

## How it works

```
Django upload ──POST (Bearer n8n_webhook_secret)──▶ Webhook ─▶ Respond 202 ─▶ Normalize Payload
   ─▶ Download Report File (signed link, 24h) ─▶ Prepare Gemini Request ─▶ IF Download OK
        ├─ yes ─▶ Gemini Analyze HTTP ─▶ Parse AI Summary ─┐
        └─ no ───────────────────────────────────────────┴─▶ Build Callback Body
   ─▶ Django Callback ──POST (Bearer n8n_callback_token)──▶ /api/n8n/health-report-callback/
```

- Every failure (download error, expired link, unsupported file, Gemini quota/error, unparseable reply) is reported back with `"status": "FAILED"` and an explanation in `ai_summary.limitations`, so reports never stay stuck in **PROCESSING**.
- Download, Gemini and callback nodes retry (3, 3 and 5 tries, 5 s apart), which covers Render cold starts.
- Gemini is called with `responseSchema`, so the reply is always the JSON shape below.

## Import

1. Sign in to n8n Cloud.
2. **Workflows** → **Add workflow** → **⋮** → **Import from File** → select `nexus-blood-report-agent.json`.
3. Attach the three credentials below (the canvas shows a warning on each node until you do).
4. **Publish** the workflow. A draft workflow only answers on the `/webhook-test/` URL while the editor is listening.

## Credentials

| Credential (type) | Node | Fields |
|-------------------|------|--------|
| **Django → n8n Webhook Bearer** (Header Auth) | Webhook Nexus Blood Report | Name `Authorization`, Value `Bearer <n8n_webhook_secret>` |
| **Google Gemini(PaLM) API** | Gemini Analyze HTTP | API key from [Google AI Studio](https://aistudio.google.com/); keep the default host |
| **n8n → Django Callback Bearer** (Header Auth) | Django Callback | Name `Authorization`, Value `Bearer <n8n_callback_token>` |

Django sends `Authorization: Bearer <secret>`, so the Header Auth value must include the `Bearer ` prefix. The Django Callback node no longer carries an inline `REPLACE_CALLBACK_TOKEN` header; if your copy still has one, delete it and use the credential.

The Gemini node calls `gemini-flash-latest`. To pin a model, edit the URL (for example `.../models/gemini-2.5-flash:generateContent`).

## Django Admin → Integration Configuration

| Field | Value |
|-------|-------|
| `n8n_blood_report_webhook_url` | **Production** URL: `https://hackathonsept2026.app.n8n.cloud/webhook/nexus-blood-report` (not `/webhook-test/`) |
| `n8n_webhook_secret` | The secret only (no `Bearer ` prefix) |
| `n8n_callback_token` | The token only (no `Bearer ` prefix) |

If Django is not on `https://ai-hackathon-sept-2026.onrender.com`, change the **Django Callback** URL.

## Contract

Webhook body sent by Django:

```json
{
  "blood_report_id": 42,
  "patient_id": 7,
  "patient_email": "patient@example.com",
  "drive_link": "https://<app>/reports/42/download/?sig=<signed>",
  "filename": "7_report_ab12cd34.pdf",
  "mime_type": "application/pdf",
  "appointment_id": "APT-2026-000123"
}
```

`patient_id` and `appointment_id` may be `null`.

Callback body sent by n8n:

```json
{
  "blood_report_id": 42,
  "patient_id": 7,
  "status": "DONE",
  "health_report_drive_file_id": "nexus-local-42",
  "health_report_drive_link": "https://<app>/reports/42/download/",
  "ai_summary": {
    "clinician_bullets": ["..."],
    "abnormal_flags": [{"test": "Haemoglobin", "value": "10.2 g/dL", "note": "Clinician to confirm."}],
    "confidence": "medium",
    "limitations": "",
    "disclaimer": "AI-generated draft for clinician review only. Not a diagnosis.",
    "model": "gemini-..."
  }
}
```

With `"status": "FAILED"` Django marks the report **FAILED**, stores `ai_summary` as the report's AI analysis and does not create a HealthReport.

## Report status in Django

| Status | Meaning |
|--------|---------|
| PENDING | No webhook URL configured, so the report was never sent |
| PROCESSING | n8n accepted the webhook; waiting for the callback |
| DONE | Callback received with an AI summary |
| FAILED | n8n was unreachable, or the workflow reported a failure |

## Verify

1. Wake Render: open `/healthz/`.
2. Upload a **synthetic** lab PDF (e.g. `sample data/cbc-report-format.pdf`) as a demo patient, or on the Render shell run:

   ```bash
   python manage.py send_report_to_n8n <report_id>   # one report, prints n8n's reply
   python manage.py send_report_to_n8n --stuck       # every PENDING/FAILED report
   python manage.py send_report_to_n8n 42 --dry-run  # show the payload only
   ```

3. In n8n **Executions**, confirm the run is green.
4. The report shows **DONE** and the AI summary on the doctor's appointment page.
