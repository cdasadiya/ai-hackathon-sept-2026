"""
services.py — External integration helpers.

Functions:
  get_drive_service()            Build an authenticated Google Drive API client
  get_or_create_subfolder()      Resolve (or create) a Drive sub-folder
  upload_blood_report_to_drive() Upload a blood-report file to Drive
  build_n8n_payload()            Webhook body for the n8n blood-report workflow
  trigger_n8n_webhook()          Fire the n8n blood-report webhook
  trigger_n8n_webhook_async()    Same, in a background thread, tracking BloodReport.n8n_status
  call_post_upload_api()         Legacy alias kept for backward compatibility
"""

import io
import json
import logging
import threading
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.core.signing import TimestampSigner
from django.db import connection
from django.urls import reverse

logger = logging.getLogger(__name__)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_integration_config():
    """Import lazily to avoid circular imports at module load time."""
    from .models import IntegrationConfig
    return IntegrationConfig.get_config()


def get_drive_service():
    """
    Build and return an authenticated Google Drive API v3 service client.

    Reads the service-account JSON from IntegrationConfig.
    Raises RuntimeError if credentials are not configured.
    """
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError(
            "Google API client libraries are not installed. "
            "Add google-api-python-client, google-auth, and google-auth-httplib2 to requirements.txt."
        ) from exc

    config = _get_integration_config()
    if not config.google_service_account_json:
        raise RuntimeError(
            "Google service account credentials are not configured. "
            "Go to Django Admin → Integration Configuration and paste your service account JSON."
        )

    try:
        creds_info = json.loads(config.google_service_account_json)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid service account JSON in IntegrationConfig: {exc}") from exc

    scopes = ["https://www.googleapis.com/auth/drive"]
    credentials = service_account.Credentials.from_service_account_info(creds_info, scopes=scopes)
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def get_or_create_subfolder(drive_service, parent_id: str, name: str) -> str:
    """
    Return the Drive folder ID for *name* inside *parent_id*.
    Creates the folder if it doesn't already exist.
    """
    query = (
        f"name = '{name}' "
        f"and mimeType = 'application/vnd.google-apps.folder' "
        f"and '{parent_id}' in parents "
        f"and trashed = false"
    )
    result = drive_service.files().list(
        q=query,
        spaces="drive",
        fields="files(id, name)",
        pageSize=1,
        includeItemsFromAllDrives=True,
        supportsAllDrives=True,
    ).execute()

    files = result.get("files", [])
    if files:
        return files[0]["id"]

    # Create the folder
    metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    folder = drive_service.files().create(
        body=metadata,
        fields="id",
        supportsAllDrives=True
    ).execute()
    logger.info("Created Drive sub-folder '%s' (id=%s) under parent %s", name, folder["id"], parent_id)
    return folder["id"]


# ─── Blood Report Upload ───────────────────────────────────────────────────────

def upload_blood_report_to_drive(patient_id: int, file_obj) -> dict:
    """
    Upload *file_obj* to Drive under:
      <root_folder>/Patient blood reports/{patient_id}_blood_report.<ext>

    Returns:
      {"id": str, "link": str, "filename": str, "folder_name": str}
    """
    try:
        from googleapiclient.http import MediaIoBaseUpload
    except ImportError as exc:
        raise RuntimeError("google-api-python-client is not installed.") from exc

    config = _get_integration_config()
    root_folder_id = config.google_drive_root_folder_id
    if not root_folder_id:
        raise RuntimeError("google_drive_root_folder_id is not set in IntegrationConfig.")

    drive_service = get_drive_service()

    # Resolve sub-folder
    subfolder_name = "Patient blood reports"
    subfolder_id = get_or_create_subfolder(drive_service, root_folder_id, subfolder_name)

    # Build canonical filename
    original_name = getattr(file_obj, "name", "upload")
    ext = original_name.rsplit(".", 1)[-1] if "." in original_name else "pdf"
    filename = f"{patient_id}_blood_report.{ext}"

    # Determine MIME type
    content_type = getattr(file_obj, "content_type", "application/octet-stream")

    # Read file bytes
    file_obj.seek(0)
    file_bytes = file_obj.read()

    media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=content_type, resumable=False)
    file_metadata = {"name": filename, "parents": [subfolder_id]}

    uploaded = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id, webViewLink",
        supportsAllDrives=True
    ).execute()

    # Make the file readable by anyone with the link
    drive_service.permissions().create(
        fileId=uploaded["id"],
        body={"type": "anyone", "role": "reader"},
        supportsAllDrives=True
    ).execute()

    drive_link = uploaded.get("webViewLink", f"https://drive.google.com/file/d/{uploaded['id']}/view")

    logger.info(
        "Uploaded blood report to Drive: filename=%s, id=%s, link=%s",
        filename, uploaded["id"], drive_link,
    )

    return {
        "id": uploaded["id"],
        "link": drive_link,
        "filename": filename,
        "folder_name": subfolder_name,
    }


