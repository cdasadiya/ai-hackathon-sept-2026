from django.core.management.base import BaseCommand
from django.db import transaction

from app.models import Department, DoctorProfile, PatientProfile, Specialty, User


class Command(BaseCommand):
    help = "Create/update demo users for each role (admin/doctor/patient) and seed departments/specialties."

    DEFAULT_PASSWORD = "Pass1234!"

    @transaction.atomic
    def handle(self, *args, **options):
        # Seed departments and specialties
        departments = ["Cardiology", "Neurology", "Orthopedics", "General Medicine", "Pathology"]
        specialties = ["Cardiologist", "Neurologist", "Orthopedic Surgeon", "General Physician", "Pathologist"]
        for name in departments:
            Department.objects.get_or_create(name=name)
        for name in specialties:
            Specialty.objects.get_or_create(name=name)
        self.stdout.write(self.style.SUCCESS("Seeded departments and specialties."))

        specs = [
            (User.Role.ADMIN, "admin", True, True),
            (User.Role.DOCTOR, "doctor", True, False),
            (User.Role.PATIENT, "patient", False, False),
        ]

        for role, prefix, is_staff, is_superuser in specs:
            for index in range(1, 4):
                username = f"{prefix}{index}"
                email = f"{username}@example.com"
                user, created = User.objects.get_or_create(
                    username=username,
                    defaults={"email": email, "role": role},
                )
                user.email = email
                user.role = role
                user.is_staff = is_staff
                user.is_superuser = is_superuser
                user.set_password(self.DEFAULT_PASSWORD)
                user.save()

                if role == User.Role.DOCTOR:
                    DoctorProfile.objects.get_or_create(user=user)
                elif role == User.Role.PATIENT:
                    PatientProfile.objects.get_or_create(user=user)

                action = "Created" if created else "Updated"
                self.stdout.write(self.style.SUCCESS(f"{action} {username} ({role})"))

        self.stdout.write(self.style.WARNING(f"\nDemo password for all users: {self.DEFAULT_PASSWORD}"))
        self.stdout.write(self.style.WARNING("Accounts: admin1/doctor1/doctor2/doctor3/patient1/patient2/patient3"))

