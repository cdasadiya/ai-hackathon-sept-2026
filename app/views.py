import logging, os, threading, json as _json
from django.contrib import messages
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import connection
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views import View
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from .forms import AppointmentForm, UnifiedAppointmentForm, DoctorRemarkForm, ReportUploadForm, RegistrationForm, PatientProfileForm, DoctorProfileForm, ReportCommentForm
from .models import Appointment, BloodReport, DoctorProfile, HealthReport, PatientProfile, ReportComment, User, UserToken
from .permissions import IsAdmin, IsDoctorOrAdmin, IsPatient
from .serializers import AppointmentSerializer, BloodReportSerializer, DoctorProfileSerializer, UserSerializer, RegisterSerializer
from .services import trigger_n8n_webhook_async

logger = logging.getLogger(__name__)

def _normalize_role(role_value):
    if not role_value: return User.Role.PATIENT
    normalized = role_value.upper()
    valid_roles = {c for c, _ in User.Role.choices}
    return normalized if normalized in valid_roles else User.Role.PATIENT

def _resolve_patient_profile(user, appointment=None):
    if user.role == User.Role.PATIENT:
        return PatientProfile.objects.filter(user=user).first()
    if user.role == User.Role.DOCTOR and appointment:
        return appointment.patient
    return None

def _get_or_create_user_token(user):
    token, created = UserToken.objects.get_or_create(user=user)
    if created or not token.access_token:
        token.generate()
    return token

def home(request):
    if request.user.is_authenticated:
        if request.user.role == User.Role.ADMIN: return redirect("admin_dashboard")
        if request.user.role == User.Role.DOCTOR: return redirect("doctor_dashboard")
        return redirect("patient_dashboard")
    return render(request, "home.html", {})

def healthz(request):
    if settings.HEALTHZ_RUN_MIGRATIONS:
        from django.core.management import call_command
        try:
            call_command("migrate", interactive=False, verbosity=0)
        except Exception as exc:
            return JsonResponse({"status": "error", "message": str(exc)}, status=503)
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()
    try:
        from .models import IntegrationConfig
        IntegrationConfig.get_config()
    except Exception:
        pass
    return JsonResponse({
        "status": "ok",
        "message": "Database reachable.",
        "revision": os.getenv("RENDER_GIT_COMMIT", "")[:12],
    })

@login_required
def debug_admin(request):
    if not request.user.is_staff:
        return JsonResponse({"detail": "Forbidden"}, status=403)
    return JsonResponse({"status": "ok", "user": request.user.username})


class RoleLoginView(LoginView):
    template_name = "auth/login.html"
    def form_valid(self, form):
        user = form.get_user()
        if not user.is_active:
            form.add_error(None, "Inactive users cannot login.")
            return self.form_invalid(form)
        user.role = _normalize_role(user.role)
        update_fields = ["role"]
        if user.role == User.Role.ADMIN and not user.is_staff:
            user.is_staff = True; update_fields.append("is_staff")
        user.save(update_fields=update_fields)
        if user.role == User.Role.PATIENT:
            PatientProfile.objects.get_or_create(user=user)
        elif user.role == User.Role.DOCTOR:
            DoctorProfile.objects.get_or_create(user=user)
        if user.role in [User.Role.PATIENT, User.Role.DOCTOR]:
            _get_or_create_user_token(user)
        return super().form_valid(form)
    def get_success_url(self):
        role = _normalize_role(self.request.user.role)
        if role == User.Role.ADMIN: return "/dashboard/admin/"
        if role == User.Role.DOCTOR: return "/doctor/dashboard/"
        return "/patient/dashboard/"

class RegisterView(View):
    template_name = "auth/register.html"
    def get(self, request):
        if request.user.is_authenticated: return redirect("home")
        return render(request, self.template_name, {"form": RegistrationForm()})
    def post(self, request):
        try:
            form = RegistrationForm(request.POST)
            if form.is_valid():
                user = form.save(commit=False)
                if user.role == User.Role.ADMIN:
                    messages.error(request, "Admin accounts cannot be self-registered.")
                    return render(request, self.template_name, {"form": form})
                user.save()
                if user.role == User.Role.PATIENT:
                    PatientProfile.objects.create(user=user)
                elif user.role == User.Role.DOCTOR:
                    DoctorProfile.objects.create(user=user)
                _get_or_create_user_token(user)
                login(request, user, backend=settings.AUTHENTICATION_BACKENDS[0])
                messages.success(request, f"Welcome, {user.username}! Your account has been created.")
                if user.role == User.Role.DOCTOR: return redirect("doctor_dashboard")
                return redirect("patient_dashboard")
            return render(request, self.template_name, {"form": form})
        except Exception:
            logger.exception("Registration failed")
            messages.error(request, "Registration could not be completed. Please try again.")
            return render(request, self.template_name, {"form": RegistrationForm(request.POST)})