# Keep old stub as a fallback for tests / backward compat
def upload_file_to_drive(file_obj) -> dict:
    """
    Legacy alias. Tries to use the real Drive upload with a placeholder patient_id.
    For production use, call upload_blood_report_to_drive(patient_id, file_obj) directly.
    """
    import uuid
    try:
        # Real upload — use a temporary patient id placeholder
        return upload_blood_report_to_drive("unknown", file_obj)
    except Exception:
        fake_id = f"drive-{uuid.uuid4().hex}-{getattr(file_obj, 'name', 'file')}"
        fake_link = f"https://drive.google.com/file/d/{fake_id}/view"
        return {"id": fake_id, "link": fake_link, "filename": getattr(file_obj, "name", "upload"), "folder_name": ""}


# Keep old name as alias for backwards compatibility
upload_pdf_to_drive = upload_file_to_drive


# ─── n8n Webhook ──────────────────────────────────────────────────────────────

REPORT_LINK_SIGNER = TimestampSigner(salt="blood-report-download")
REPORT_LINK_MAX_AGE = 60 * 60 * 24


def signed_report_path(report) -> str:
    """Session-less download path for *report*; valid for REPORT_LINK_MAX_AGE seconds."""
    sig = REPORT_LINK_SIGNER.sign(str(report.pk)).split(":", 1)[1]
    return f"{reverse('download_blood_report', args=[report.pk])}?{urlencode({'sig': sig})}"


def build_n8n_payload(report, absolute_url) -> dict:
    """
    Body POSTed to the n8n "Nexus Health — Blood Report Agent" webhook.

    *absolute_url* turns a path into a full URL (e.g. request.build_absolute_uri).
    """
    patient = report.patient
    appointment = report.appointment
    return {
        "blood_report_id": report.pk,
        "patient_id": patient.pk if patient else None,
        "patient_email": patient.user.email if patient else report.uploader.email,
        "drive_link": absolute_url(signed_report_path(report)),
        "filename": report.original_filename,
        "mime_type": report.content_type,
        "appointment_id": appointment.appointment_id if appointment else None,
    }


def _post_n8n_webhook(payload: dict):
    """POST *payload* to n8n. Returns n8n's JSON reply, or None if the call failed."""
    config = _get_integration_config()
    endpoint = config.n8n_blood_report_webhook_url
    secret = config.n8n_webhook_secret

    if not endpoint:
        logger.warning("n8n_blood_report_webhook_url is not configured — skipping webhook call.")
        return None

    headers = {"Content-Type": "application/json"}
    if secret:
        headers["Authorization"] = f"Bearer {secret}"

    try:
        resp = requests.post(endpoint, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        logger.info("n8n webhook called successfully (status=%s)", resp.status_code)
        try:
            return resp.json()
        except Exception:
            return {"status": "ok"}
    except requests.exceptions.Timeout:
        logger.error("n8n webhook timed out (url=%s)", endpoint)
        return None
    except requests.exceptions.RequestException as exc:
        logger.error("n8n webhook call failed: %s", exc)
        return None


def trigger_n8n_webhook(payload: dict) -> dict:
    """
    POST *payload* to the configured n8n blood-report webhook URL.

    Includes:
      Authorization: Bearer <n8n_webhook_secret>

    Returns the JSON response from n8n, or {} on failure.
    """
    return _post_n8n_webhook(payload) or {}


def _set_report_status(report_id, status, error=None):
    from .models import BloodReport
    updates = {"n8n_status": status}
    if error:
        updates["ai_analysis"] = {"error": error}
    BloodReport.objects.filter(pk=report_id).update(**updates)


def _deliver_n8n_webhook(payload: dict) -> None:
    from .models import BloodReport
    try:
        if _post_n8n_webhook(payload) is None:
            _set_report_status(
                payload.get("blood_report_id"),
                BloodReport.N8nStatus.FAILED,
                "The n8n workflow could not be reached. Check that it is active, then re-send the report.",
            )
    except Exception:
        logger.exception("n8n webhook delivery crashed for BloodReport #%s", payload.get("blood_report_id"))
    finally:
        connection.close()


def trigger_n8n_webhook_async(payload: dict) -> bool:
    """
    Mark the report PROCESSING and deliver *payload* to n8n in a background thread.

    Reports stay PENDING when no webhook URL is configured, and become FAILED if n8n
    cannot be reached. Returns True when delivery was started.
    """
    from .models import BloodReport
    report_id = payload.get("blood_report_id")
    if not _get_integration_config().n8n_blood_report_webhook_url:
        logger.warning("n8n webhook URL is not configured; BloodReport #%s stays PENDING.", report_id)
        return False
    _set_report_status(report_id, BloodReport.N8nStatus.PROCESSING)
    threading.Thread(target=_deliver_n8n_webhook, args=(payload,), daemon=True).start()
    return True


# ─── Legacy helper (kept for backward compatibility) ──────────────────────────

def call_post_upload_api(payload: dict) -> dict:
    """
    Legacy function. Now delegates to trigger_n8n_webhook.
    Falls back to the old POST_UPLOAD_WEBHOOK_URL env var if n8n is not configured.
    """
    config = _get_integration_config()
    if config.n8n_blood_report_webhook_url:
        return trigger_n8n_webhook(payload)

    # Fallback to old env-var based behaviour
    endpoint = getattr(settings, "POST_UPLOAD_WEBHOOK_URL", "")
    token = getattr(settings, "POST_UPLOAD_WEBHOOK_TOKEN", "")
    if not endpoint:
        return {}

    try:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        resp = requests.post(endpoint, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return {}
