"""Seed command: creates test Admin, Doctor, Patient + appointment + blood report."""
import os
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.files import File


class Command(BaseCommand):
    help = "Seed test data: Admin, Doctor, Patient, Appointment, BloodReport."

    def handle(self, *args, **options):
        from app.models import (
            User, DoctorProfile, PatientProfile, Appointment,
            BloodReport, UserToken, ReportComment
        )

        # Admin
        if not User.objects.filter(username="admin_qa").exists():
            admin = User.objects.create_superuser(
                username="admin_qa", email="admin_qa@nexushealth.com",
                password="AdminPass@123", role=User.Role.ADMIN,
            )
            self.stdout.write(f"  Created admin: {admin.username}")
        else:
            self.stdout.write("  admin_qa already exists.")

        # Doctor
        if not User.objects.filter(username="doctor_qa").exists():
            doc_user = User.objects.create_user(
                username="doctor_qa", email="doctor_qa@nexushealth.com",
                password="DoctorPass@123", role=User.Role.DOCTOR,
                first_name="Dr. QA", last_name="Smith",
            )
            doc_profile = DoctorProfile.objects.create(
                user=doc_user,
                medical_license_no="ML-QA-001",
                bio="QA Test Doctor for automated testing.",
                availability_notes="Mon–Fri 9am–5pm",
                verification_status=DoctorProfile.VerificationStatus.APPROVED,
                is_accepting_appointments=True,
            )
            tok, _ = UserToken.objects.get_or_create(user=doc_user)
            tok.generate()
            self.stdout.write(f"  Created doctor: {doc_user.username}")
        else:
            doc_profile = DoctorProfile.objects.get(user__username="doctor_qa")
            self.stdout.write("  doctor_qa already exists.")

        # Patient
        if not User.objects.filter(username="patient_qa").exists():
            pat_user = User.objects.create_user(
                username="patient_qa", email="patient_qa@nexushealth.com",
                password="PatientPass@123", role=User.Role.PATIENT,
                first_name="QA", last_name="Patient",
            )
            pat_profile = PatientProfile.objects.create(
                user=pat_user, phone="+91 9876543210",
                blood_group="O+", address="123 Test Street, QA City",
            )
            tok, _ = UserToken.objects.get_or_create(user=pat_user)
            tok.generate()
            self.stdout.write(f"  Created patient: {pat_user.username}")
        else:
            pat_profile = PatientProfile.objects.get(user__username="patient_qa")
            self.stdout.write("  patient_qa already exists.")

        # Appointment
        future = timezone.now() + timezone.timedelta(days=3, hours=2)
        appt, created = Appointment.objects.get_or_create(
            patient=pat_profile, doctor=doc_profile,
            defaults={
                "start_time": future,
                "end_time": future + timezone.timedelta(hours=1),
                "notes": "QA test appointment — seeded by seed_test_data command.",
                "status": Appointment.Status.CONFIRMED,
            }
        )
        if created:
            self.stdout.write(f"  Created appointment: {appt.appointment_id}")
        else:
            self.stdout.write(f"  Appointment already exists: {appt.appointment_id}")

        # BloodReport using sample.pdf
        sample_path = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures", "sample.pdf")
        sample_path = os.path.normpath(sample_path)
        if BloodReport.objects.filter(appointment=appt).exists():
            self.stdout.write("  BloodReport already exists for this appointment.")
        elif os.path.exists(sample_path):
            from django.core.files.storage import FileSystemStorage
            fs = FileSystemStorage()
            with open(sample_path, "rb") as f:
                filename = f"qa_blood_report_seed.pdf"
                saved = fs.save(filename, File(f))
                file_url = f"/media/{saved}"
            report = BloodReport.objects.create(
                uploader=pat_profile.user,
                patient=pat_profile,
                appointment=appt,
                original_filename=filename,
                drive_file_id=filename,
                drive_link=file_url,
                file_type=BloodReport.FileType.PDF,
                n8n_status=BloodReport.N8nStatus.DONE,
                drive_folder_name="local_media",
                ai_analysis={"summary": "QA seed report — AI analysis placeholder.", "status": "NORMAL"},
            )
            self.stdout.write(f"  Created BloodReport: #{report.id}")
        else:
            self.stdout.write(f"  Sample PDF not found at {sample_path} — skipping BloodReport.")

        # Seed comment
        if not ReportComment.objects.filter(appointment=appt).exists():
            ReportComment.objects.create(
                appointment=appt,
                author=doc_profile.user,
                body="Initial QA doctor remark — please upload your blood report before the appointment.",
            )
            self.stdout.write("  Created doctor comment on appointment.")

        self.stdout.write(self.style.SUCCESS("\n✅ Seed complete. Credentials:"))
        self.stdout.write("  Admin  → admin_qa / AdminPass@123")
        self.stdout.write("  Doctor → doctor_qa / DoctorPass@123")
        self.stdout.write("  Patient→ patient_qa / PatientPass@123")