def custom_logout(request):
    from django.contrib.auth import logout
    logout(request); return redirect("home")


@login_required
def admin_dashboard(request):
    if request.user.role != User.Role.ADMIN:
        messages.error(request, "Access denied. Admin role required.")
        return redirect("home")
    total_users = User.objects.count()
    total_patients = PatientProfile.objects.count()
    total_doctors = DoctorProfile.objects.count()
    active_doctors = DoctorProfile.objects.filter(user__is_active=True, verification_status=DoctorProfile.VerificationStatus.APPROVED).count()
    pending_doctors = DoctorProfile.objects.filter(verification_status=DoctorProfile.VerificationStatus.PENDING).count()
    total_appointments = Appointment.objects.count()
    total_reports = BloodReport.objects.count()
    ctx = {
        "stats": [
            ("bi bi-people-fill", "#4f46e5", total_users, "Total Users"),
            ("bi bi-person-heart", "#0ea5e9", total_patients, "Patients"),
            ("bi bi-person-badge", "#10b981", active_doctors, "Active Doctors"),
            ("bi bi-calendar3", "#f59e0b", total_appointments, "Appointments"),
            ("bi bi-droplet-fill", "#ef4444", total_reports, "Blood Reports"),
            ("bi bi-hourglass-split", "#8b5cf6", pending_doctors, "Pending Doctors"),
        ],
        "pending_doctors": pending_doctors,
        "recent_users": User.objects.order_by("-date_joined")[:5],
        "recent_appointments": Appointment.objects.select_related("patient__user", "doctor__user").order_by("-created_at")[:10],
        "all_doctors": DoctorProfile.objects.select_related("user").order_by("verification_status", "user__username"),
    }
    return render(request, "admin/dashboard.html", ctx)

@login_required
def patient_dashboard(request):
    if request.user.role != User.Role.PATIENT:
        messages.error(request, "Access denied."); return redirect("home")
    profile = get_object_or_404(PatientProfile, user=request.user)
    tab = request.GET.get("tab", "upcoming")
    search = request.GET.get("search", "").strip()
    qs = Appointment.objects.filter(patient=profile).select_related("doctor__user", "doctor__specialty")
    if search:
        qs = qs.filter(Q(doctor__user__username__icontains=search) | Q(appointment_id__icontains=search) | Q(notes__icontains=search))
    now = timezone.now()
    if tab == "upcoming": qs = qs.filter(start_time__gte=now, status__in=[Appointment.Status.PENDING, Appointment.Status.CONFIRMED])
    elif tab == "past": qs = qs.filter(start_time__lt=now)
    elif tab == "cancelled": qs = qs.filter(status=Appointment.Status.CANCELLED)
    elif tab == "completed": qs = qs.filter(status=Appointment.Status.COMPLETED)
    qs = qs.order_by("-start_time")
    paginator = Paginator(qs, 10)
    page = paginator.get_page(request.GET.get("page", 1))
    all_appts = Appointment.objects.filter(patient=profile).order_by("-start_time")
    blood_reports = BloodReport.objects.filter(patient=profile).select_related("appointment").order_by("-uploaded_at")
    return render(request, "patient/dashboard.html", {
        "appointments": page, "all_appointments": all_appts,
        "blood_reports": blood_reports,
        "form": UnifiedAppointmentForm(), "profile": profile,
        "tab": tab, "search": search, "now": now,
        "status_choices": Appointment.Status.choices,
    })

