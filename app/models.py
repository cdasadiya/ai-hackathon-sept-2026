from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Admin"
        DOCTOR = "DOCTOR", "Doctor"
        PATIENT = "PATIENT", "Patient"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.PATIENT)
    email = models.EmailField(unique=True)
    email_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    REQUIRED_FIELDS = ["email", "role"]


class Specialty(models.Model):
    name = models.CharField(max_length=120, unique=True)

    def __str__(self):
        return self.name


class Department(models.Model):
    name = models.CharField(max_length=120, unique=True)

    def __str__(self):
        return self.name


class DoctorProfile(models.Model):
    class VerificationStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    specialty = models.ForeignKey(Specialty, on_delete=models.SET_NULL, null=True, blank=True)
    bio = models.TextField(blank=True)
    availability_notes = models.TextField(blank=True)
    medical_license_no = models.CharField(max_length=120, blank=True)
    verification_status = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING,
    )
    is_accepting_appointments = models.BooleanField(default=True)

    def __str__(self):
        return f"Dr. {self.user.get_full_name() or self.user.username}"


class PatientProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    phone = models.CharField(max_length=20, blank=True)
    dob = models.DateField(null=True, blank=True)
    address = models.TextField(blank=True)
    emergency_contact = models.CharField(max_length=100, blank=True)
    blood_group = models.CharField(max_length=10, blank=True)

    def __str__(self):
        return self.user.get_full_name() or self.user.username


class Appointment(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CONFIRMED = "CONFIRMED", "Confirmed"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"
        NO_SHOW = "NO_SHOW", "No Show"

    # Human-readable unique appointment ID (APT-2026-000001)
    appointment_id = models.CharField(max_length=25, unique=True, blank=True, db_index=True)

    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE)
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    notes = models.TextField(blank=True)
    doctor_remarks = models.TextField(
        blank=True,
        default="",
        help_text="Doctor's review notes / remarks on this appointment.",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start_time"]

    def generate_appointment_id(self):
        """Generate APT-YYYY-NNNNNN format based on pk."""
        year = timezone.now().year
        return f"APT-{year}-{self.pk:06d}"

    def save(self, *args, **kwargs):
        # Django 6 accepts keyword arguments only on Model.save().
        if args:
            raise TypeError("Appointment.save() accepts keyword arguments only.")
        is_new = self.pk is None
        super().save(**kwargs)
        if is_new and not self.appointment_id:
            self.appointment_id = self.generate_appointment_id()
            Appointment.objects.filter(pk=self.pk).update(appointment_id=self.appointment_id)

    def clean(self):
        """Triple-layer backdating protection: model, form, and API levels."""
        now = timezone.now()
        # Require appointment at least 30 minutes in the future
        min_start = now + timezone.timedelta(minutes=30)
        if self.start_time and self.start_time < min_start:
            raise ValidationError(
                "Appointment must be scheduled at least 30 minutes from now. "
                "Past or near-future dates are not allowed."
            )
        if self.end_time and self.start_time and self.end_time <= self.start_time:
            raise ValidationError("End time must be later than start time.")
        if self.start_time and self.end_time and self.doctor_id:
            overlapping = Appointment.objects.filter(
                doctor=self.doctor,
                start_time__lt=self.end_time,
                end_time__gt=self.start_time,
                status__in=[self.Status.PENDING, self.Status.CONFIRMED],
            ).exclude(pk=self.pk)
            if overlapping.exists():
                raise ValidationError("Doctor already has an appointment in this timeslot.")
        if self.doctor_id and not self.doctor.is_accepting_appointments:
            raise ValidationError("Doctor is unavailable for booking.")

    def __str__(self):
        return f"{self.appointment_id or self.pk} — {self.patient} / {self.doctor}"


class ReportComment(models.Model):
    """Remarks/comments on an appointment by patient or doctor."""
    appointment = models.ForeignKey(
        Appointment, on_delete=models.CASCADE, related_name="comments"
    )
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment by {self.author.username} on {self.appointment}"


def blood_report_upload_path(instance, filename):
    """Store blood reports under media/blood_reports/<patient_id>/<filename>."""
    patient_id = instance.patient_id or "unknown"
    return f"blood_reports/{patient_id}/{filename}"


class BloodReport(models.Model):
    class FileType(models.TextChoices):
        PDF = "PDF", "PDF"
        IMAGE = "IMAGE", "Image"

    class N8nStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PROCESSING = "PROCESSING", "Processing"
        DONE = "DONE", "Done"
        FAILED = "FAILED", "Failed"

    uploader = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    patient = models.ForeignKey(
        "PatientProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="blood_reports",
    )
    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE, null=True, blank=True, related_name="blood_reports")
    # Actual file stored locally (preferred going forward)
    report_file = models.FileField(
        upload_to=blood_report_upload_path,
        null=True,
        blank=True,
        help_text="Uploaded PDF/image file stored on server.",
    )
    original_filename = models.CharField(max_length=255)
    # Legacy Google Drive fields — kept for backward compat with existing records
    drive_file_id = models.CharField(max_length=255, blank=True, default="")
    drive_link = models.URLField(blank=True, default="")
    file_type = models.CharField(max_length=10, choices=FileType.choices, default=FileType.PDF)
    ai_analysis = models.JSONField(default=dict, blank=True)
    uploaded_at = models.DateTimeField(default=timezone.now)

    # n8n pipeline tracking
    n8n_status = models.CharField(
        max_length=20,
        choices=N8nStatus.choices,
        default=N8nStatus.PENDING,
    )
    drive_folder_name = models.CharField(max_length=255, blank=True)

    def get_file_url(self):
        """Return the best available URL for the report file."""
        if self.report_file:
            return self.report_file.url
        return self.drive_link or None

    def __str__(self):
        return f"BloodReport #{self.pk} — {self.original_filename}"


