from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from app.models import User, Specialty, Department, DoctorProfile, PatientProfile, Appointment, BloodReport

class Command(BaseCommand):
    help = 'Populates the database with 5 meaningful demo records.'

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting DB population...")

        # Admin User
        admin_user, created = User.objects.get_or_create(username="admin", email="admin@nexushealth.com", role=User.Role.ADMIN)
        if created:
            admin_user.set_password("Admin@123")
            admin_user.is_staff = True
            admin_user.is_superuser = True
            admin_user.save()
            self.stdout.write(self.style.SUCCESS("Created Admin User"))

        # Specialties
        s_cardio, _ = Specialty.objects.get_or_create(name="Cardiology")
        s_neuro, _ = Specialty.objects.get_or_create(name="Neurology")
        s_ortho, _ = Specialty.objects.get_or_create(name="Orthopedics")
        s_pedia, _ = Specialty.objects.get_or_create(name="Pediatrics")
        s_gp, _ = Specialty.objects.get_or_create(name="General Practice")

        # Departments
        d_cardio, _ = Department.objects.get_or_create(name="Cardiology Department")
        d_neuro, _ = Department.objects.get_or_create(name="Neurology Department")
        d_ortho, _ = Department.objects.get_or_create(name="Orthopedics Department")
        d_pedia, _ = Department.objects.get_or_create(name="Pediatrics Department")
        d_gp, _ = Department.objects.get_or_create(name="Outpatient Department")

        # Create 5 Doctors
        doctor_data = [
            ("drsmith", "smith@nexushealth.com", "Dr. John Smith", "DrSmith@123", s_cardio, d_cardio, "LIC-1001"),
            ("drjones", "jones@nexushealth.com", "Dr. Sarah Jones", "DrJones@123", s_neuro, d_neuro, "LIC-1002"),
            ("drbrown", "brown@nexushealth.com", "Dr. Michael Brown", "DrBrown@123", s_ortho, d_ortho, "LIC-1003"),
            ("drwhite", "white@nexushealth.com", "Dr. Emily White", "DrWhite@123", s_pedia, d_pedia, "LIC-1004"),
            ("drtaylor", "taylor@nexushealth.com", "Dr. David Taylor", "DrTaylor@123", s_gp, d_gp, "LIC-1005"),
        ]

        doctors = []
        for uname, email, fname, pwd, spec, dept, lic in doctor_data:
            user, created = User.objects.get_or_create(username=uname, email=email, role=User.Role.DOCTOR)
            if created:
                user.set_password(pwd)
                user.first_name = fname
                user.save()
                profile, _ = DoctorProfile.objects.get_or_create(user=user)
                profile.specialty = spec
                profile.department = dept
                profile.medical_license_no = lic
                profile.verification_status = DoctorProfile.VerificationStatus.APPROVED
                profile.save()
                self.stdout.write(self.style.SUCCESS(f"Created Doctor {fname}"))
            doctors.append(user.doctorprofile)

        # Create 5 Patients
        patient_data = [
            ("alice", "alice@email.com", "Alice Williams", "Alice@123", "555-0101", "1990-05-15"),
            ("bob", "bob@email.com", "Bob Davis", "Bob@123", "555-0102", "1985-08-22"),
            ("charlie", "charlie@email.com", "Charlie Miller", "Charlie@123", "555-0103", "1992-11-05"),
            ("diana", "diana@email.com", "Diana Wilson", "Diana@123", "555-0104", "1978-03-30"),
            ("evan", "evan@email.com", "Evan Moore", "Evan@123", "555-0105", "2000-12-12"),
        ]

        patients = []
        for uname, email, fname, pwd, phone, dob in patient_data:
            user, created = User.objects.get_or_create(username=uname, email=email, role=User.Role.PATIENT)
            if created:
                user.set_password(pwd)
                user.first_name = fname
                user.save()
                profile, _ = PatientProfile.objects.get_or_create(user=user)
                profile.phone = phone
                profile.dob = dob
                profile.save()
                self.stdout.write(self.style.SUCCESS(f"Created Patient {fname}"))
            patients.append(user.patientprofile)

        # Create 5 Appointments
        Appointment.objects.all().delete()
        
        now = timezone.now()
        appt_data = [
            (patients[0], doctors[0], now + timedelta(days=1, hours=2), now + timedelta(days=1, hours=3), "Regular checkup"),
            (patients[1], doctors[1], now + timedelta(days=2, hours=1), now + timedelta(days=2, hours=2), "Headache consultation"),
            (patients[2], doctors[2], now + timedelta(days=3, hours=4), now + timedelta(days=3, hours=5), "Knee pain"),
            (patients[3], doctors[3], now + timedelta(days=4, hours=2), now + timedelta(days=4, hours=3), "Child vaccination"),
            (patients[4], doctors[4], now + timedelta(days=5, hours=1), now + timedelta(days=5, hours=2), "Fever and cold"),
        ]

        appointments = []
        for pat, doc, start, end, notes in appt_data:
            appt = Appointment.objects.create(
                patient=pat, doctor=doc, start_time=start, end_time=end, notes=notes, status=Appointment.Status.CONFIRMED
            )
            appointments.append(appt)
            self.stdout.write(self.style.SUCCESS(f"Created Appointment for {pat.user.first_name} with {doc.user.first_name}"))

        # Create 5 Blood Reports
        BloodReport.objects.all().delete()
        ai_mock = {
            "summary": "Blood levels are mostly normal.",
            "anomalies": ["Slightly elevated cholesterol"],
            "recommendation": "Maintain a healthy diet."
        }

        report_data = [
            (patients[0].user, appointments[0], "cbc_report_alice.pdf"),
            (patients[1].user, appointments[1], "mri_summary_bob.pdf"),
            (patients[2].user, appointments[2], "xray_report_charlie.pdf"),
            (patients[3].user, appointments[3], "vaccine_history_diana.pdf"),
            (patients[4].user, appointments[4], "fever_blood_test_evan.pdf"),
        ]

        for user, appt, fname in report_data:
            BloodReport.objects.create(
                uploader=user,
                appointment=appt,
                original_filename=fname,
                drive_file_id="mock_drive_id_" + fname,
                drive_link="https://drive.google.com/open?id=mock",
                file_type=BloodReport.FileType.PDF,
                ai_analysis=ai_mock
            )
            self.stdout.write(self.style.SUCCESS(f"Created Blood Report {fname}"))

        self.stdout.write(self.style.SUCCESS("Database population completed successfully!"))
