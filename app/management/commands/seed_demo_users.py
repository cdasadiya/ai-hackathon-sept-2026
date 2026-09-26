from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from app.models import Department, DoctorProfile, PatientProfile, Specialty, User

# Shared with scripts/sync_live_roster.py so local seed and live registration stay aligned.
DOCTORS = [
    {
        "username": "doctor1",
        "first_name": "Aisha",
        "last_name": "Mehta",
        "bio": (
            "Consultant cardiologist focused on preventive heart checks, "
            "ECG review, and cholesterol management."
        ),
        "availability_notes": "Mon–Fri 09:00–17:00",
        "medical_license_no": "MH-MED-10421",
        "department": "Cardiology",
        "specialty": "Cardiologist",
    },
    {
        "username": "doctor2",
        "first_name": "Rohan",
        "last_name": "Iyer",
        "bio": "Neurologist seeing headache, migraine, and follow-up nerve studies.",
        "availability_notes": "Mon–Thu 10:00–18:00",
        "medical_license_no": "MH-MED-10422",
        "department": "Neurology",
        "specialty": "Neurologist",
    },
    {
        "username": "doctor3",
        "first_name": "Priya",
        "last_name": "Nair",
        "bio": "Orthopedic surgeon for joint pain, sports injuries, and fracture follow-up.",
        "availability_notes": "Tue–Sat 09:00–16:00",
        "medical_license_no": "MH-MED-10423",
        "department": "Orthopedics",
        "specialty": "Orthopedic Surgeon",
    },
    {
        "username": "doctor4",
        "first_name": "Vikram",
        "last_name": "Shah",
        "bio": (
            "General physician for fever workups, diabetes review, "
            "and routine blood-report interpretation."
        ),
        "availability_notes": "Mon–Sat 08:00–14:00",
        "medical_license_no": "MH-MED-10424",
        "department": "General Medicine",
        "specialty": "General Physician",
    },
    {
        "username": "doctor5",
        "first_name": "Neha",
        "last_name": "Kapoor",
        "bio": "Pathologist reviewing complete blood counts, lipid panels, and uploaded lab PDFs.",
        "availability_notes": "Mon–Fri 11:00–19:00",
        "medical_license_no": "MH-MED-10425",
        "department": "Pathology",
        "specialty": "Pathologist",
    },
]

PATIENTS = [
    {
        "username": "patient1",
        "first_name": "Arjun",
        "last_name": "Desai",
        "phone": "+91 9811111001",
        "dob": date(1990, 5, 15),
        "blood_group": "O+",
        "address": "12 Marine Drive, Mumbai 400020",
        "emergency_contact": "Kavita Desai +91 9811111101",
    },
    {
        "username": "patient2",
        "first_name": "Meera",
        "last_name": "Joshi",
        "phone": "+91 9811111002",
        "dob": date(1988, 8, 22),
        "blood_group": "A+",
        "address": "45 FC Road, Pune 411004",
        "emergency_contact": "Amit Joshi +91 9811111102",
    },
    {
        "username": "patient3",
        "first_name": "Kabir",
        "last_name": "Singh",
        "phone": "+91 9811111003",
        "dob": date(1995, 11, 3),
        "blood_group": "B+",
        "address": "8 CG Road, Ahmedabad 380009",
        "emergency_contact": "Simran Singh +91 9811111103",
    },
    {
        "username": "patient4",
        "first_name": "Ananya",
        "last_name": "Reddy",
        "phone": "+91 9811111004",
        "dob": date(1992, 2, 18),
        "blood_group": "AB+",
        "address": "22 Banjara Hills, Hyderabad 500034",
        "emergency_contact": "Ravi Reddy +91 9811111104",
    },
    {
        "username": "patient5",
        "first_name": "Dev",
        "last_name": "Patel",
        "phone": "+91 9811111005",
        "dob": date(1986, 12, 9),
        "blood_group": "O-",
        "address": "16 Ring Road, Surat 395003",
        "emergency_contact": "Nita Patel +91 9811111105",
    },
]


class Command(BaseCommand):
    help = "Create/update demo users for each role (admin/doctor/patient) and seed departments/specialties."

    DEFAULT_PASSWORD = "Pass1234!"

    @transaction.atomic
    def handle(self, *args, **options):
        departments = ["Cardiology", "Neurology", "Orthopedics", "General Medicine", "Pathology"]
        specialties = [
            "Cardiologist",
            "Neurologist",
            "Orthopedic Surgeon",
            "General Physician",
            "Pathologist",
        ]
        dept_map = {name: Department.objects.get_or_create(name=name)[0] for name in departments}
        spec_map = {name: Specialty.objects.get_or_create(name=name)[0] for name in specialties}
        self.stdout.write(self.style.SUCCESS("Seeded departments and specialties."))

        for index in range(1, 4):
            username = f"admin{index}"
            email = f"{username}@example.com"
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"email": email, "role": User.Role.ADMIN},
            )
            user.email = email
            user.role = User.Role.ADMIN
            user.is_staff = True
            user.is_superuser = True
            user.set_password(self.DEFAULT_PASSWORD)
            user.save()
            action = "Created" if created else "Updated"
            self.stdout.write(self.style.SUCCESS(f"{action} {username} (ADMIN)"))

        for row in DOCTORS:
            username = row["username"]
            email = f"{username}@example.com"
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"email": email, "role": User.Role.DOCTOR},
            )
            user.email = email
            user.role = User.Role.DOCTOR
            user.first_name = row["first_name"]
            user.last_name = row["last_name"]
            user.is_staff = True
            user.is_superuser = False
            user.set_password(self.DEFAULT_PASSWORD)
            user.save()

            profile, _ = DoctorProfile.objects.get_or_create(user=user)
            profile.department = dept_map[row["department"]]
            profile.specialty = spec_map[row["specialty"]]
            profile.bio = row["bio"]
            profile.availability_notes = row["availability_notes"]
            profile.medical_license_no = row["medical_license_no"]
            profile.verification_status = DoctorProfile.VerificationStatus.APPROVED
            profile.is_accepting_appointments = True
            profile.save()

            action = "Created" if created else "Updated"
            self.stdout.write(self.style.SUCCESS(f"{action} {username} (DOCTOR)"))

        for row in PATIENTS:
            username = row["username"]
            email = f"{username}@example.com"
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"email": email, "role": User.Role.PATIENT},
            )
            user.email = email
            user.role = User.Role.PATIENT
            user.first_name = row["first_name"]
            user.last_name = row["last_name"]
            user.is_staff = False
            user.is_superuser = False
            user.set_password(self.DEFAULT_PASSWORD)
            user.save()

            profile, _ = PatientProfile.objects.get_or_create(user=user)
            profile.phone = row["phone"]
            profile.dob = row["dob"]
            profile.blood_group = row["blood_group"]
            profile.address = row["address"]
            profile.emergency_contact = row["emergency_contact"]
            profile.save()

            action = "Created" if created else "Updated"
            self.stdout.write(self.style.SUCCESS(f"{action} {username} (PATIENT)"))

        self.stdout.write(self.style.WARNING(f"\nDemo password for all users: {self.DEFAULT_PASSWORD}"))
        self.stdout.write(
            self.style.WARNING(
                "Accounts: admin1–admin3, doctor1–doctor5, patient1–patient5"
            )
        )
