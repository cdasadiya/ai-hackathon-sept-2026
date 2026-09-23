from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils import timezone

from .models import (
    Appointment, AuditLog, BloodReport, Department, DoctorProfile,
    HealthReport, IntegrationConfig, PatientProfile, ReportComment,
    Specialty, User, UserToken,
)

admin.site.site_header = "NexusHealth Admin Portal"
admin.site.site_title = "NexusHealth"
admin.site.index_title = "Platform Administration"


# ─── Inlines ──────────────────────────────────────────────────────────────────

class BloodReportInline(admin.TabularInline):
    model = BloodReport
    extra = 0
    fields = ("original_filename", "file_type", "n8n_status", "report_file_link", "uploaded_at")
    readonly_fields = ("original_filename", "file_type", "n8n_status", "report_file_link", "uploaded_at")

    def report_file_link(self, obj):
        url = obj.get_file_url()
        if url:
            return format_html('<a href="{}" target="_blank">📄 View</a>', url)
        return "—"
    report_file_link.short_description = "File"


class AppointmentInline(admin.TabularInline):
    model = Appointment
    extra = 0
    fields = ("appointment_id", "doctor", "start_time", "status")
    readonly_fields = ("appointment_id", "start_time")
    ordering = ("-start_time",)


class ReportCommentInline(admin.TabularInline):
    model = ReportComment
    extra = 0
    fields = ("author", "body", "created_at")
    readonly_fields = ("author", "body", "created_at")


