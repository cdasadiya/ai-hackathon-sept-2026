#!/usr/bin/env python3
"""Create the same 5 doctors and 5 patients on a running site.

Uses public registration plus each user's profile form so local seed data
and the live database stay aligned. Safe to re-run.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ["SEED_DEMO_USERS"] = "false"

import django

django.setup()

from app.management.commands.seed_demo_users import DOCTORS, PATIENTS  # noqa: E402

BASE = os.environ.get("ROSTER_BASE_URL", "https://ai-hackathon-sept-2026.onrender.com").rstrip("/")
PASSWORD = "Pass1234!"


class Site:
    def __init__(self):
        self.jar = CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def csrf(self):
        for cookie in self.jar:
            if cookie.name == "csrftoken":
                return cookie.value
        raise RuntimeError("CSRF cookie missing")

    def request(self, path, data=None, headers=None, json_body=None):
        hdrs = {"User-Agent": "nexus-roster-sync"}
        if headers:
            hdrs.update(headers)
        body = data
        if json_body is not None:
            body = json.dumps(json_body).encode()
            hdrs["Content-Type"] = "application/json"
        req = urllib.request.Request(BASE + path, data=body, headers=hdrs)
        try:
            with self.opener.open(req, timeout=90) as resp:
                return resp.status, resp.geturl(), resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.geturl(), exc.read().decode("utf-8", "replace")

    def login(self, username):
        self.request("/login/")
        payload = urllib.parse.urlencode(
            {
                "username": username,
                "password": PASSWORD,
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
    elif status == 400 and "already exists" in body:
        print(f"  {username} already exists")
    else:
        raise RuntimeError(f"Register {username} failed HTTP {status}: {body[:240]}")


def sync_patient(row):
    register(row["username"], "PATIENT")
    site = Site()
    site.login(row["username"])
    site.request("/patient/profile/")
    payload = urllib.parse.urlencode(
        {
            "csrfmiddlewaretoken": site.csrf(),
            "first_name": row["first_name"],
            "last_name": row["last_name"],
            "phone": row["phone"],
            "dob": row["dob"].isoformat(),
            "blood_group": row["blood_group"],
            "address": row["address"],
            "emergency_contact": row["emergency_contact"],
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
    if "Profile updated successfully" not in html and status >= 400:
        raise RuntimeError(f"Patient profile {row['username']} HTTP {status} {url}")
    if row["blood_group"] not in html or row["first_name"] not in html:
        raise RuntimeError(f"Patient profile {row['username']} did not show saved values")
    print(f"  synced patient {row['username']} ({row['first_name']} {row['last_name']}, {row['blood_group']})")


def sync_doctor(row):
    register(row["username"], "DOCTOR")
    site = Site()
    site.login(row["username"])
    site.request("/doctor/profile/")
    payload = urllib.parse.urlencode(
        {
            "csrfmiddlewaretoken": site.csrf(),
            "first_name": row["first_name"],
            "last_name": row["last_name"],
            "bio": row["bio"],
            "availability_notes": row["availability_notes"],
            "medical_license_no": row["medical_license_no"],
            "is_accepting_appointments": "on",
        }
    ).encode()
    status, url, html = site.request(
        "/doctor/profile/",
        data=payload,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": BASE + "/doctor/profile/",
        },
    )
    if row["medical_license_no"] not in html or row["first_name"] not in html:
        raise RuntimeError(f"Doctor profile {row['username']} HTTP {status} did not show saved values")
    print(f"  synced doctor {row['username']} (Dr. {row['first_name']} {row['last_name']}, {row['medical_license_no']})")


def main():
    print(f"Syncing roster to {BASE}")
    print("Doctors")
    for row in DOCTORS:
        sync_doctor(row)
    print("Patients")
    for row in PATIENTS:
        sync_patient(row)
    print("Done: 5 doctors and 5 patients")


if __name__ == "__main__":
    main()
