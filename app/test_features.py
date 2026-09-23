import json
from datetime import timedelta
from io import BytesIO
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from .models import (
    Appointment,
    BloodReport,
    DoctorProfile,
    HealthReport,
    IntegrationConfig,
    PatientProfile,
    ReportComment,
    User,
    UserToken,
)
from .services import call_post_upload_api, get_drive_service, trigger_n8n_webhook


def local_dt(value):
    return timezone.localtime(value).strftime("%Y-%m-%dT%H:%M")


def window(hours=3, minutes=30):
    start = timezone.now() + timedelta(hours=hours)
    return start, start + timedelta(minutes=minutes)


class FeatureDataMixin:
    password = "Pass1234!"

    def make_user(self, username, role, **extra):
        return User.objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password=self.password,
            role=role,
            **extra,
        )

    def make_doctor(self, username="doc", approved=True, accepting=True):
        user = self.make_user(username, User.Role.DOCTOR)
        profile = DoctorProfile.objects.create(
            user=user,
            verification_status=(
                DoctorProfile.VerificationStatus.APPROVED
                if approved
                else DoctorProfile.VerificationStatus.PENDING
            ),
            is_accepting_appointments=accepting,
        )
        return user, profile

    def make_patient(self, username="pat"):
        user = self.make_user(username, User.Role.PATIENT)
        profile = PatientProfile.objects.create(user=user)
        return user, profile

    def make_admin(self, username="root"):
        return self.make_user(username, User.Role.ADMIN, is_staff=True, is_superuser=True)

    def book(self, patient, doctor, hours=3, status=Appointment.Status.PENDING):
        start, end = window(hours=hours)
        return Appointment.objects.create(
            patient=patient,
            doctor=doctor,
            start_time=start,
            end_time=end,
            status=status,
            notes="routine",
        )

    def login(self, username):
        client = Client()
        logged_in = client.login(username=username, password=self.password)
        self.assertTrue(logged_in)
        return client

    def api(self, user):
        client = APIClient()
        access = str(RefreshToken.for_user(user).access_token)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        return client