class HealthReport(models.Model):
    """Generated by the n8n AI agent after processing a blood report."""

    blood_report = models.OneToOneField(BloodReport, on_delete=models.CASCADE, related_name="health_report")
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name="health_reports")
    drive_file_id = models.CharField(max_length=255)
    drive_link = models.URLField()
    original_filename = models.CharField(max_length=255)
    ai_summary = models.JSONField(default=dict, blank=True)
    emailed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"HealthReport #{self.pk} — patient {self.patient_id}"


class UserToken(models.Model):
    """Persistent JWT / API token per user. Managed exclusively by Admin."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="api_token",
    )
    access_token = models.TextField(blank=True)
    refresh_token = models.TextField(blank=True)
    generated_at = models.DateTimeField(null=True, blank=True)
    is_revoked = models.BooleanField(default=False)
    revoked_at = models.DateTimeField(null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True, help_text="Admin notes about this token.")

    class Meta:
        verbose_name = "User API Token"
        verbose_name_plural = "User API Tokens"

    def __str__(self):
        return f"Token for {self.user.username} ({'revoked' if self.is_revoked else 'active'})"

    def generate(self):
        """(Re)generate the access + refresh tokens and persist."""
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(self.user)
        self.refresh_token = str(refresh)
        self.access_token = str(refresh.access_token)
        self.generated_at = timezone.now()
        self.is_revoked = False
        self.revoked_at = None
        self.save(update_fields=["access_token", "refresh_token", "generated_at", "is_revoked", "revoked_at"])

    def revoke(self):
        self.is_revoked = True
        self.revoked_at = timezone.now()
        self.save(update_fields=["is_revoked", "revoked_at"])


class IntegrationConfig(models.Model):
    """
    Singleton model that stores all external API credentials.
    Managed exclusively from Django Admin → Integration Configuration.
    Only one row should ever exist (enforced via save()).
    """

    # ── Google Drive ──────────────────────────────────────────────────────────
    google_service_account_json = models.TextField(
        blank=True,
        help_text=(
            "Paste the full JSON key of your Google Cloud service account here. "
            "This is used to authenticate Drive API calls."
        ),
    )
    google_drive_root_folder_id = models.CharField(
        max_length=255,
        default="1-0RxsA0L1-0Qcp4qLYzBq5wyI2qauEjT",
        help_text="The root Google Drive folder ID that contains the 'Patient blood reports' and 'Patient health reports' sub-folders.",
    )

    # ── n8n Webhook ───────────────────────────────────────────────────────────
    n8n_blood_report_webhook_url = models.URLField(
        blank=True,
        help_text="Full URL of the n8n webhook that receives new blood report notifications.",
    )
    n8n_webhook_secret = models.CharField(
        max_length=255,
        blank=True,
        help_text="Shared secret sent as 'Authorization: Bearer <secret>' when calling n8n.",
    )
    n8n_callback_token = models.CharField(
        max_length=255,
        blank=True,
        help_text="Token that Django expects when n8n POSTs back the health report result.",
    )

    # ── JWT ───────────────────────────────────────────────────────────────────
    jwt_access_token_lifetime_minutes = models.PositiveIntegerField(
        default=60,
        help_text="Access token lifetime in minutes. Applied at runtime via SIMPLE_JWT setting.",
    )

    class Meta:
        verbose_name = "Integration Configuration"
        verbose_name_plural = "Integration Configuration"

    def __str__(self):
        return "Integration Configuration"

    def save(self, *args, **kwargs):
        """Enforce singleton: always use pk=1."""
        if args:
            raise TypeError("IntegrationConfig.save() accepts keyword arguments only.")
        self.pk = 1
        super().save(**kwargs)

    def delete(self, *args, **kwargs):
        """Prevent deletion of the singleton."""
        pass

    @classmethod
    def get_config(cls):
        """Return the singleton instance, creating it with defaults if needed."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class AuditLog(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=255)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.created_at:%Y-%m-%d %H:%M}] {self.actor} — {self.action}"