@login_required
def patient_appointment_detail(request, appointment_id):
    if request.user.role != User.Role.PATIENT:
        messages.error(request, "Access denied."); return redirect("home")
    profile = get_object_or_404(PatientProfile, user=request.user)
    appt = get_object_or_404(Appointment, appointment_id=appointment_id, patient=profile)
    report = BloodReport.objects.filter(appointment=appt).first()
    comments = appt.comments.select_related("author").all()
    comment_form = ReportCommentForm()
    return render(request, "patient/appointment_detail.html", {
        "appt": appt, "report": report, "comments": comments,
        "comment_form": comment_form, "profile": profile,
    })


@login_required
def book_appointment(request):
    if request.user.role != User.Role.PATIENT:
        return JsonResponse({"detail": "Forbidden"}, status=403)
    profile = get_object_or_404(PatientProfile, user=request.user)
    if request.method != "POST": return redirect("patient_dashboard")
    form = UnifiedAppointmentForm(request.POST, request.FILES)
    if form.is_valid():
        appointment = form.save(commit=False)
        appointment.patient = profile
        try:
            appointment.full_clean()
            appointment.save()
            # If a report file was included, create linked BloodReport
            report_file = form.cleaned_data.get("report_file")
            if report_file:
                import uuid
                ext = report_file.name.rsplit(".", 1)[-1] if "." in report_file.name else "pdf"
                safe_name = f"{profile.id}_report_{uuid.uuid4().hex[:8]}.{ext}"
                report_file.name = safe_name
                file_type = BloodReport.FileType.PDF if "pdf" in report_file.content_type else BloodReport.FileType.IMAGE
                saved = BloodReport.objects.create(
                    uploader=request.user, patient=profile, appointment=appointment,
                    report_file=report_file, original_filename=safe_name,
                    file_type=file_type, n8n_status=BloodReport.N8nStatus.PENDING,
                    drive_folder_name="local_media",
                )
                from rest_framework_simplejwt.tokens import RefreshToken
                jwt_token = str(RefreshToken.for_user(request.user).access_token)
                webhook_payload = {
                    "blood_report_id": saved.id, "patient_id": profile.id,
                    "patient_email": request.user.email,
                    "drive_link": request.build_absolute_uri(saved.report_file.url),
                    "filename": safe_name, "jwt_token": jwt_token,
                    "appointment_id": appointment.appointment_id,
                }
                trigger_n8n_webhook_async(webhook_payload)
                saved.n8n_status = BloodReport.N8nStatus.PROCESSING
                saved.save(update_fields=["n8n_status"])
            messages.success(request, f"✅ Appointment {appointment.appointment_id} booked!")
        except ValidationError as exc:
            for msg in exc.messages: messages.error(request, msg)
    else:
        for field, errors in form.errors.items():
            for error in errors: messages.error(request, f"{field}: {error}")
    return redirect("patient_dashboard")

@login_required
def cancel_appointment(request, appointment_id):
    if request.user.role != User.Role.PATIENT:
        return JsonResponse({"detail": "Forbidden"}, status=403)
    profile = get_object_or_404(PatientProfile, user=request.user)
    appt = get_object_or_404(Appointment, appointment_id=appointment_id, patient=profile)
    if appt.status != Appointment.Status.PENDING:
        messages.error(request, f"Only PENDING appointments can be cancelled. Status: {appt.get_status_display()}.")
    else:
        appt.status = Appointment.Status.CANCELLED
        appt.save(update_fields=["status"])
        messages.success(request, f"Appointment {appt.appointment_id} cancelled.")
    return redirect("patient_dashboard")

@login_required
def add_report_comment(request, appointment_id):
    if request.method != "POST":
        return redirect("patient_dashboard")
    if request.user.role == User.Role.PATIENT:
        profile = get_object_or_404(PatientProfile, user=request.user)
        appt = get_object_or_404(Appointment, appointment_id=appointment_id, patient=profile)
        redirect_url = "patient_appointment_detail"
    elif request.user.role == User.Role.DOCTOR:
        doc_profile = get_object_or_404(DoctorProfile, user=request.user)
        appt = get_object_or_404(Appointment, appointment_id=appointment_id, doctor=doc_profile)
        redirect_url = "doctor_appointment_detail"
    else:
        return JsonResponse({"detail": "Forbidden"}, status=403)
    form = ReportCommentForm(request.POST)
    if form.is_valid():
        ReportComment.objects.create(appointment=appt, author=request.user, body=form.cleaned_data["body"])
        messages.success(request, "Comment added.")
    else:
        messages.error(request, "Comment cannot be empty.")
    return redirect(redirect_url, appointment_id=appointment_id)


