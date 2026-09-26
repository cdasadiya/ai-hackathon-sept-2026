#!/usr/bin/env python3
"""Push the showcase case roster + future appointments/reports to a running site.

Uses public registration, profile forms, appointment/report APIs, and comment
forms. Past appointments, doctor approval/rejection, inactive flags, audit logs,
health reports, specialties, and departments cannot be written without admin /
n8n callback — those gaps are printed clearly. Safe to re-run.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from http.cookiejar import CookieJar

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ["SEED_DEMO_USERS"] = "false"
os.environ.setdefault("SEED_SHOWCASE", "false")

import django

django.setup()

from app.management.commands.seed_showcase import (  # noqa: E402
    BLOOD_REPORTS,
    COMMENTS,
    DOCTORS,
    PASSWORD,
    PATIENTS,
)

BASE = os.environ.get("SHOWCASE_BASE_URL", "https://ai-hackathon-sept-2026.onrender.com").rstrip("/")
UTC = timezone.utc

# Fixed future slots (absolute UTC) so re-runs land on the same wall times.
# Past showcase visits cannot be created through the live API (Appointment.clean).
LIVE_APPOINTMENTS = [
    {
        "key": "APT-2026-900001",
        "patient": "case_patient_01",
        "doctor": "case_doctor_01",
        "start": datetime(2026, 10, 10, 9, 0, tzinfo=UTC),
        "end": datetime(2026, 10, 10, 9, 30, tzinfo=UTC),
        "status": "COMPLETED",
        "notes": "Cardiac review after a dizzy spell. (Live mirror of showcase APT-2026-900001; original was past.)",
        "remarks": "ECG reviewed. Continue current medication and repeat lipids in 8 weeks.",
    },
    {
        "key": "APT-2026-900002",
        "patient": "case_patient_02",
        "doctor": "case_doctor_02",
        "start": datetime(2026, 10, 12, 11, 0, tzinfo=UTC),
        "end": datetime(2026, 10, 12, 11, 45, tzinfo=UTC),
        "status": "CANCELLED",
        "notes": "Neurology slot cancelled by the patient. (Live mirror of showcase APT-2026-900002.)",
        "remarks": "",
    },
    {
        "key": "APT-2026-900003",
        "patient": "case_patient_03",
        "doctor": "case_doctor_06",
        "start": datetime(2026, 10, 18, 8, 0, tzinfo=UTC),
        "end": datetime(2026, 10, 18, 8, 30, tzinfo=UTC),
        "status": "NO_SHOW",
        "notes": "Pediatric follow-up marked no-show. (Live mirror of showcase APT-2026-900003.)",
        "remarks": "Marked no-show. Reception attempted one phone call.",
    },
    {
        "key": "APT-2026-900004",
        "patient": "case_patient_04",
        "doctor": "case_doctor_07",
        "start": datetime(2026, 10, 26, 14, 45, tzinfo=UTC),
        "end": datetime(2026, 10, 26, 16, 15, tzinfo=UTC),
        "status": "CONFIRMED",
        "notes": "Rash review. (Live mirror of showcase APT-2026-900004.)",
        "remarks": "Exam in progress. Waiting on the image report pipeline.",
    },
    {
        "key": "APT-2026-900005",
        "patient": "case_patient_05",
        "doctor": "case_doctor_01",
        "start": datetime(2026, 10, 27, 4, 0, tzinfo=UTC),
        "end": datetime(2026, 10, 27, 4, 30, tzinfo=UTC),
        "status": "PENDING",
        "notes": "Next-day request still awaiting confirmation. (Live mirror of showcase APT-2026-900005.)",
        "remarks": "",
    },
    {
        "key": "APT-2026-900006",
        "patient": "case_patient_06",
        "doctor": "case_doctor_02",
        "start": datetime(2026, 10, 28, 10, 0, tzinfo=UTC),
        "end": datetime(2026, 10, 28, 11, 0, tzinfo=UTC),
        "status": "CONFIRMED",
        "notes": "Neurology visit. Lab file uploaded and still queued. (Live mirror of showcase APT-2026-900006.)",
        "remarks": "",
    },
    {
        "key": "APT-2026-900007",
        "patient": "case_patient_07",
        "doctor": "case_doctor_08",
        "start": datetime(2026, 11, 2, 6, 30, tzinfo=UTC),
        "end": datetime(2026, 11, 2, 7, 15, tzinfo=UTC),
        "status": "PENDING",
        "notes": "ENT booking. Sinus symptoms for three weeks. (Live mirror of showcase APT-2026-900007.)",
        "remarks": "",
    },
    {
        "key": "APT-2026-900008",
        "patient": "case_patient_08",
        "doctor": "case_doctor_03",
        "start": datetime(2026, 11, 5, 13, 0, tzinfo=UTC),
        "end": datetime(2026, 11, 5, 13, 20, tzinfo=UTC),
        "status": "CANCELLED",
        "notes": "Slot cancelled after the surgeon closed new bookings. (Live mirror of showcase APT-2026-900008.)",
        "remarks": "Cancelled because the doctor is not accepting appointments.",
    },
    {
        "key": "APT-2026-900009",
        "patient": "case_patient_10",
        "doctor": "case_doctor_10",
        "start": datetime(2026, 11, 20, 7, 0, tzinfo=UTC),
        "end": datetime(2026, 11, 20, 8, 0, tzinfo=UTC),
        "status": "COMPLETED",
        "notes": "Endocrine review. (Live mirror of showcase APT-2026-900009; original was past.)",
        "remarks": "HbA1c above target. Diet plan discussed.",
    },
    {
        "key": "APT-2026-900010",
        "patient": "case_patient_09",
        "doctor": "case_doctor_09",
        "start": datetime(2026, 12, 1, 9, 0, tzinfo=UTC),
        "end": datetime(2026, 12, 1, 9, 40, tzinfo=UTC),
        "status": "CONFIRMED",
        "notes": "Oncology consult. No report attached yet. (Live mirror of showcase APT-2026-900010.)",
        "remarks": "",
    },
]


class Site:
    def __init__(self):
        self.jar = CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def csrf(self):
        for cookie in self.jar:
            if cookie.name == "csrftoken":
                return cookie.value
        raise RuntimeError("CSRF cookie missing")

    def request(self, path, data=None, headers=None, json_body=None, method=None):
        hdrs = {"User-Agent": "nexus-showcase-sync"}
        if headers:
            hdrs.update(headers)
        body = data
        if json_body is not None:
            body = json.dumps(json_body).encode()
            hdrs["Content-Type"] = "application/json"
        req = urllib.request.Request(BASE + path, data=body, headers=hdrs, method=method)
        try:
            with self.opener.open(req, timeout=90) as resp:
                return resp.status, resp.geturl(), resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.geturl(), exc.read().decode("utf-8", "replace")

    def login(self, username, password=PASSWORD):
        self.request("/login/")
        payload = urllib.parse.urlencode(
            {
                "username": username,
                "password": password,
                "csrfmiddlewaretoken": self.csrf(),
            }
        ).encode()
        status, url, _html = self.request(
            "/login/",
            data=payload,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": BASE + "/login/",
            },
        )
        if "/login/" in url or status >= 400:
            raise RuntimeError(f"Login failed for {username}: HTTP {status} {url}")
        return url


def token_for(username, password=PASSWORD):
    status, _url, body = Site().request(
        "/api/token/",
        json_body={"username": username, "password": password},
    )
    if status != 200:
        raise RuntimeError(f"Token for {username} failed HTTP {status}: {body[:240]}")
    return json.loads(body)["access"]


def register(username, role):
    site = Site()
    status, _url, body = site.request(
        "/api/register/",
        json_body={
            "username": username,
            "email": f"{username}@example.com",
            "password": PASSWORD,
            "role": role,
        },
    )
    if status == 201:
        print(f"  registered {username}")
        return json.loads(body)
    if status == 400 and "already exists" in body.lower():
        print(f"  {username} already exists")
        return None
    # Username unique vs email unique wording varies by deploy
    if status == 400 and ("exist" in body.lower() or "unique" in body.lower()):
        print(f"  {username} already exists ({body[:120]})")
        return None
    raise RuntimeError(f"Register {username} failed HTTP {status}: {body[:240]}")


def sync_patient(row):
    username, first, last, phone, dob, blood, address, emergency, active, verified = row
    register(username, "PATIENT")
    site = Site()
    site.login(username)
    site.request("/patient/profile/")
    payload = urllib.parse.urlencode(
        {
            "csrfmiddlewaretoken": site.csrf(),
            "first_name": first,
            "last_name": last,
            "phone": phone,
            "dob": dob,
            "blood_group": blood,
            "address": address,
            "emergency_contact": emergency,
        }
    ).encode()
    status, url, html = site.request(
        "/patient/profile/",
        data=payload,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": BASE + "/patient/profile/",
        },
    )
    if first and first not in html:
        raise RuntimeError(f"Patient profile {username} HTTP {status} {url} missing first_name")
    note = ""
    if not active:
        note = " (is_active=False cannot be set via public API)"
    if verified:
        note += " (email_verified cannot be set via public API)"
    print(f"  synced patient {username}{note}")


def sync_doctor(row):
    username, first, last, _spec, _dept, license_no, verification, accepting, active, verified, bio = row
    register(username, "DOCTOR")
    site = Site()
    site.login(username)
    site.request("/doctor/profile/")
    fields = {
        "csrfmiddlewaretoken": site.csrf(),
        "first_name": first,
        "last_name": last,
        "bio": bio,
        "availability_notes": "Showcase calendar. Times below are fixed demo visits.",
        "medical_license_no": license_no,
    }
    if accepting:
        fields["is_accepting_appointments"] = "on"
    payload = urllib.parse.urlencode(fields).encode()
    status, url, html = site.request(
        "/doctor/profile/",
        data=payload,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": BASE + "/doctor/profile/",
        },
    )
    if first and first not in html:
        raise RuntimeError(f"Doctor profile {username} HTTP {status} did not show saved values")
    gaps = []
    if verification != "PENDING":
        gaps.append(f"verification={verification} needs admin")
    if not active:
        gaps.append("is_active=False needs admin/ORM")
    if verified:
        gaps.append("email_verified needs admin/ORM")
    gaps.append("specialty/department not on public form")
    print(f"  synced doctor {username}" + (f" [{'; '.join(gaps)}]" if gaps else ""))


def set_accepting(username, accepting, first, last, bio, license_no):
    site = Site()
    site.login(username)
    site.request("/doctor/profile/")
    fields = {
        "csrfmiddlewaretoken": site.csrf(),
        "first_name": first,
        "last_name": last,
        "bio": bio,
        "availability_notes": "Showcase calendar. Times below are fixed demo visits.",
        "medical_license_no": license_no,
    }
    if accepting:
        fields["is_accepting_appointments"] = "on"
    status, _url, _html = site.request(
        "/doctor/profile/",
        data=urllib.parse.urlencode(fields).encode(),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": BASE + "/doctor/profile/",
        },
    )
    if status >= 400:
        raise RuntimeError(f"set_accepting({username}) HTTP {status}")


def map_all_doctor_ids(patient_username="case_patient_01"):
    """Discover DoctorProfile pks for every showcase doctor with minimal probes."""
    doctor_rows_by_name = {row[0]: row for row in DOCTORS}
    # Enable accepting so probes are not blocked by Appointment.clean()
    for row in DOCTORS:
        username, first, last, _s, _d, license_no, _v, _a, _act, _ver, bio = row
        set_accepting(username, True, first, last, bio, license_no)

    access_patient = token_for(patient_username)
    mapped = {}
    unmapped = {row[0] for row in DOCTORS}

    # Reuse any appointments already on the doctor (e.g. prior map probes)
    for username in list(unmapped):
        access_doc = token_for(username)
        st, _u, body = Site().request(
            "/api/appointments/",
            headers={"Authorization": f"Bearer {access_doc}"},
        )
        if st == 200:
            rows = json.loads(body)
            if isinstance(rows, list) and rows:
                mapped[username] = rows[0]["doctor"]
                unmapped.discard(username)
                print(f"  mapped {username} -> doctor_profile_id={mapped[username]} (existing)")

    start = datetime.now(UTC) + timedelta(days=75)
    for doc_id in range(1, 80):
        if not unmapped:
            break
        if doc_id in mapped.values():
            continue
        start_i = start + timedelta(minutes=doc_id * 40)
        end_i = start_i + timedelta(minutes=20)
        marker = f"SHOWCASE_MAP:id={doc_id}"
        payload = {
            "doctor": doc_id,
            "start_time": start_i.isoformat().replace("+00:00", "Z"),
            "end_time": end_i.isoformat().replace("+00:00", "Z"),
            "notes": marker,
            "status": "PENDING",
        }
        st, _u, body = Site().request(
            "/api/appointments/",
            json_body=payload,
            headers={"Authorization": f"Bearer {access_patient}"},
        )
        if st not in (200, 201):
            continue
        appt = json.loads(body)
        hit = None
        for username in list(unmapped):
            access_doc = token_for(username)
            st2, _u2, body2 = Site().request(
                "/api/appointments/",
                headers={"Authorization": f"Bearer {access_doc}"},
            )
            if st2 == 200 and marker in body2:
                hit = username
                mapped[username] = doc_id
                unmapped.discard(username)
                print(f"  mapped {username} -> doctor_profile_id={doc_id}")
                Site().request(
                    f"/api/appointments/{appt['id']}/update_status/",
                    json_body={"status": "CANCELLED", "notes": marker + " (cancelled map probe)"},
                    headers={"Authorization": f"Bearer {access_doc}"},
                )
                break
        if hit is None:
            # Not a showcase doctor (e.g. doctor1..5). Leave the row; do not delete (patient cannot).
            print(f"  probe doctor_profile_id={doc_id} is not a showcase doctor")

    # Restore intended accepting flags
    for row in DOCTORS:
        username, first, last, _s, _d, license_no, _v, accepting, _act, _ver, bio = row
        set_accepting(username, accepting, first, last, bio, license_no)

    if unmapped:
        raise RuntimeError(f"Unmapped showcase doctors: {sorted(unmapped)}")
    return mapped, doctor_rows_by_name


def find_existing_appointment(access, notes_substr):
    st, _u, body = Site().request(
        "/api/appointments/",
        headers={"Authorization": f"Bearer {access}"},
    )
    if st != 200:
        return None
    rows = json.loads(body)
    if not isinstance(rows, list):
        rows = rows.get("results", [])
    for row in rows:
        if notes_substr in (row.get("notes") or ""):
            return row
    return None


def ensure_appointment(row, doctor_ids, doctor_rows_by_name):
    patient = row["patient"]
    doctor = row["doctor"]
    access = token_for(patient)
    existing = find_existing_appointment(access, row["key"])
    if existing:
        print(f"  appointment {row['key']} already present as {existing.get('appointment_id')}")
        appt = existing
    else:
        drow = doctor_rows_by_name[doctor]
        username, first, last, _spec, _dept, license_no, _ver, accepting, _active, _verified, bio = drow
        if not accepting:
            set_accepting(username, True, first, last, bio, license_no)
        payload = {
            "doctor": doctor_ids[doctor],
            "start_time": row["start"].isoformat().replace("+00:00", "Z"),
            "end_time": row["end"].isoformat().replace("+00:00", "Z"),
            "notes": f"{row['notes']} [{row['key']}]",
            "status": "PENDING",
        }
        st, _u, body = Site().request(
            "/api/appointments/",
            json_body=payload,
            headers={"Authorization": f"Bearer {access}"},
        )
        if not accepting:
            set_accepting(username, False, first, last, bio, license_no)
        if st not in (200, 201):
            raise RuntimeError(f"Create {row['key']} failed HTTP {st}: {body[:300]}")
        appt = json.loads(body)
        print(f"  created {row['key']} -> {appt.get('appointment_id')} (pk={appt.get('id')})")

    if row["status"] != "PENDING" or row["remarks"]:
        doc_access = token_for(doctor)
        st, _u, body = Site().request(
            f"/api/appointments/{appt['id']}/update_status/",
            json_body={"status": row["status"], "notes": appt.get("notes", "")},
            headers={"Authorization": f"Bearer {doc_access}"},
        )
        if st != 200:
            print(f"  WARN status {row['status']} for {row['key']}: HTTP {st} {body[:160]}")
        elif row["remarks"]:
            site = Site()
            site.login(doctor)
            appt_id = appt.get("appointment_id") or json.loads(body).get("appointment_id")
            site.request(f"/doctor/appointment/{appt_id}/")
            form = urllib.parse.urlencode(
                {
                    "csrfmiddlewaretoken": site.csrf(),
                    "status": row["status"],
                    "doctor_remarks": row["remarks"],
                }
            ).encode()
            site.request(
                f"/doctor/appointment/{appt_id}/update/",
                data=form,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Referer": BASE + f"/doctor/appointment/{appt_id}/",
                },
            )
    return appt


def ensure_report(filename, patient_name, appt_id, file_type, n8n_status, folder, analysis, appt_map):
    access = token_for(patient_name)
    st, _u, body = Site().request(
        "/api/reports/",
        headers={"Authorization": f"Bearer {access}"},
    )
    if st == 200:
        rows = json.loads(body)
        if not isinstance(rows, list):
            rows = rows.get("results", [])
        for row in rows:
            if row.get("original_filename") == filename:
                print(f"  report {filename} already present")
                return row
    payload = {
        "original_filename": filename,
        "file_type": file_type,
        "n8n_status": n8n_status,
        "drive_folder_name": folder,
        "ai_analysis": analysis,
        "drive_file_id": f"showcase-{filename}",
        "drive_link": f"https://example.com/showcase/{filename}",
    }
    if appt_id and appt_id in appt_map:
        payload["appointment"] = appt_map[appt_id]["id"]
    st, _u, body = Site().request(
        "/api/reports/",
        json_body=payload,
        headers={"Authorization": f"Bearer {access}"},
    )
    if st not in (200, 201):
        raise RuntimeError(f"Report {filename} failed HTTP {st}: {body[:300]}")
    print(f"  created report {filename} ({n8n_status}/{file_type})")
    return json.loads(body)


def ensure_comment(appt_key, author, body_text, appt_map):
    appt = appt_map.get(appt_key)
    if not appt:
        print(f"  skip comment on {appt_key}: appointment missing on live")
        return
    appt_id = appt.get("appointment_id")
    site = Site()
    site.login(author)
    # Patient vs doctor comment routes
    if author.startswith("case_patient"):
        path = f"/patient/appointment/{appt_id}/"
        post = f"/patient/appointment/{appt_id}/comment/"
    else:
        path = f"/doctor/appointment/{appt_id}/"
        post = f"/doctor/appointment/{appt_id}/comment/"
    st, _u, html = site.request(path)
    if body_text in html:
        print(f"  comment on {appt_key} by {author} already present")
        return
    site.request(path)
    form = urllib.parse.urlencode(
        {"csrfmiddlewaretoken": site.csrf(), "body": body_text}
    ).encode()
    st, _u, html = site.request(
        post,
        data=form,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": BASE + path,
        },
    )
    print(f"  comment on {appt_key} by {author}: HTTP {st}")


def main():
    print(f"Syncing showcase to {BASE}")
    print("Doctors")
    for row in DOCTORS:
        sync_doctor(row)
    print("Patients")
    for row in PATIENTS:
        sync_patient(row)

    print("Discovering doctor profile ids")
    doctor_ids, doctor_rows_by_name = map_all_doctor_ids()

    print("Appointments (10 future mirrors)")
    appt_map = {}
    for row in LIVE_APPOINTMENTS:
        appt = ensure_appointment(row, doctor_ids, doctor_rows_by_name)
        appt_map[row["key"]] = appt

    print("Blood reports")
    # Only the primary 10 showcase filenames (skip companion DONE pads if any beyond guide)
    primary = BLOOD_REPORTS[:10]
    for filename, patient_name, appt_id, file_type, n8n_status, folder, analysis in primary:
        ensure_report(filename, patient_name, appt_id, file_type, n8n_status, folder, analysis, appt_map)

    print("Comments")
    for appt_key, author, body_text, _created in COMMENTS:
        ensure_comment(appt_key, author, body_text, appt_map)

    print()
    print("Live gaps (cannot write via public site on current deploy):")
    print("  - Doctor verification APPROVED/REJECTED (no admin1 on live)")
    print("  - Specialty / Department rows (no public write; profile form omits them)")
    print("  - Past appointment wall-clock times (API enforces 30+ minutes future)")
    print("  - User.is_active=False / email_verified (no public write)")
    print("  - HealthReport (n8n callback token required)")
    print("  - AuditLog (admin/ORM only)")
    print("  - UserToken showcase placeholders (admin generate_user_tokens / ORM)")
    print("  - IntegrationConfig (singleton; do not overwrite secrets)")
    print(f"Done. Case users password: {PASSWORD}")


if __name__ == "__main__":
    main()