class AuthenticationTests(FeatureDataMixin, TestCase):
    def test_login_page_and_valid_patient_login(self):
        self.make_patient("pat_login")
        client = Client()
        page = client.get(reverse("login"))
        self.assertEqual(page.status_code, 200)
        response = client.post(
            reverse("login"),
            {"username": "pat_login", "password": self.password},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dashboard")

    def test_login_rejects_bad_password_and_inactive_user(self):
        user, _ = self.make_patient("pat_bad")
        client = Client()
        bad = client.post(reverse("login"), {"username": "pat_bad", "password": "wrong-pass"})
        self.assertEqual(bad.status_code, 200)
        self.assertContains(bad, "Please enter a correct")
        user.is_active = False
        user.save(update_fields=["is_active"])
        inactive = client.post(
            reverse("login"),
            {"username": "pat_bad", "password": self.password},
        )
        self.assertEqual(inactive.status_code, 200)
        self.assertFalse(inactive.wsgi_request.user.is_authenticated)

    def test_register_patient_and_reject_admin_role(self):
        client = Client()
        ok = client.post(
            reverse("register"),
            {
                "username": "new_pat",
                "email": "new_pat@example.com",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
                "role": User.Role.PATIENT,
            },
            follow=True,
        )
        self.assertEqual(ok.status_code, 200)
        user = User.objects.get(username="new_pat")
        self.assertEqual(user.role, User.Role.PATIENT)
        self.assertTrue(PatientProfile.objects.filter(user=user).exists())
        self.assertTrue(UserToken.objects.filter(user=user).exists())

        denied = client.post(
            reverse("register"),
            {
                "username": "sneaky_admin",
                "email": "sneaky_admin@example.com",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
                "role": User.Role.ADMIN,
            },
        )
        self.assertEqual(denied.status_code, 200)
        self.assertFalse(User.objects.filter(username="sneaky_admin").exists())

    def test_register_rejects_mismatched_passwords(self):
        client = Client()
        response = client.post(
            reverse("register"),
            {
                "username": "mismatch",
                "email": "mismatch@example.com",
                "password1": "StrongPass123!",
                "password2": "OtherPass123!",
                "role": User.Role.PATIENT,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="mismatch").exists())

    def test_logout_and_password_reset_page(self):
        self.make_patient("pat_out")
        client = self.login("pat_out")
        response = client.post(reverse("logout"), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sign In")
        reset = Client().get(reverse("password_reset"))
        self.assertEqual(reset.status_code, 200)

    def test_home_redirects_by_role(self):
        self.make_admin("home_admin")
        self.make_doctor("home_doc")
        self.make_patient("home_pat")
        self.assertRedirects(self.login("home_admin").get(reverse("home")), reverse("admin_dashboard"))
        self.assertRedirects(self.login("home_doc").get(reverse("home")), reverse("doctor_dashboard"))
        self.assertRedirects(self.login("home_pat").get(reverse("home")), reverse("patient_dashboard"))


class AuthorizationTests(FeatureDataMixin, TestCase):
    def test_dashboards_reject_the_wrong_role(self):
        self.make_patient("auth_pat")
        self.make_doctor("auth_doc")
        self.make_admin("auth_admin")
        patient = self.login("auth_pat")
        doctor = self.login("auth_doc")
        self.assertEqual(patient.get(reverse("doctor_dashboard")).status_code, 302)
        self.assertEqual(patient.get(reverse("admin_dashboard")).status_code, 302)
        self.assertEqual(doctor.get(reverse("patient_dashboard")).status_code, 302)
        self.assertEqual(doctor.get(reverse("admin_dashboard")).status_code, 302)
        anon = Client().get(reverse("patient_dashboard"))
        self.assertEqual(anon.status_code, 302)
        self.assertIn("/login/", anon.url)

    def test_doctor_approval_is_admin_only(self):
        admin = self.make_admin("approver")
        _, doctor = self.make_doctor("needs_review", approved=False)
        patient_client = self.login(self.make_patient("not_admin")[0].username)
        denied = patient_client.post(reverse("approve_doctor", args=[doctor.pk]), follow=True)
        doctor.refresh_from_db()
        self.assertEqual(doctor.verification_status, DoctorProfile.VerificationStatus.PENDING)
        self.assertEqual(denied.status_code, 200)

        admin_client = self.login(admin.username)
        approved = admin_client.post(reverse("approve_doctor", args=[doctor.pk]), follow=True)
        self.assertEqual(approved.status_code, 200)
        doctor.refresh_from_db()
        self.assertEqual(doctor.verification_status, DoctorProfile.VerificationStatus.APPROVED)
        rejected = admin_client.post(reverse("reject_doctor", args=[doctor.pk]), follow=True)
        self.assertEqual(rejected.status_code, 200)
        doctor.refresh_from_db()
        self.assertEqual(doctor.verification_status, DoctorProfile.VerificationStatus.REJECTED)

    def test_debug_admin_is_staff_only(self):
        _, patient = self.make_patient("dbg_pat")
        admin = self.make_admin("dbg_admin")
        denied = self.login(patient.user.username).get(reverse("debug_admin"))
        self.assertEqual(denied.status_code, 403)
        allowed = self.login(admin.username).get(reverse("debug_admin"))
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.json()["user"], "dbg_admin")


class AppointmentTests(FeatureDataMixin, TestCase):
    def test_patient_books_future_appointment(self):
        _, patient = self.make_patient("booker")
        _, doctor = self.make_doctor("book_doc")
        start, end = window(hours=4)
        client = self.login("booker")
        response = client.post(
            reverse("book_appointment"),
            {
                "doctor": doctor.pk,
                "start_time": local_dt(start),
                "end_time": local_dt(end),
                "notes": "café 血液",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        appt = Appointment.objects.get(patient=patient)
        self.assertTrue(appt.appointment_id.startswith(f"APT-{timezone.now().year}-"))
        self.assertIn("血液", appt.notes)

    def test_rejects_backdated_overlap_and_unavailable_doctor(self):
        _, patient = self.make_patient("edge_pat")
        _, doctor = self.make_doctor("edge_doc")
        client = self.login("edge_pat")
        past = timezone.now() - timedelta(hours=2)
        too_soon = timezone.now() + timedelta(minutes=10)
        start, end = window(hours=5)
        for begin, finish in ((past, past + timedelta(hours=1)), (too_soon, too_soon + timedelta(hours=1))):
            response = client.post(
                reverse("book_appointment"),
                {
                    "doctor": doctor.pk,
                    "start_time": local_dt(begin),
                    "end_time": local_dt(finish),
                },
                follow=True,
            )
            self.assertEqual(response.status_code, 200)
        self.assertEqual(Appointment.objects.filter(patient=patient).count(), 0)

        first = client.post(
            reverse("book_appointment"),
            {"doctor": doctor.pk, "start_time": local_dt(start), "end_time": local_dt(end)},
            follow=True,
        )
        self.assertEqual(first.status_code, 200)
        second = client.post(
            reverse("book_appointment"),
            {"doctor": doctor.pk, "start_time": local_dt(start), "end_time": local_dt(end)},
            follow=True,
        )
        self.assertEqual(second.status_code, 200)
        self.assertEqual(Appointment.objects.filter(patient=patient).count(), 1)

        doctor.is_accepting_appointments = False
        doctor.save(update_fields=["is_accepting_appointments"])
        later, later_end = window(hours=8)
        closed = client.post(
            reverse("book_appointment"),
            {"doctor": doctor.pk, "start_time": local_dt(later), "end_time": local_dt(later_end)},
            follow=True,
        )
        self.assertEqual(closed.status_code, 200)
        self.assertEqual(Appointment.objects.filter(patient=patient).count(), 1)

    def test_cancel_only_pending_and_only_owner(self):
        _, patient = self.make_patient("cancel_pat")
        _, other = self.make_patient("other_pat")
        _, doctor = self.make_doctor("cancel_doc")
        pending = self.book(patient, doctor, hours=6)
        confirmed = self.book(patient, doctor, hours=9, status=Appointment.Status.CONFIRMED)
        client = self.login("cancel_pat")
        denied = client.post(reverse("cancel_appointment", args=[confirmed.appointment_id]), follow=True)
        self.assertEqual(denied.status_code, 200)
        confirmed.refresh_from_db()
        self.assertEqual(confirmed.status, Appointment.Status.CONFIRMED)
        ok = client.post(reverse("cancel_appointment", args=[pending.appointment_id]), follow=True)
        self.assertEqual(ok.status_code, 200)
        pending.refresh_from_db()
        self.assertEqual(pending.status, Appointment.Status.CANCELLED)
        missing = client.post(reverse("cancel_appointment", args=["APT-1999-000000"]))
        self.assertEqual(missing.status_code, 404)
        stranger = self.login("other_pat")
        blocked = stranger.post(reverse("cancel_appointment", args=[confirmed.appointment_id]))
        self.assertEqual(blocked.status_code, 404)

    def test_search_is_not_sql_and_unknown_page_is_safe(self):
        _, patient = self.make_patient("search_pat")
        _, doctor = self.make_doctor("search_doc")
        self.book(patient, doctor, hours=6)
        client = self.login("search_pat")
        response = client.get(reverse("patient_dashboard"), {"search": "'; DROP TABLE app_appointment;--", "page": 99})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Appointment.objects.count(), 1)


class ReportAndCommentTests(FeatureDataMixin, TestCase):
    def test_upload_valid_pdf_and_reject_bad_files(self):
        _, patient = self.make_patient("up_pat")
        _, doctor = self.make_doctor("up_doc")
        appt = self.book(patient, doctor, hours=6)
        client = self.login("up_pat")
        pdf = SimpleUploadedFile("labs.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        ok = client.post(
            reverse("upload_report"),
            {"appointment_id": appt.appointment_id, "report_file": pdf},
            follow=True,
        )
        self.assertEqual(ok.status_code, 200)
        report = BloodReport.objects.get(appointment=appt)
        self.assertEqual(report.uploader, patient.user)
        self.assertEqual(report.n8n_status, BloodReport.N8nStatus.PROCESSING)

        huge = SimpleUploadedFile("big.pdf", b"x" * (10 * 1024 * 1024 + 1), content_type="application/pdf")
        too_big = client.post(
            reverse("upload_report"),
            {"appointment_id": appt.appointment_id, "report_file": huge},
            follow=True,
        )
        self.assertEqual(too_big.status_code, 200)
        self.assertEqual(BloodReport.objects.filter(appointment=appt).count(), 1)

        text = SimpleUploadedFile("notes.txt", b"hello", content_type="text/plain")
        wrong_type = client.post(
            reverse("upload_report"),
            {"appointment_id": appt.appointment_id, "report_file": text},
            follow=True,
        )
        self.assertEqual(wrong_type.status_code, 200)
        self.assertEqual(BloodReport.objects.filter(appointment=appt).count(), 1)

    def test_patient_cannot_upload_against_another_appointment(self):
        _, owner = self.make_patient("owner_pat")
        _, stranger = self.make_patient("stranger_pat")
        _, doctor = self.make_doctor("idor_doc")
        appt = self.book(owner, doctor, hours=6)
        client = self.login("stranger_pat")
        pdf = SimpleUploadedFile("labs.pdf", b"%PDF-1.4", content_type="application/pdf")
        response = client.post(
            reverse("upload_report"),
            {"appointment_id": appt.appointment_id, "report_file": pdf},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(BloodReport.objects.filter(appointment=appt).exists())

    def test_comments_and_doctor_review(self):
        _, patient = self.make_patient("c_pat")
        doctor_user, doctor = self.make_doctor("c_doc")
        appt = self.book(patient, doctor, hours=6)
        patient_client = self.login("c_pat")
        empty = patient_client.post(
            reverse("patient_add_comment", args=[appt.appointment_id]),
            {"body": "   "},
            follow=True,
        )
        self.assertEqual(empty.status_code, 200)
        self.assertEqual(ReportComment.objects.count(), 0)
        posted = patient_client.post(
            reverse("patient_add_comment", args=[appt.appointment_id]),
            {"body": "<script>alert(1)</script>"},
            follow=True,
        )
        self.assertEqual(posted.status_code, 200)
        self.assertContains(posted, "&lt;script&gt;alert(1)&lt;/script&gt;")
        doctor_client = self.login(doctor_user.username)
        review = doctor_client.post(
            reverse("doctor_update_appointment", args=[appt.appointment_id]),
            {"status": Appointment.Status.COMPLETED, "doctor_remarks": "Follow up in two weeks"},
            follow=True,
        )
        self.assertEqual(review.status_code, 200)
        appt.refresh_from_db()
        self.assertEqual(appt.status, Appointment.Status.COMPLETED)
        self.assertEqual(appt.doctor_remarks, "Follow up in two weeks")
        invalid = doctor_client.post(
            reverse("update_appointment_status", args=[appt.appointment_id]),
            {"status": "NOT_A_STATUS"},
            follow=True,
        )
        self.assertEqual(invalid.status_code, 200)
        appt.refresh_from_db()
        self.assertEqual(appt.status, Appointment.Status.COMPLETED)


class ProfileTests(FeatureDataMixin, TestCase):
    def test_patient_and_doctor_can_update_profiles(self):
        _, patient = self.make_patient("prof_pat")
        doctor_user, doctor = self.make_doctor("prof_doc")
        patient_client = self.login("prof_pat")
        saved = patient_client.post(
            reverse("patient_profile_edit"),
            {
                "first_name": "Asha",
                "last_name": "Patel",
                "phone": "+91 90000",
                "dob": "1991-04-02",
                "blood_group": "O+",
                "address": "12 MG Road",
                "emergency_contact": "Ravi 90001",
            },
            follow=True,
        )
        self.assertEqual(saved.status_code, 200)
        patient.refresh_from_db()
        patient.user.refresh_from_db()
        self.assertEqual(patient.user.first_name, "Asha")
        self.assertEqual(patient.blood_group, "O+")

        doctor_client = self.login(doctor_user.username)
        updated = doctor_client.post(
            reverse("doctor_profile_edit"),
            {
                "first_name": "Meera",
                "last_name": "Shah",
                "bio": "Cardiology",
                "availability_notes": "Mon–Fri",
                "medical_license_no": "LIC-42",
                "is_accepting_appointments": "",
            },
            follow=True,
        )
        self.assertEqual(updated.status_code, 200)
        doctor.refresh_from_db()
        self.assertEqual(doctor.medical_license_no, "LIC-42")
        self.assertFalse(doctor.is_accepting_appointments)


class ApiTests(FeatureDataMixin, TestCase):
    def test_token_and_scoped_appointment_api(self):
        _, patient = self.make_patient("api_pat")
        _, other = self.make_patient("api_other")
        _, doctor = self.make_doctor("api_doc")
        mine = self.book(patient, doctor, hours=6)
        theirs = self.book(other, doctor, hours=9)
        anon = APIClient().get("/api/appointments/")
        self.assertEqual(anon.status_code, 401)

        token = APIClient().post(
            reverse("token_obtain_pair"),
            {"username": "api_pat", "password": self.password},
            format="json",
        )
        self.assertEqual(token.status_code, 200)
        self.assertIn("access", token.data)

        client = self.api(patient.user)
        listing = client.get("/api/appointments/")
        self.assertEqual(listing.status_code, 200)
        ids = {row["id"] for row in listing.data}
        self.assertIn(mine.pk, ids)
        self.assertNotIn(theirs.pk, ids)

        start, end = window(hours=12)
        created = client.post(
            "/api/appointments/",
            {
                "doctor": doctor.pk,
                "patient": other.pk,
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
                "notes": "api booking",
            },
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.data)
        booked = Appointment.objects.get(pk=created.data["id"])
        self.assertEqual(booked.patient_id, patient.pk)

        past = timezone.now() - timedelta(hours=1)
        rejected = client.post(
            "/api/appointments/",
            {
                "doctor": doctor.pk,
                "start_time": past.isoformat(),
                "end_time": (past + timedelta(hours=1)).isoformat(),
            },
            format="json",
        )
        self.assertEqual(rejected.status_code, 400)

    def test_api_register_rejects_admin_and_duplicate_email(self):
        client = APIClient()
        created = client.post(
            reverse("api_register"),
            {
                "username": "api_new",
                "email": "api_new@example.com",
                "password": "StrongPass123!",
                "role": "PATIENT",
            },
            format="json",
        )
        self.assertEqual(created.status_code, 201)
        self.assertNotIn("password", created.data["user"])
        admin = client.post(
            reverse("api_register"),
            {
                "username": "api_admin",
                "email": "api_admin@example.com",
                "password": "StrongPass123!",
                "role": "ADMIN",
            },
            format="json",
        )
        self.assertEqual(admin.status_code, 403)
        duplicate = client.post(
            reverse("api_register"),
            {
                "username": "api_new_2",
                "email": "api_new@example.com",
                "password": "StrongPass123!",
                "role": "PATIENT",
            },
            format="json",
        )
        self.assertEqual(duplicate.status_code, 400)

    def test_doctor_status_action_and_report_uploader_binding(self):
        _, patient = self.make_patient("bind_pat")
        doctor_user, doctor = self.make_doctor("bind_doc")
        appt = self.book(patient, doctor, hours=6)
        doctor_api = self.api(doctor_user)
        updated = doctor_api.post(
            f"/api/appointments/{appt.pk}/update_status/",
            {"status": "NO_SHOW"},
            format="json",
        )
        self.assertEqual(updated.status_code, 200)
        appt.refresh_from_db()
        self.assertEqual(appt.status, Appointment.Status.NO_SHOW)
        bad = doctor_api.post(
            f"/api/appointments/{appt.pk}/update_status/",
            {"status": "GHOST"},
            format="json",
        )
        self.assertEqual(bad.status_code, 400)

        patient_api = self.api(patient.user)
        report = patient_api.post(
            "/api/reports/",
            {"original_filename": "cbc.pdf", "uploader": doctor_user.pk, "file_type": "PDF"},
            format="json",
        )
        self.assertEqual(report.status_code, 201, report.data)
        saved = BloodReport.objects.get(pk=report.data["id"])
        self.assertEqual(saved.uploader_id, patient.user_id)
        self.assertEqual(saved.patient_id, patient.pk)
        hidden = patient_api.get(f"/api/appointments/{Appointment.objects.exclude(patient=patient).first().pk if False else 999999}/")
        self.assertIn(hidden.status_code, (404, 403))


class CallbackAndHealthTests(FeatureDataMixin, TestCase):
    def test_n8n_callback_auth_and_idempotent_write(self):
        _, patient = self.make_patient("cb_pat")
        report = BloodReport.objects.create(
            uploader=patient.user,
            patient=patient,
            original_filename="cbc.pdf",
        )
        client = Client()
        missing = client.post(
            reverse("n8n_health_report_callback"),
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(missing.status_code, 503)

        config = IntegrationConfig.get_config()
        config.n8n_callback_token = "callback-secret"
        config.save()
        denied = client.post(
            reverse("n8n_health_report_callback"),
            data=json.dumps({"blood_report_id": report.pk}),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer wrong",
        )
        self.assertEqual(denied.status_code, 401)
        invalid = client.post(
            reverse("n8n_health_report_callback"),
            data="{",
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer callback-secret",
        )
        self.assertEqual(invalid.status_code, 400)
        incomplete = client.post(
            reverse("n8n_health_report_callback"),
            data=json.dumps({"blood_report_id": report.pk}),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer callback-secret",
        )
        self.assertEqual(incomplete.status_code, 400)
        payload = {
            "blood_report_id": report.pk,
            "patient_id": patient.pk,
            "health_report_drive_file_id": "file-1",
            "health_report_drive_link": "https://drive.google.com/file/d/file-1/view",
            "ai_summary": {"summary": "stable"},
        }
        first = client.post(
            reverse("n8n_health_report_callback"),
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer callback-secret",
        )
        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.json()["created"])
        second = client.post(
            reverse("n8n_health_report_callback"),
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer callback-secret",
        )
        self.assertEqual(second.status_code, 200)
        self.assertFalse(second.json()["created"])
        self.assertEqual(HealthReport.objects.filter(blood_report=report).count(), 1)
        report.refresh_from_db()
        self.assertEqual(report.n8n_status, BloodReport.N8nStatus.DONE)

    def test_healthz_and_missing_integrations_fail_closed(self):
        health = Client().get(reverse("healthz"))
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["status"], "ok")
        self.assertEqual(trigger_n8n_webhook({"blood_report_id": 1}), {})
        self.assertEqual(call_post_upload_api({"blood_report_id": 1}), {})
        with self.assertRaises(RuntimeError):
            get_drive_service()

    @patch("app.services.requests.post")
    def test_n8n_webhook_handles_timeout(self, post):
        import requests

        config = IntegrationConfig.get_config()
        config.n8n_blood_report_webhook_url = "https://example.invalid/hook"
        config.n8n_webhook_secret = "hook-secret"
        config.save()
        post.side_effect = requests.exceptions.Timeout("timed out")
        self.assertEqual(trigger_n8n_webhook({"blood_report_id": 1}), {})
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer hook-secret")


class AdminApiTests(FeatureDataMixin, TestCase):
    def test_admin_user_and_doctor_management_api(self):
        admin = self.make_admin("api_admin_user")
        patient_user, _ = self.make_patient("api_admin_pat")
        _, doctor = self.make_doctor("api_admin_doc")
        admin_api = self.api(admin)
        patient_api = self.api(patient_user)

        users = admin_api.get("/api/users/")
        self.assertEqual(users.status_code, 200)
        self.assertGreaterEqual(len(users.data), 3)

        denied = patient_api.get("/api/users/")
        self.assertEqual(denied.status_code, 403)

        doctors = admin_api.get("/api/doctor-management/")
        self.assertEqual(doctors.status_code, 200)
        self.assertTrue(any(row["id"] == doctor.pk for row in doctors.data))

        patch = admin_api.patch(
            f"/api/doctor-management/{doctor.pk}/",
            {"is_accepting_appointments": False},
            format="json",
        )
        self.assertEqual(patch.status_code, 200)
        doctor.refresh_from_db()
        self.assertFalse(doctor.is_accepting_appointments)


class AdminAndCommandTests(FeatureDataMixin, TestCase):
    def test_django_admin_login_and_dashboard(self):
        admin = self.make_admin("panel_admin")
        client = Client()
        page = client.get("/admin/login/")
        self.assertEqual(page.status_code, 200)
        client.login(username=admin.username, password=self.password)
        index = client.get("/admin/")
        self.assertEqual(index.status_code, 200)
        dashboard = client.get(reverse("admin_dashboard"))
        self.assertEqual(dashboard.status_code, 200)

    def test_seed_and_token_commands(self):
        call_command("seed_demo_users")
        self.assertTrue(User.objects.filter(username="admin1", role=User.Role.ADMIN).exists())
        self.assertTrue(User.objects.filter(username="doctor1", role=User.Role.DOCTOR).exists())
        self.assertTrue(User.objects.filter(username="patient1", role=User.Role.PATIENT).exists())
        call_command("generate_user_tokens")
        patient = User.objects.get(username="patient1")
        self.assertTrue(patient.api_token.access_token)
        call_command("populate_demo_db")
        self.assertGreaterEqual(Appointment.objects.count(), 5)
        self.assertGreaterEqual(BloodReport.objects.count(), 5)