@login_required
def upload_report(request):
    """Standalone upload endpoint with IDOR fix — scopes appointment by ownership."""
    if request.user.role not in [User.Role.PATIENT, User.Role.DOCTOR]:
        messages.error(request, "Only patients or doctors can upload reports.")
        return redirect("home")
    if request.method != "POST":
        if request.user.role == User.Role.DOCTOR: return redirect("doctor_dashboard")
        return redirect("patient_dashboard")
    form = ReportUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        for field, errors in form.errors.items():
            for error in errors: messages.error(request, error)
        if request.user.role == User.Role.DOCTOR: return redirect("doctor_dashboard")
        return redirect("patient_dashboard")
    report_file = form.cleaned_data["report_file"]
    appointment_id_str = form.cleaned_data.get("appointment_id") or request.POST.get("appointment_id", "")
    appointment = None
    if appointment_id_str:
        # IDOR fix: scope appointment lookup by ownership
        if request.user.role == User.Role.PATIENT:
            pat_profile = get_object_or_404(PatientProfile, user=request.user)
            appointment = Appointment.objects.filter(
                appointment_id=appointment_id_str, patient=pat_profile
            ).first()
        elif request.user.role == User.Role.DOCTOR:
            doc_profile = get_object_or_404(DoctorProfile, user=request.user)
            appointment = Appointment.objects.filter(
                appointment_id=appointment_id_str, doctor=doc_profile
            ).first()
        if appointment_id_str and not appointment:
            messages.error(request, "Appointment not found or access denied.")
            if request.user.role == User.Role.DOCTOR: return redirect("doctor_dashboard")
            return redirect("patient_dashboard")
    patient_profile = _resolve_patient_profile(request.user, appointment)
    try:
        import uuid
        ext = report_file.name.rsplit(".", 1)[-1] if "." in report_file.name else "pdf"
        pid = patient_profile.id if patient_profile else "unknown"
        safe_name = f"{pid}_report_{uuid.uuid4().hex[:8]}.{ext}"
        report_file.name = safe_name
        file_type = BloodReport.FileType.PDF if "pdf" in report_file.content_type else BloodReport.FileType.IMAGE
        saved = BloodReport.objects.create(
            uploader=request.user, patient=patient_profile, appointment=appointment,
            report_file=report_file, original_filename=safe_name,
            file_type=file_type, n8n_status=BloodReport.N8nStatus.PENDING,
            drive_folder_name="local_media",
        )
        from rest_framework_simplejwt.tokens import RefreshToken
        jwt_token = str(RefreshToken.for_user(request.user).access_token)
        patient_email = patient_profile.user.email if patient_profile else request.user.email
        file_url = request.build_absolute_uri(saved.report_file.url)
        trigger_n8n_webhook_async({
            "blood_report_id": saved.id, "patient_id": pid,
            "patient_email": patient_email, "drive_link": file_url,
            "filename": safe_name, "jwt_token": jwt_token,
            "appointment_id": appointment.appointment_id if appointment else None,
        })
        saved.n8n_status = BloodReport.N8nStatus.PROCESSING
        saved.save(update_fields=["n8n_status"])
        messages.success(request, f"✅ Report uploaded successfully! AI analysis in progress.")
    except Exception as exc:
        logger.exception("Report upload failed: %s", exc)
        messages.error(request, f"Upload failed: {exc}")
    if request.user.role == User.Role.DOCTOR: return redirect("doctor_dashboard")
    return redirect("patient_dashboard")