# ─── User ──────────────────────────────────────────────────────────────────────

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "role", "is_staff", "is_active", "date_joined")
    list_filter = ("role", "is_staff", "is_active")
    search_fields = ("username", "email", "first_name", "last_name")
    ordering = ("-date_joined",)
    list_per_page = 25
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "email")}),
        ("Role & Permissions", {"fields": ("role", "is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("username", "email", "role", "password1", "password2", "is_staff", "is_superuser")}),
    )


# ─── DoctorProfile ─────────────────────────────────────────────────────────────

@admin.register(DoctorProfile)
class DoctorProfileAdmin(admin.ModelAdmin):
    list_display = ("get_username", "get_email", "verification_status", "is_accepting_appointments", "medical_license_no", "specialty", "department")
    list_filter = ("verification_status", "is_accepting_appointments", "specialty", "department")
    search_fields = ("user__username", "user__email", "user__first_name", "medical_license_no")
    ordering = ("verification_status", "user__username")
    list_per_page = 25
    readonly_fields = ("user",)
    actions = ["approve_doctors", "reject_doctors"]
    fieldsets = (
        ("Account", {"fields": ("user",)}),
        ("Professional Info", {"fields": ("specialty", "department", "medical_license_no", "bio", "availability_notes")}),
        ("Status", {"fields": ("verification_status", "is_accepting_appointments")}),
    )

    def get_username(self, obj): return obj.user.username
    get_username.short_description = "Username"

    def get_email(self, obj): return obj.user.email
    get_email.short_description = "Email"

    @admin.action(description="✅ Approve selected doctors")
    def approve_doctors(self, request, queryset):
        from .views import _get_or_create_user_token
        updated = queryset.update(verification_status=DoctorProfile.VerificationStatus.APPROVED)
        for doc in queryset:
            try:
                _get_or_create_user_token(doc.user)
            except Exception:
                pass
        self.message_user(request, f"{updated} doctor(s) approved & tokens generated.", messages.SUCCESS)

    @admin.action(description="❌ Reject selected doctors")
    def reject_doctors(self, request, queryset):
        updated = queryset.update(verification_status=DoctorProfile.VerificationStatus.REJECTED)
        self.message_user(request, f"{updated} doctor(s) rejected.", messages.WARNING)


# ─── PatientProfile ────────────────────────────────────────────────────────────

@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
    list_display = ("get_username", "get_email", "phone", "dob", "blood_group", "appointment_count")
    search_fields = ("user__username", "user__email", "phone")
    list_per_page = 25
    readonly_fields = ("user",)
    inlines = [AppointmentInline]

    def get_username(self, obj): return obj.user.username
    get_username.short_description = "Username"

    def get_email(self, obj): return obj.user.email
    get_email.short_description = "Email"

    def appointment_count(self, obj):
        return obj.appointments.count() if hasattr(obj, "appointments") else Appointment.objects.filter(patient=obj).count()
    appointment_count.short_description = "Appointments"


# ─── Appointment ───────────────────────────────────────────────────────────────

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("appointment_id", "get_patient", "get_doctor", "start_time", "end_time", "status", "has_report", "created_at")
    list_filter = ("status", "start_time")
    search_fields = ("appointment_id", "patient__user__username", "doctor__user__username", "notes")
    readonly_fields = ("appointment_id", "created_at")
    ordering = ("-created_at",)
    list_per_page = 25
    date_hierarchy = "start_time"
    inlines = [BloodReportInline, ReportCommentInline]
    actions = ["mark_completed", "mark_confirmed"]
    fieldsets = (
        ("Identifiers", {"fields": ("appointment_id",)}),
        ("Participants", {"fields": ("patient", "doctor")}),
        ("Schedule", {"fields": ("start_time", "end_time")}),
        ("Content", {"fields": ("notes", "doctor_remarks", "status")}),
        ("Meta", {"fields": ("created_at",)}),
    )

    def get_patient(self, obj): return obj.patient.user.username
    get_patient.short_description = "Patient"

    def get_doctor(self, obj): return f"Dr. {obj.doctor.user.get_full_name() or obj.doctor.user.username}"
    get_doctor.short_description = "Doctor"

    def has_report(self, obj):
        return obj.blood_reports.exists()
    has_report.boolean = True
    has_report.short_description = "Report"

    @admin.action(description="✅ Mark selected appointments as Completed")
    def mark_completed(self, request, queryset):
        updated = queryset.update(status=Appointment.Status.COMPLETED)
        self.message_user(request, f"{updated} appointment(s) marked completed.", messages.SUCCESS)

    @admin.action(description="📅 Mark selected appointments as Confirmed")
    def mark_confirmed(self, request, queryset):
        updated = queryset.update(status=Appointment.Status.CONFIRMED)
        self.message_user(request, f"{updated} appointment(s) confirmed.", messages.SUCCESS)


# ─── BloodReport ───────────────────────────────────────────────────────────────

@admin.register(BloodReport)
class BloodReportAdmin(admin.ModelAdmin):
    list_display = ("id", "get_patient_name", "original_filename", "n8n_status", "file_type", "uploaded_at", "file_link_display")
    list_filter = ("n8n_status", "file_type", "uploaded_at")
    search_fields = ("uploader__username", "original_filename", "patient__user__username")
    readonly_fields = ("uploaded_at", "file_link_display")
    ordering = ("-uploaded_at",)
    list_per_page = 25
    list_select_related = ("uploader", "patient__user", "appointment")

    def get_patient_name(self, obj):
        if obj.patient: return obj.patient.user.username
        return obj.uploader.username
    get_patient_name.short_description = "Patient"

    def file_link_display(self, obj):
        url = obj.get_file_url()
        if url:
            return format_html('<a href="{}" target="_blank">📄 Open File ↗</a>', url)
        return "—"
    file_link_display.short_description = "File"


# ─── HealthReport ──────────────────────────────────────────────────────────────

@admin.register(HealthReport)
class HealthReportAdmin(admin.ModelAdmin):
    list_display = ("id", "patient", "blood_report", "original_filename", "emailed_at", "created_at", "drive_link_display")
    list_filter = ("emailed_at", "created_at")
    search_fields = ("patient__user__username", "original_filename")
    readonly_fields = ("created_at", "drive_link_display")
    ordering = ("-created_at",)

    def drive_link_display(self, obj):
        if obj.drive_link:
            return format_html('<a href="{}" target="_blank">Open ↗</a>', obj.drive_link)
        return "—"
    drive_link_display.short_description = "Health Report Link"


# ─── ReportComment ─────────────────────────────────────────────────────────────

@admin.register(ReportComment)
class ReportCommentAdmin(admin.ModelAdmin):
    list_display = ("id", "appointment", "author", "body_preview", "created_at")
    search_fields = ("appointment__appointment_id", "author__username", "body")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)

    def body_preview(self, obj): return obj.body[:60] + ("…" if len(obj.body) > 60 else "")
    body_preview.short_description = "Comment"


# ─── UserToken ─────────────────────────────────────────────────────────────────

@admin.register(UserToken)
class UserTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "get_role", "is_revoked", "generated_at", "revoked_at", "short_token", "notes")
    list_filter = ("is_revoked", "user__role")
    search_fields = ("user__username", "user__email")
    readonly_fields = ("access_token", "refresh_token", "generated_at", "revoked_at")
    ordering = ("-generated_at",)
    list_per_page = 25
    actions = ["action_generate_tokens", "action_revoke_tokens"]
    fieldsets = (
        ("User", {"fields": ("user", "notes")}),
        ("Token Data (read-only)", {"fields": ("access_token", "refresh_token", "generated_at")}),
        ("Revocation", {"fields": ("is_revoked", "revoked_at")}),
    )

    def get_role(self, obj): return obj.user.role
    get_role.short_description = "Role"

    def short_token(self, obj):
        if obj.access_token:
            return obj.access_token[:30] + "…"
        return "—"
    short_token.short_description = "Access Token (preview)"

    @admin.action(description="🔑 Generate / Regenerate tokens for selected users")
    def action_generate_tokens(self, request, queryset):
        count = sum(1 for ut in queryset if not (ut.generate() or False) or True)
        self.message_user(request, f"Generated tokens for {count} user(s).", messages.SUCCESS)

    @admin.action(description="🚫 Revoke tokens for selected users")
    def action_revoke_tokens(self, request, queryset):
        count = sum(1 for ut in queryset if not (ut.revoke() or False) or True)
        self.message_user(request, f"Revoked tokens for {count} user(s).", messages.WARNING)


