from django.test import Client, TestCase
from django.urls import reverse

from .models import DoctorProfile, PatientProfile, User


class RegistrationFlowTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_registration_form_defaults_role_to_patient(self):
        """New register page uses a card selector; verify the hidden input defaults to PATIENT."""
        response = self.client.get(reverse("register"))
        self.assertEqual(response.status_code, 200)
        # Card selector uses a hidden input with id="roleInput" defaulting to PATIENT
        self.assertContains(response, 'id="roleInput"')
        self.assertContains(response, 'value="PATIENT"')

    def test_register_patient_without_role_uses_default_patient(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "patient_default",
                "email": "patient_default@example.com",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        user = User.objects.get(username="patient_default")
        self.assertEqual(user.role, User.Role.PATIENT)


class RoleLoginResilienceTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_patient_login_works_even_if_profile_missing(self):
        user = User.objects.create_user(
            username="patient_no_profile",
            email="patient_no_profile@example.com",
            password="Pass1234!",
            role=User.Role.PATIENT,
        )
        PatientProfile.objects.filter(user=user).delete()

        response = self.client.post(
            reverse("login"),
            {"username": "patient_no_profile", "password": "Pass1234!"},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(PatientProfile.objects.filter(user=user).exists())

    def test_doctor_login_works_even_if_profile_missing(self):
        user = User.objects.create_user(
            username="doctor_no_profile",
            email="doctor_no_profile@example.com",
            password="Pass1234!",
            role=User.Role.DOCTOR,
        )
        DoctorProfile.objects.filter(user=user).delete()

        response = self.client.post(
            reverse("login"),
            {"username": "doctor_no_profile", "password": "Pass1234!"},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(DoctorProfile.objects.filter(user=user).exists())
    def test_login_normalizes_legacy_lowercase_role(self):
        user = User.objects.create_user(
            username="legacy_patient",
            email="legacy_patient@example.com",
            password="Pass1234!",
            role=User.Role.PATIENT,
        )
        User.objects.filter(pk=user.pk).update(role="patient")

        response = self.client.post(
            reverse("login"),
            {"username": "legacy_patient", "password": "Pass1234!"},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.role, User.Role.PATIENT)