@login_required
def doctor_dashboard(request):
    if request.user.role != User.Role.DOCTOR:
        messages.error(request, "Access denied."); return redirect("home")
    profile = get_object_or_404(DoctorProfile, user=request.user)
    search = request.GET.get("search", "").strip()
    status_filter = request.GET.get("status", "")
    tab = request.GET.get("tab", "all")
    sort = request.GET.get("sort", "-start_time")
    valid_sorts = {"start_time", "-start_time", "status", "-status", "patient__user__username"}
    if sort not in valid_sorts: sort = "-start_time"
    qs = Appointment.objects.filter(doctor=profile).select_related("patient__user")
    if search:
        qs = qs.filter(
            Q(patient__user__username__icontains=search) |
            Q(patient__user__first_name__icontains=search) |
            Q(appointment_id__icontains=search) | Q(notes__icontains=search)
        )
    if status_filter and status_filter in dict(Appointment.Status.choices):
        qs = qs.filter(status=status_filter)
    now = timezone.now()
    if tab == "upcoming": qs = qs.filter(start_time__gte=now, status__in=[Appointment.Status.PENDING, Appointment.Status.CONFIRMED])
    elif tab == "past": qs = qs.filter(start_time__lt=now)
    elif tab == "completed": qs = qs.filter(status=Appointment.Status.COMPLETED)
    qs = qs.order_by(sort)
    paginator = Paginator(qs, 10)
    page = paginator.get_page(request.GET.get("page", 1))
    # Scoped to this doctor's patients only
    blood_reports = BloodReport.objects.filter(
        appointment__doctor=profile
    ).select_related("uploader", "appointment", "patient__user").order_by("-uploaded_at")[:20]
    return render(request, "doctor/dashboard.html", {
        "appointments": page, "blood_reports": blood_reports, "profile": profile,
        "status_choices": Appointment.Status.choices, "search": search,
        "status_filter": status_filter, "sort": sort, "tab": tab, "now": now,
        "upload_form": ReportUploadForm(),
    })

@login_required
def doctor_appointment_detail(request, appointment_id):
    if request.user.role != User.Role.DOCTOR:
        messages.error(request, "Access denied."); return redirect("home")
    doc_profile = get_object_or_404(DoctorProfile, user=request.user)
    appt = get_object_or_404(Appointment, appointment_id=appointment_id, doctor=doc_profile)
    report = BloodReport.objects.filter(appointment=appt).first()
    comments = appt.comments.select_related("author").all()
    comment_form = ReportCommentForm()
    remark_form = DoctorRemarkForm(initial={"status": appt.status, "doctor_remarks": appt.doctor_remarks})
    return render(request, "doctor/appointment_detail.html", {
        "appt": appt, "report": report, "comments": comments,
        "comment_form": comment_form, "remark_form": remark_form,
        "profile": doc_profile, "status_choices": Appointment.Status.choices,
    })


@login_required
def doctor_update_appointment(request, appointment_id):
    """Doctor updates status + remarks together via DoctorRemarkForm."""
    if request.user.role != User.Role.DOCTOR:
        return JsonResponse({"detail": "Forbidden"}, status=403)
    doc_profile = get_object_or_404(DoctorProfile, user=request.user)
    appt = get_object_or_404(Appointment, appointment_id=appointment_id, doctor=doc_profile)
    if request.method != "POST":
        return redirect("doctor_appointment_detail", appointment_id=appointment_id)
    form = DoctorRemarkForm(request.POST)
    if form.is_valid():
        new_status = form.cleaned_data["status"]
        remarks = form.cleaned_data.get("doctor_remarks", "")
        appt.status = new_status
        appt.doctor_remarks = remarks
        appt.save(update_fields=["status", "doctor_remarks"])
        messages.success(request, f"Appointment updated to {appt.get_status_display()}.")
    else:
        messages.error(request, "Invalid form data.")
    return redirect("doctor_appointment_detail", appointment_id=appointment_id)

@login_required
def update_appointment_status(request, appointment_id):
    if request.user.role not in [User.Role.DOCTOR, User.Role.ADMIN]:
        return JsonResponse({"detail": "Forbidden"}, status=403)
    appt = get_object_or_404(Appointment, appointment_id=appointment_id)
    if request.user.role == User.Role.DOCTOR and appt.doctor.user != request.user:
        messages.error(request, "You can only update your own appointments.")
        return redirect("doctor_dashboard")
    new_status = request.POST.get("status")
    if new_status in dict(Appointment.Status.choices):
        appt.status = new_status; appt.save(update_fields=["status"])
        messages.success(request, f"Appointment {appt.appointment_id} → {appt.get_status_display()}.")
    else:
        messages.error(request, "Invalid status value.")
    if request.user.role == User.Role.ADMIN: return redirect("admin_dashboard")
    return redirect("doctor_dashboard")

@login_required
def approve_doctor(request, doctor_id):
    if request.user.role != User.Role.ADMIN:
        messages.error(request, "Access denied."); return redirect("home")
    doc = get_object_or_404(DoctorProfile, id=doctor_id)
    doc.verification_status = DoctorProfile.VerificationStatus.APPROVED
    doc.save(update_fields=["verification_status"])
    messages.success(request, f"Dr. {doc.user.username} approved.")
    return redirect("admin_dashboard")