# ─── IntegrationConfig ─────────────────────────────────────────────────────────

@admin.register(IntegrationConfig)
class IntegrationConfigAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Google Drive", {"fields": ("google_service_account_json", "google_drive_root_folder_id")}),
        ("n8n Webhook", {"fields": ("n8n_blood_report_webhook_url", "n8n_webhook_secret", "n8n_callback_token")}),
        ("JWT Settings", {
            "fields": ("jwt_access_token_lifetime_minutes",),
            "description": "Access token lifetime in minutes. Refresh tokens valid for 30 days.",
        }),
    )

    def get_form(self, request, obj=None, **kwargs):
        from django import forms as dj_forms
        form = super().get_form(request, obj, **kwargs)
        form.base_fields["google_service_account_json"].widget = dj_forms.Textarea(
            attrs={"rows": 10, "cols": 80, "style": "font-family:monospace;font-size:12px;"}
        )
        return form

    def get_urls(self):
        urls = super().get_urls()
        custom = [path("test-drive/", self.admin_site.admin_view(self.test_drive_connection), name="app_integrationconfig_test_drive")]
        return custom + urls

    def changelist_view(self, request, extra_context=None):
        try:
            obj, _ = IntegrationConfig.objects.get_or_create(pk=1)
            return HttpResponseRedirect(reverse("admin:app_integrationconfig_change", args=[obj.pk]))
        except Exception:
            return super().changelist_view(request, extra_context)

    def has_add_permission(self, request):
        try: return not IntegrationConfig.objects.exists()
        except Exception: return True

    def has_delete_permission(self, request, obj=None): return False

    def test_drive_connection(self, request):
        try:
            from .services import get_drive_service
            service = get_drive_service()
            config = IntegrationConfig.get_config()
            result = service.files().list(
                q=f"'{config.google_drive_root_folder_id}' in parents and trashed=false",
                pageSize=1, fields="files(id,name)"
            ).execute()
            self.message_user(request, f"✅ Drive OK — {len(result.get('files', []))} item(s) found.", messages.SUCCESS)
        except Exception as exc:
            self.message_user(request, f"❌ Drive failed: {exc}", messages.ERROR)
        return HttpResponseRedirect(reverse("admin:app_integrationconfig_change", args=[1]))


# ─── AuditLog ──────────────────────────────────────────────────────────────────

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "action", "metadata_preview")
    list_filter = ("created_at",)
    search_fields = ("actor__username", "action")
    readonly_fields = ("created_at", "actor", "action", "metadata")
    ordering = ("-created_at",)
    list_per_page = 50

    def metadata_preview(self, obj):
        s = str(obj.metadata)
        return s[:80] + "…" if len(s) > 80 else s
    metadata_preview.short_description = "Metadata"

    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False


# ─── Specialty / Department ────────────────────────────────────────────────────

@admin.register(Specialty)
class SpecialtyAdmin(admin.ModelAdmin):
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    search_fields = ("name",)
    ordering = ("name",)
