from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Appointment, DoctorProfile, PatientProfile, User

MAX_REPORT_SIZE_MB = 10
ALLOWED_CONTENT_TYPES = ("application/pdf", "image/jpeg", "image/png", "image/gif")


def _approved_doctors_qs():
    """Return queryset of approved, appointment-accepting doctors."""
    return DoctorProfile.objects.filter(
        verification_status=DoctorProfile.VerificationStatus.APPROVED,
        is_accepting_appointments=True,
    ).select_related("user", "specialty")


class RegistrationForm(UserCreationForm):
    """
    Public registration form. ADMIN role is intentionally excluded —
    admin accounts must be created via Django CLI (`createsuperuser`) or
    by an existing admin through Django Admin.
    """
    role = forms.ChoiceField(
        choices=[
            (User.Role.PATIENT, "Patient"),
            (User.Role.DOCTOR, "Doctor"),
        ],
        initial=User.Role.PATIENT,
        required=False,
    )

    def clean_role(self):
        role = self.cleaned_data.get("role") or User.Role.PATIENT
        if role == User.Role.ADMIN:
            raise ValidationError(
                "Admin accounts cannot be self-registered. "
                "Please contact an existing administrator."
            )
        return role

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            css_class = "form-select" if name == "role" else "form-control"
            field.widget.attrs["class"] = css_class

    class Meta:
        model = User
        fields = ("username", "email", "role")


# ─────────────────────────────────────────────────────────────────────────────
# Unified Appointment + Blood Report Form
# ─────────────────────────────────────────────────────────────────────────────