@login_required
def reject_doctor(request, doctor_id):
    if request.user.role != User.Role.ADMIN:
        messages.error(request, "Access denied."); return redirect("home")
    doc = get_object_or_404(DoctorProfile, id=doctor_id)
    doc.verification_status = DoctorProfile.VerificationStatus.REJECTED
    doc.save(update_fields=["verification_status"])
    messages.warning(request, f"Dr. {doc.user.username} rejected.")
    return redirect("admin_dashboard")

@login_required
def patient_profile_edit(request):
    if request.user.role != User.Role.PATIENT:
        messages.error(request, "Access denied."); return redirect("home")
    profile = get_object_or_404(PatientProfile, user=request.user)
    if request.method == "POST":
        form = PatientProfileForm(request.POST, instance=profile)
        if form.is_valid():
            request.user.first_name = form.cleaned_data.get("first_name", request.user.first_name)
            request.user.last_name = form.cleaned_data.get("last_name", request.user.last_name)
            request.user.save(update_fields=["first_name", "last_name"])
            form.save()
            messages.success(request, "Profile updated successfully!")
            return redirect("patient_profile_edit")
    else:
        form = PatientProfileForm(instance=profile, initial={"first_name": request.user.first_name, "last_name": request.user.last_name})
    return render(request, "patient/profile.html", {"form": form, "profile": profile})

@login_required
def doctor_profile_edit(request):
    if request.user.role != User.Role.DOCTOR:
        messages.error(request, "Access denied."); return redirect("home")
    profile = get_object_or_404(DoctorProfile, user=request.user)
    if request.method == "POST":
        form = DoctorProfileForm(request.POST, instance=profile)
        if form.is_valid():
            request.user.first_name = form.cleaned_data.get("first_name", request.user.first_name)
            request.user.last_name = form.cleaned_data.get("last_name", request.user.last_name)
            request.user.save(update_fields=["first_name", "last_name"])
            form.save()
            messages.success(request, "Profile updated successfully!")
            return redirect("doctor_profile_edit")
    else:
        form = DoctorProfileForm(instance=profile, initial={"first_name": request.user.first_name, "last_name": request.user.last_name})
    return render(request, "doctor/profile.html", {"form": form, "profile": profile})


from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

@csrf_exempt
@require_POST
def n8n_health_report_callback(request):
    from .models import IntegrationConfig
    config = IntegrationConfig.get_config()
    expected_token = config.n8n_callback_token
    auth_header = request.META.get("HTTP_AUTHORIZATION", "")
    provided_token = auth_header.removeprefix("Bearer ").strip()
    if not expected_token:
        logger.error("n8n callback rejected because no callback token is configured.")
        return JsonResponse({"detail": "Callback token is not configured."}, status=503)
    if provided_token != expected_token:
        logger.warning("n8n callback: invalid token.")
        return JsonResponse({"detail": "Unauthorized"}, status=401)
    try: data = _json.loads(request.body)
    except _json.JSONDecodeError: return JsonResponse({"detail": "Invalid JSON."}, status=400)
    blood_report_id = data.get("blood_report_id")
    patient_id = data.get("patient_id")
    drive_file_id = data.get("health_report_drive_file_id", "")
    drive_link = data.get("health_report_drive_link", "")
    ai_summary = data.get("ai_summary", {})
    emailed_at_raw = data.get("emailed_at")
    if not blood_report_id: return JsonResponse({"detail": "blood_report_id required."}, status=400)
    if not drive_file_id or not drive_link: return JsonResponse({"detail": "health_report_drive_file_id and link required."}, status=400)
    blood_report = BloodReport.objects.filter(pk=blood_report_id).first()
    if not blood_report: return JsonResponse({"detail": f"BloodReport #{blood_report_id} not found."}, status=404)
    patient_profile = PatientProfile.objects.filter(pk=patient_id).first() or blood_report.patient
    if not patient_profile: return JsonResponse({"detail": f"PatientProfile #{patient_id} not found."}, status=404)
    emailed_at = None
    if emailed_at_raw:
        try: emailed_at = parse_datetime(emailed_at_raw)
        except Exception: pass
    health_report, created = HealthReport.objects.update_or_create(
        blood_report=blood_report,
        defaults={"patient": patient_profile, "drive_file_id": drive_file_id, "drive_link": drive_link,
                  "original_filename": f"{patient_profile.id}_health_report.pdf",
                  "ai_summary": ai_summary or {}, "emailed_at": emailed_at},
    )
    blood_report.n8n_status = BloodReport.N8nStatus.DONE
    if ai_summary: blood_report.ai_analysis = ai_summary
    blood_report.save(update_fields=["n8n_status", "ai_analysis"])
    return JsonResponse({"status": "ok", "health_report_id": health_report.pk, "created": created})


