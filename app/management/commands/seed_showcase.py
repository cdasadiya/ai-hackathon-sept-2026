"""Idempotent showcase dataset shared by local and production databases.

Natural keys (usernames, appointment IDs, filenames) are fixed so a second run
updates the same rows instead of inserting duplicates. Times are absolute UTC
instants so both databases match even if the command runs at different moments.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand
from django.db import connection, transaction

from app.models import (
    Appointment,
    AuditLog,
    BloodReport,
    Department,
    DoctorProfile,
    HealthReport,
    IntegrationConfig,
    PatientProfile,
    ReportComment,
    Specialty,
    User,
    UserToken,
)

UTC = ZoneInfo("UTC")
PASSWORD = "Showcase123!"


def at(*parts):
    return datetime(*parts, tzinfo=UTC)


DEPARTMENTS = [
    "Cardiology",
    "Neurology",
    "Orthopedics",
    "General Medicine",
    "Pathology",
    "Pediatrics",
    "Dermatology",
    "ENT",
    "Oncology",
    "Endocrinology",
]
SPECIALTIES = [
    "Cardiologist",
    "Neurologist",
    "Orthopedic Surgeon",
    "General Physician",
    "Pathologist",
    "Pediatrician",
    "Dermatologist",
    "ENT Specialist",
    "Oncologist",
    "Endocrinologist",
]

# username, first, last, specialty, department, license, verification, accepting, active, verified, bio
DOCTORS = [
    ("case_doctor_01", "Asha", "Mehta", "Cardiologist", "Cardiology", "MH-CARD-1001", "APPROVED", True, True, True, "Interventional cardiologist. Accepts new patients on weekday mornings."),
    ("case_doctor_02", "Rohan", "Iyer", "Neurologist", "Neurology", "MH-NEUR-1002", "APPROVED", True, True, False, "Stroke and headache clinic. Evening slots on Tuesday and Thursday."),
    ("case_doctor_03", "Meera", "Kapoor", "Orthopedic Surgeon", "Orthopedics", "MH-ORTH-1003", "APPROVED", False, True, True, "Approved, but the clinic calendar is closed for new bookings."),
    ("case_doctor_04", "Vikram", "Shah", "General Physician", "General Medicine", "MH-GP-1004", "PENDING", True, True, False, "License uploaded. Waiting for admin verification."),
    ("case_doctor_05", "Neha", "Reddy", "Pathologist", "Pathology", "MH-PATH-1005", "REJECTED", False, True, False, "Verification was rejected. Documents need to be resubmitted."),
    ("case_doctor_06", "Arjun", "Desai", "Pediatrician", "Pediatrics", "MH-PED-1006", "APPROVED", True, False, True, "Account deactivated after a locum contract ended."),
    ("case_doctor_07", "Kavita", "Nair", "Dermatologist", "Dermatology", "MH-DERM-1007", "APPROVED", True, True, True, "Skin clinic with same-week follow-ups."),
    ("case_doctor_08", "Sameer", "Khan", "ENT Specialist", "ENT", "MH-ENT-1008", "APPROVED", True, True, False, "Ear, nose, and throat outpatient clinic."),
    ("case_doctor_09", "Lata", "Joshi", "Oncologist", "Oncology", "MH-ONC-1009", "APPROVED", True, True, True, "Consultation and lab-review oncology clinic."),
    ("case_doctor_10", "Imran", "Qureshi", "Endocrinologist", "Endocrinology", "", "APPROVED", True, True, False, ""),
]

# username, first, last, phone, dob, blood, address, emergency, active, verified
PATIENTS = [
    ("case_patient_01", "Priya", "Sharma", "+91 9811110001", "1992-04-18", "O+", "12 Linking Road, Mumbai", "Raj Sharma +91 9811110091", True, True),
    ("case_patient_02", "Amit", "Patel", "+91 9811110002", "1984-11-02", "A+", "44 CG Road, Ahmedabad", "Neelam Patel +91 9811110092", True, False),
    ("case_patient_03", "Sneha", "Gupta", "+91 9811110003", "1998-07-29", "B-", "9 Park Street, Kolkata", "Anil Gupta +91 9811110093", True, True),
    ("case_patient_04", "Rahul", "Verma", "+91 9811110004", "1976-01-14", "AB+", "88 Anna Salai, Chennai", "Pooja Verma +91 9811110094", True, False),
    ("case_patient_05", "Anjali", "Singh", "+91 9811110005", "2001-09-09", "O-", "3 Civil Lines, Lucknow", "Suresh Singh +91 9811110095", False, False),
    ("case_patient_06", "Karan", "Malhotra", "", "1990-12-25", "A-", "21 Sector 17, Chandigarh", "", True, True),
    ("case_patient_07", "Fatima", "Sheikh", "+91 9811110007", "1988-03-03", "B+", "6 Banjara Hills, Hyderabad", "Yusuf Sheikh +91 9811110097", True, False),
    ("case_patient_08", "Daniel", "Fernandes", "+91 9811110008", "1995-06-21", "AB-", "15 Panaji Market, Goa", "Maria Fernandes +91 9811110098", True, True),
    ("case_patient_09", "Meera", "Joshi", "+91 9811110009", "1971-10-30", "O+", "70 MI Road, Jaipur", "Dev Joshi +91 9811110099", True, False),
    ("case_patient_10", "Harpreet", "Kaur", "+91 9811110010", "1983-02-08", "", "4 Model Town, Ludhiana", "Gurpreet Kaur +91 9811110100", True, True),
]

# Fixed appointment catalog. Times stay identical across databases.
APPOINTMENTS = [
    {
        "appointment_id": "APT-2026-900001",
        "patient": "case_patient_01",
        "doctor": "case_doctor_01",
        "start": at(2026, 9, 10, 9, 0),
        "end": at(2026, 9, 10, 9, 30),
        "status": "COMPLETED",
        "notes": "Past visit. Annual cardiac review after a dizzy spell.",
        "remarks": "ECG reviewed. Continue current medication and repeat lipids in 8 weeks.",
        "created_at": at(2026, 9, 1, 8, 0),
    },
    {
        "appointment_id": "APT-2026-900002",
        "patient": "case_patient_02",
        "doctor": "case_doctor_02",
        "start": at(2026, 9, 12, 11, 0),
        "end": at(2026, 9, 12, 11, 45),
        "status": "CANCELLED",
        "notes": "Past visit cancelled by the patient the evening before.",
        "remarks": "",
        "created_at": at(2026, 9, 5, 10, 15),
    },
    {
        "appointment_id": "APT-2026-900003",
        "patient": "case_patient_03",
        "doctor": "case_doctor_06",
        "start": at(2026, 9, 18, 8, 0),
        "end": at(2026, 9, 18, 8, 30),
        "status": "NO_SHOW",
        "notes": "Past pediatric follow-up. Patient did not arrive.",
        "remarks": "Marked no-show. Reception attempted one phone call.",
        "created_at": at(2026, 9, 15, 6, 40),
    },
    {
        "appointment_id": "APT-2026-900004",
        "patient": "case_patient_04",
        "doctor": "case_doctor_07",
        "start": at(2026, 9, 26, 14, 45),
        "end": at(2026, 9, 26, 16, 15),
        "status": "CONFIRMED",
        "notes": "In-clinic visit happening on 26 Sep 2026. Rash review.",
        "remarks": "Exam in progress. Waiting on the image report pipeline.",
        "created_at": at(2026, 9, 24, 9, 0),
    },
    {
        "appointment_id": "APT-2026-900005",
        "patient": "case_patient_05",
        "doctor": "case_doctor_01",
        "start": at(2026, 9, 27, 4, 0),
        "end": at(2026, 9, 27, 4, 30),
        "status": "PENDING",
        "notes": "Next-day request from an inactive patient account. Still awaiting confirmation.",
        "remarks": "",
        "created_at": at(2026, 9, 26, 12, 0),
    },
    {
        "appointment_id": "APT-2026-900006",
        "patient": "case_patient_06",
        "doctor": "case_doctor_02",
        "start": at(2026, 9, 28, 10, 0),
        "end": at(2026, 9, 28, 11, 0),
        "status": "CONFIRMED",
        "notes": "Future neurology visit. Lab file uploaded and still queued.",
        "remarks": "",
        "created_at": at(2026, 9, 22, 11, 30),
    },
    {
        "appointment_id": "APT-2026-900007",
        "patient": "case_patient_07",
        "doctor": "case_doctor_08",
        "start": at(2026, 10, 2, 6, 30),
        "end": at(2026, 10, 2, 7, 15),
        "status": "PENDING",
        "notes": "Future ENT booking. Sinus symptoms for three weeks.",
        "remarks": "",
        "created_at": at(2026, 9, 25, 7, 20),
    },
    {
        "appointment_id": "APT-2026-900008",
        "patient": "case_patient_08",
        "doctor": "case_doctor_03",
        "start": at(2026, 10, 5, 13, 0),
        "end": at(2026, 10, 5, 13, 20),
        "status": "CANCELLED",
        "notes": "Future slot cancelled after the surgeon closed new bookings.",
        "remarks": "Cancelled because the doctor is not accepting appointments.",
        "created_at": at(2026, 9, 20, 4, 5),
    },
    {
        "appointment_id": "APT-2026-900009",
        "patient": "case_patient_10",
        "doctor": "case_doctor_10",
        "start": at(2026, 8, 20, 7, 0),
        "end": at(2026, 8, 20, 8, 0),
        "status": "COMPLETED",
        "notes": "Older endocrine review. Health report generated but not emailed.",
        "remarks": "HbA1c above target. Diet plan discussed.",
        "created_at": at(2026, 8, 12, 9, 45),
    },
    {
        "appointment_id": "APT-2026-900010",
        "patient": "case_patient_09",
        "doctor": "case_doctor_09",
        "start": at(2026, 11, 1, 9, 0),
        "end": at(2026, 11, 1, 9, 40),
        "status": "CONFIRMED",
        "notes": "Far-future oncology consult. No report attached yet.",
        "remarks": "",
        "created_at": at(2026, 9, 18, 15, 0),
    },
]

BLOOD_REPORTS = [
    ("cbc_priya_completed.pdf", "case_patient_01", "APT-2026-900001", "PDF", "DONE", "Patient blood reports", {"summary": "Lipid panel mildly high.", "flag": "BORDERLINE"}),
    ("rash_photo_rahul.jpg", "case_patient_04", "APT-2026-900004", "IMAGE", "PROCESSING", "Patient blood reports", {}),
    ("neuro_panel_karan.pdf", "case_patient_06", "APT-2026-900006", "PDF", "PENDING", "Patient blood reports", {}),
    ("sinus_labs_fatima.pdf", "case_patient_07", "APT-2026-900007", "PDF", "PROCESSING", "Patient blood reports", {"summary": "Analyzer started."}),
    ("knee_xray_daniel.jpg", "case_patient_08", "APT-2026-900008", "IMAGE", "FAILED", "Patient blood reports", {"error": "Unreadable image."}),
    ("hba1c_harpreet.pdf", "case_patient_10", "APT-2026-900009", "PDF", "DONE", "Patient blood reports", {"summary": "HbA1c 8.4%.", "flag": "HIGH"}),
    ("walkin_cbc_amit.pdf", "case_patient_02", "", "PDF", "DONE", "Patient blood reports", {"summary": "Standalone upload, no visit linked.", "flag": "NORMAL"}),
    ("unlinked_ferritin_sneha.pdf", "case_patient_03", "", "PDF", "FAILED", "Patient blood reports", {"error": "Webhook timeout."}),
    ("preview_thyroid_meera.pdf", "case_patient_09", "APT-2026-900010", "PDF", "PENDING", "Patient blood reports", {}),
    ("old_scan_anjali.png", "case_patient_05", "", "IMAGE", "DONE", "Patient blood reports", {"summary": "Archived image with no appointment."}),
    # Companion DONE labs so HealthReport can reach 10 while the files above keep PENDING/PROCESSING/FAILED coverage.
    ("lipid_followup_priya.pdf", "case_patient_01", "APT-2026-900001", "PDF", "DONE", "Patient blood reports", {"summary": "Repeat lipids after diet change.", "flag": "NORMAL"}),
    ("vitd_panel_rahul.pdf", "case_patient_04", "APT-2026-900004", "PDF", "DONE", "Patient blood reports", {"summary": "Vitamin D insufficient.", "flag": "LOW"}),
    ("iron_study_sneha.pdf", "case_patient_03", "", "PDF", "DONE", "Patient blood reports", {"summary": "Iron studies after ferritin failure retry.", "flag": "LOW"}),
    ("glucose_log_harpreet.pdf", "case_patient_10", "APT-2026-900009", "PDF", "DONE", "Patient blood reports", {"summary": "Home glucose log transcribed.", "flag": "HIGH"}),
    ("thyroid_full_meera.pdf", "case_patient_09", "APT-2026-900010", "PDF", "DONE", "Patient blood reports", {"summary": "Full thyroid panel for oncology prep."}),
    ("wellness_cbc_karan.pdf", "case_patient_06", "APT-2026-900006", "PDF", "DONE", "Patient blood reports", {"summary": "Baseline wellness CBC.", "flag": "NORMAL"}),
]

HEALTH_REPORTS = [
    ("cbc_priya_completed.pdf", "case_patient_01", "priya_health_report.pdf", {"summary": "Borderline cholesterol. Repeat in 8 weeks."}, at(2026, 9, 10, 12, 0)),
    ("hba1c_harpreet.pdf", "case_patient_10", "harpreet_health_report.pdf", {"summary": "Diabetes follow-up. Email not sent."}, None),
    ("walkin_cbc_amit.pdf", "case_patient_02", "amit_health_report.pdf", {"summary": "CBC within normal limits. Standalone walk-in."}, at(2026, 9, 21, 9, 0)),
    ("old_scan_anjali.png", "case_patient_05", "anjali_health_report.pdf", {"summary": "Archived image reviewed. No acute findings."}, None),
    ("lipid_followup_priya.pdf", "case_patient_01", "priya_lipid_health.pdf", {"summary": "Lipids improved after diet advice."}, at(2026, 9, 20, 12, 0)),
    ("vitd_panel_rahul.pdf", "case_patient_04", "rahul_vitd_health.pdf", {"summary": "Start vitamin D supplementation."}, at(2026, 9, 26, 17, 0)),
    ("iron_study_sneha.pdf", "case_patient_03", "sneha_iron_health.pdf", {"summary": "Iron deficiency. Dietary counseling."}, at(2026, 9, 23, 10, 0)),
    ("glucose_log_harpreet.pdf", "case_patient_10", "harpreet_glucose_health.pdf", {"summary": "Fasting glucose remains high."}, None),
    ("thyroid_full_meera.pdf", "case_patient_09", "meera_thyroid_health.pdf", {"summary": "TSH borderline. Recheck at oncology visit."}, None),
    ("wellness_cbc_karan.pdf", "case_patient_06", "karan_wellness_health.pdf", {"summary": "Wellness CBC unremarkable."}, at(2026, 9, 28, 7, 0)),
]

COMMENTS = [
    ("APT-2026-900001", "case_doctor_01", "Please keep the lipid sheet with your medicines.", at(2026, 9, 10, 9, 40)),
    ("APT-2026-900002", "case_patient_02", "I need to cancel. I am travelling.", at(2026, 9, 11, 18, 5)),
    ("APT-2026-900004", "case_doctor_07", "Photo received. I will compare it with last month.", at(2026, 9, 26, 15, 0)),
    ("APT-2026-900009", "case_doctor_10", "Bring the home glucose log next time.", at(2026, 8, 20, 8, 10)),
    ("APT-2026-900001", "case_patient_01", "Thank you doctor. I will book the lipid repeat.", at(2026, 9, 10, 10, 5)),
    ("APT-2026-900003", "case_doctor_06", "No-show recorded. Please rebook within two weeks.", at(2026, 9, 18, 9, 0)),
    ("APT-2026-900006", "case_patient_06", "I uploaded the neuro panel PDF for this visit.", at(2026, 9, 22, 12, 0)),
    ("APT-2026-900007", "case_doctor_08", "Sinus symptoms noted. Labs attached for review.", at(2026, 9, 25, 8, 0)),
    ("APT-2026-900008", "case_patient_08", "Understood — I will wait until bookings reopen.", at(2026, 9, 20, 5, 0)),
    ("APT-2026-900010", "case_doctor_09", "Bring prior oncology labs to the November visit.", at(2026, 9, 19, 10, 0)),
]

AUDIT_EVENTS = [
    ("case_doctor_01", "showcase.doctor.approved", {"username": "case_doctor_01"}, at(2026, 8, 1, 9, 0)),
    ("case_doctor_05", "showcase.doctor.rejected", {"username": "case_doctor_05"}, at(2026, 8, 2, 9, 0)),
    ("case_patient_01", "showcase.report.uploaded", {"file": "cbc_priya_completed.pdf"}, at(2026, 9, 10, 8, 50)),
    ("case_patient_02", "showcase.appointment.cancelled", {"appointment_id": "APT-2026-900002"}, at(2026, 9, 11, 18, 6)),
    ("case_doctor_07", "showcase.appointment.confirmed", {"appointment_id": "APT-2026-900004"}, at(2026, 9, 24, 9, 5)),
    ("case_doctor_04", "showcase.doctor.pending", {"username": "case_doctor_04"}, at(2026, 8, 3, 9, 0)),
    ("case_patient_06", "showcase.report.uploaded", {"file": "neuro_panel_karan.pdf"}, at(2026, 9, 22, 11, 45)),
    ("case_doctor_08", "showcase.appointment.pending", {"appointment_id": "APT-2026-900007"}, at(2026, 9, 25, 7, 25)),
    ("case_patient_08", "showcase.appointment.cancelled", {"appointment_id": "APT-2026-900008"}, at(2026, 9, 20, 4, 10)),
    ("case_doctor_09", "showcase.appointment.confirmed", {"appointment_id": "APT-2026-900010"}, at(2026, 9, 18, 15, 5)),
]


class Command(BaseCommand):
    help = "Create the shared 10-patient / 10-doctor / 10-appointment showcase dataset."

    def handle(self, *args, **options):
        locked = connection.vendor == "postgresql"
        if locked:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_lock(%s)", [867530901])
        try:
            with transaction.atomic():
                self._seed()
        finally:
            if locked:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_advisory_unlock(%s)", [867530901])

    def _seed(self):
        departments = {name: Department.objects.get_or_create(name=name)[0] for name in DEPARTMENTS}
        specialties = {name: Specialty.objects.get_or_create(name=name)[0] for name in SPECIALTIES}
        IntegrationConfig.get_config()

        doctors = {}
        for row in DOCTORS:
            username, first, last, spec, dept, license_no, verification, accepting, active, verified, bio = row
            user = self._user(username, User.Role.DOCTOR, first, last, active, verified)
            profile, _ = DoctorProfile.objects.get_or_create(user=user)
            profile.department = departments[dept]
            profile.specialty = specialties[spec]
            profile.medical_license_no = license_no
            profile.verification_status = verification
            profile.is_accepting_appointments = accepting
            profile.bio = bio
            profile.availability_notes = "Showcase calendar. Times below are fixed demo visits."
            profile.save()
            doctors[username] = profile
            self._token(user, revoked=False)

        patients = {}
        for row in PATIENTS:
            username, first, last, phone, dob, blood, address, emergency, active, verified = row
            user = self._user(username, User.Role.PATIENT, first, last, active, verified)
            profile, _ = PatientProfile.objects.get_or_create(user=user)
            profile.phone = phone
            profile.dob = date.fromisoformat(dob)
            profile.blood_group = blood
            profile.address = address
            profile.emergency_contact = emergency
            profile.save()
            patients[username] = profile
            self._token(user, revoked=(username == "case_patient_10"))

        appointments = {}
        for row in APPOINTMENTS:
            appt, _ = Appointment.objects.get_or_create(
                appointment_id=row["appointment_id"],
                defaults={
                    "patient": patients[row["patient"]],
                    "doctor": doctors[row["doctor"]],
                    "start_time": row["start"],
                    "end_time": row["end"],
                    "status": row["status"],
                    "notes": row["notes"],
                    "doctor_remarks": row["remarks"],
                },
            )
            appt.patient = patients[row["patient"]]
            appt.doctor = doctors[row["doctor"]]
            appt.start_time = row["start"]
            appt.end_time = row["end"]
            appt.status = row["status"]
            appt.notes = row["notes"]
            appt.doctor_remarks = row["remarks"]
            appt.save()
            Appointment.objects.filter(pk=appt.pk).update(created_at=row["created_at"])
            appointments[row["appointment_id"]] = appt

        reports = {}
        for filename, patient_name, appt_id, file_type, n8n_status, folder, analysis in BLOOD_REPORTS:
            patient = patients[patient_name]
            appointment = appointments.get(appt_id) if appt_id else None
            report, _ = BloodReport.objects.get_or_create(
                original_filename=filename,
                patient=patient,
                defaults={
                    "uploader": patient.user,
                    "appointment": appointment,
                    "file_type": file_type,
                    "n8n_status": n8n_status,
                    "drive_folder_name": folder,
                    "ai_analysis": analysis,
                    "drive_file_id": f"showcase-{filename}",
                    "drive_link": f"https://example.com/showcase/{filename}",
                    "uploaded_at": at(2026, 9, 20, 10, 0),
                },
            )
            report.uploader = patient.user
            report.appointment = appointment
            report.file_type = file_type
            report.n8n_status = n8n_status
            report.drive_folder_name = folder
            report.ai_analysis = analysis
            report.drive_file_id = f"showcase-{filename}"
            report.drive_link = f"https://example.com/showcase/{filename}"
            report.uploaded_at = at(2026, 9, 20, 10, 0)
            report.save()
            reports[filename] = report

        for filename, patient_name, health_name, summary, emailed_at in HEALTH_REPORTS:
            health, _ = HealthReport.objects.get_or_create(
                blood_report=reports[filename],
                defaults={
                    "patient": patients[patient_name],
                    "drive_file_id": f"showcase-{health_name}",
                    "drive_link": f"https://example.com/showcase/{health_name}",
                    "original_filename": health_name,
                    "ai_summary": summary,
                    "emailed_at": emailed_at,
                },
            )
            health.patient = patients[patient_name]
            health.drive_file_id = f"showcase-{health_name}"
            health.drive_link = f"https://example.com/showcase/{health_name}"
            health.original_filename = health_name
            health.ai_summary = summary
            health.emailed_at = emailed_at
            health.save()
            HealthReport.objects.filter(pk=health.pk).update(created_at=at(2026, 9, 20, 11, 0))

        for appt_id, author_name, body, created_at in COMMENTS:
            author = User.objects.get(username=author_name)
            comment, _ = ReportComment.objects.get_or_create(
                appointment=appointments[appt_id],
                author=author,
                body=body,
            )
            ReportComment.objects.filter(pk=comment.pk).update(created_at=created_at)

        for username, action, metadata, created_at in AUDIT_EVENTS:
            actor = User.objects.get(username=username)
            log, _ = AuditLog.objects.get_or_create(
                actor=actor,
                action=action,
                defaults={"metadata": metadata},
            )
            log.metadata = metadata
            log.save(update_fields=["metadata"])
            AuditLog.objects.filter(pk=log.pk).update(created_at=created_at)

        self.stdout.write(self.style.SUCCESS("Showcase dataset ready."))
        self.stdout.write(f"Password for case_patient_01..10 and case_doctor_01..10: {PASSWORD}")
        self.stdout.write(
            "Appointments APT-2026-900001..900010 cover completed, cancelled, no-show, "
            "pending, confirmed, past, in-progress, and future visits."
        )

    def _user(self, username, role, first, last, active, verified):
        user, _ = User.objects.get_or_create(
            username=username,
            defaults={"email": f"{username}@example.com", "role": role},
        )
        user.email = f"{username}@example.com"
        user.role = role
        user.first_name = first
        user.last_name = last
        user.is_active = active
        user.is_staff = False
        user.is_superuser = False
        user.email_verified = verified
        user.set_password(PASSWORD)
        user.save()
        return user

    def _token(self, user, revoked):
        token, _ = UserToken.objects.get_or_create(user=user)
        token.access_token = f"showcase-access-{user.username}"
        token.refresh_token = f"showcase-refresh-{user.username}"
        token.generated_at = at(2026, 9, 1, 0, 0)
        token.is_revoked = revoked
        token.revoked_at = at(2026, 9, 15, 0, 0) if revoked else None
        token.notes = "Showcase dataset token"
        token.save()