class UnifiedAppointmentForm(forms.ModelForm):
    """
    Single form that books an appointment and optionally attaches
    a blood report PDF in one transaction.
    Validates backdated times at both form and model level.
    """
    report_file = forms.FileField(
        required=False,
        label="Blood Report (PDF / Image, optional)",
        help_text="Accepted formats: PDF, JPEG, PNG. Maximum size: 10 MB.",
        widget=forms.FileInput(attrs={
            "class": "form-control",
            "accept": "application/pdf,image/*",
            "id": "id_report_file",
        }),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["doctor"].queryset = _approved_doctors_qs()
        self.fields["doctor"].label_from_instance = lambda obj: (
            f"Dr. {obj.user.get_full_name() or obj.user.username}"
            + (f" — {obj.specialty.name}" if obj.specialty else "")
        )
        # HTML5 min datetime: now + 1 hour (extra front-end guard)
        min_dt = (timezone.now() + timezone.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")
        self.fields["start_time"].widget.attrs["min"] = min_dt
        self.fields["end_time"].widget.attrs["min"] = min_dt
        # Placeholders
        self.fields["notes"].widget.attrs["placeholder"] = (
            "Optional notes or symptoms for your doctor…"
        )

    def clean_start_time(self):
        start_time = self.cleaned_data.get("start_time")
        if start_time:
            min_start = timezone.now() + timezone.timedelta(minutes=30)
            if start_time < min_start:
                raise ValidationError(
                    "Appointment must be at least 30 minutes in the future. "
                    "Backdated or near-current appointments are not allowed."
                )
        return start_time

    def clean_end_time(self):
        end_time = self.cleaned_data.get("end_time")
        start_time = self.cleaned_data.get("start_time")
        if end_time and start_time and end_time <= start_time:
            raise ValidationError("End time must be after start time.")
        return end_time

    def clean_report_file(self):
        report_file = self.cleaned_data.get("report_file")
        if not report_file:
            return report_file
        # File size check
        if report_file.size > MAX_REPORT_SIZE_MB * 1024 * 1024:
            raise ValidationError(
                f"File size exceeds {MAX_REPORT_SIZE_MB} MB limit. "
                "Please compress or use a smaller file."
            )
        # MIME type check
        if report_file.content_type not in ALLOWED_CONTENT_TYPES:
            raise ValidationError(
                "Only PDF, JPEG, or PNG files are accepted for blood reports."
            )
        return report_file

    class Meta:
        model = Appointment
        fields = ("doctor", "start_time", "end_time", "notes")
        widgets = {
            "doctor": forms.Select(attrs={"class": "form-select"}),
            "start_time": forms.DateTimeInput(
                attrs={"type": "datetime-local", "class": "form-control"},
                format="%Y-%m-%dT%H:%M",
            ),
            "end_time": forms.DateTimeInput(
                attrs={"type": "datetime-local", "class": "form-control"},
                format="%Y-%m-%dT%H:%M",
            ),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Legacy standalone appointment form (kept for API serializer compatibility)
# ─────────────────────────────────────────────────────────────────────────────

class AppointmentForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["doctor"].queryset = _approved_doctors_qs()
        self.fields["doctor"].label_from_instance = lambda obj: (
            f"Dr. {obj.user.get_full_name() or obj.user.username}"
            + (f" — {obj.specialty.name}" if obj.specialty else "")
        )
        min_dt = (timezone.now() + timezone.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")
        self.fields["start_time"].widget.attrs["min"] = min_dt
        self.fields["end_time"].widget.attrs["min"] = min_dt

    def clean_start_time(self):
        start_time = self.cleaned_data.get("start_time")
        if start_time and start_time <= timezone.now():
            raise ValidationError("Appointment start time must be in the future.")
        return start_time

    def clean_end_time(self):
        end_time = self.cleaned_data.get("end_time")
        start_time = self.cleaned_data.get("start_time")
        if end_time and start_time and end_time <= start_time:
            raise ValidationError("End time must be after start time.")
        return end_time

    class Meta:
        model = Appointment
        fields = ("doctor", "start_time", "end_time", "notes")
        widgets = {
            "doctor": forms.Select(attrs={"class": "form-select"}),
            "start_time": forms.DateTimeInput(
                attrs={"type": "datetime-local", "class": "form-control"},
                format="%Y-%m-%dT%H:%M",
            ),
            "end_time": forms.DateTimeInput(
                attrs={"type": "datetime-local", "class": "form-control"},
                format="%Y-%m-%dT%H:%M",
            ),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3,
                                           "placeholder": "Optional notes for your doctor..."}),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Doctor Remark + Status Form
# ─────────────────────────────────────────────────────────────────────────────

class DoctorRemarkForm(forms.Form):
    """Doctor updates appointment status and optionally adds review remarks."""
    status = forms.ChoiceField(
        choices=Appointment.Status.choices,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Appointment Status",
    )
    doctor_remarks = forms.CharField(
        required=False,
        max_length=2000,
        widget=forms.Textarea(attrs={
            "class": "form-control",
            "rows": 3,
            "placeholder": "Add clinical remarks, observations, or follow-up instructions…",
        }),
        label="Doctor Remarks / Review Notes",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Report Upload (standalone — for doctor upload panel)
# ─────────────────────────────────────────────────────────────────────────────

class ReportUploadForm(forms.Form):
    """Standalone report upload form used in doctor/patient upload panels."""
    appointment_id = forms.CharField(required=False, widget=forms.HiddenInput())
    report_file = forms.FileField(
        label="Blood Report File (PDF or Image)",
        widget=forms.FileInput(attrs={
            "class": "form-control",
            "accept": "application/pdf,image/*",
        }),
    )

    def clean_report_file(self):
        report_file = self.cleaned_data.get("report_file")
        if not report_file:
            return report_file
        if report_file.size > MAX_REPORT_SIZE_MB * 1024 * 1024:
            raise ValidationError(
                f"File exceeds {MAX_REPORT_SIZE_MB} MB limit."
            )
        if report_file.content_type not in ALLOWED_CONTENT_TYPES:
            raise ValidationError("Only PDF, JPEG, or PNG files are accepted.")
        return report_file


# ─────────────────────────────────────────────────────────────────────────────
# Comments & Profile Forms
# ─────────────────────────────────────────────────────────────────────────────

class ReportCommentForm(forms.Form):
    body = forms.CharField(
        widget=forms.Textarea(attrs={
            "class": "form-control",
            "rows": 3,
            "placeholder": "Add a remark or note...",
        }),
        max_length=2000,
        label="Comment / Remark",
    )


class PatientProfileForm(forms.ModelForm):
    """Allows patient to update their profile details."""
    first_name = forms.CharField(
        max_length=150, required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "First name"}),
    )
    last_name = forms.CharField(
        max_length=150, required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Last name"}),
    )

    class Meta:
        model = PatientProfile
        fields = ("phone", "dob", "blood_group", "address", "emergency_contact")
        widgets = {
            "phone": forms.TextInput(attrs={"class": "form-control", "placeholder": "+91 9876543210"}),
            "dob": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "blood_group": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. O+"}),
            "address": forms.Textarea(attrs={"class": "form-control", "rows": 2,
                                             "placeholder": "Home address"}),
            "emergency_contact": forms.TextInput(attrs={"class": "form-control",
                                                         "placeholder": "Emergency contact name & phone"}),
        }


class DoctorProfileForm(forms.ModelForm):
    """Allows doctor to update their professional details."""
    first_name = forms.CharField(
        max_length=150, required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "First name"}),
    )
    last_name = forms.CharField(
        max_length=150, required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Last name"}),
    )

    class Meta:
        model = DoctorProfile
        fields = ("bio", "availability_notes", "medical_license_no", "is_accepting_appointments")
        widgets = {
            "bio": forms.Textarea(attrs={"class": "form-control", "rows": 3,
                                         "placeholder": "Brief professional bio..."}),
            "availability_notes": forms.Textarea(attrs={"class": "form-control", "rows": 2,
                                                         "placeholder": "e.g., Mon–Fri 9am–5pm"}),
            "medical_license_no": forms.TextInput(attrs={"class": "form-control",
                                                          "placeholder": "License number"}),
            "is_accepting_appointments": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