from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny

class ApiRegisterView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        if request.data.get("role", "").upper() == User.Role.ADMIN:
            return Response({"detail": "Admin accounts cannot be self-registered via API."}, status=status.HTTP_403_FORBIDDEN)
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            if user.role == User.Role.PATIENT: PatientProfile.objects.create(user=user)
            elif user.role == User.Role.DOCTOR: DoctorProfile.objects.create(user=user)
            _get_or_create_user_token(user)
            refresh = RefreshToken.for_user(user)
            return Response({"user": UserSerializer(user).data, "refresh": str(refresh), "access": str(refresh.access_token)}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserManagementViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAdmin]


class DoctorManagementViewSet(viewsets.ModelViewSet):
    queryset = DoctorProfile.objects.select_related("user").all()
    serializer_class = DoctorProfileSerializer
    permission_classes = [IsAdmin]


class AppointmentViewSet(viewsets.ModelViewSet):
    queryset = Appointment.objects.all()
    serializer_class = AppointmentSerializer
    def get_permissions(self):
        if self.action in ["create"]: return [IsPatient()]
        if self.action in ["update_status", "destroy", "partial_update", "update"]: return [IsDoctorOrAdmin()]
        return [permissions.IsAuthenticated()]
    def get_queryset(self):
        user = self.request.user
        if user.role == User.Role.ADMIN: return Appointment.objects.all()
        if user.role == User.Role.DOCTOR: return Appointment.objects.filter(doctor__user=user)
        if user.role == User.Role.PATIENT: return Appointment.objects.filter(patient__user=user)
        return Appointment.objects.none()
    def perform_create(self, serializer):
        profile = PatientProfile.objects.filter(user=self.request.user).first()
        if profile is None:
            raise PermissionDenied("A patient profile is required to book an appointment.")
        candidate = Appointment(
            patient=profile,
            **{key: value for key, value in serializer.validated_data.items() if key != "patient"},
        )
        try:
            candidate.full_clean()
        except ValidationError as exc:
            from rest_framework.serializers import ValidationError as SerializerValidationError
            detail = exc.message_dict if getattr(exc, "message_dict", None) else exc.messages
            raise SerializerValidationError(detail)
        serializer.save(patient=profile)
    @action(detail=True, methods=["post"])
    def update_status(self, request, pk=None):
        appt = self.get_object()
        if request.user.role == User.Role.DOCTOR and appt.doctor.user_id != request.user.id:
            raise PermissionDenied("You can only modify your appointments")
        new_status = request.data.get("status", appt.status)
        if new_status not in dict(Appointment.Status.choices):
            return Response({"detail": "Invalid status."}, status=status.HTTP_400_BAD_REQUEST)
        appt.status = new_status; appt.notes = request.data.get("notes", appt.notes); appt.save()
        return Response(AppointmentSerializer(appt).data)


class BloodReportViewSet(viewsets.ModelViewSet):
    queryset = BloodReport.objects.select_related("uploader", "appointment").all()
    serializer_class = BloodReportSerializer
    def get_permissions(self): return [permissions.IsAuthenticated()]
    def perform_create(self, serializer):
        extra = {"uploader": self.request.user}
        if self.request.user.role == User.Role.PATIENT:
            extra["patient"] = PatientProfile.objects.filter(user=self.request.user).first()
        serializer.save(**extra)
    def get_queryset(self):
        user = self.request.user
        if user.role == User.Role.ADMIN: return BloodReport.objects.all()
        if user.role == User.Role.DOCTOR: return BloodReport.objects.filter(appointment__doctor__user=user)
        return BloodReport.objects.filter(uploader=user)

