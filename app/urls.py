from django.contrib.auth.views import LogoutView, PasswordResetDoneView, PasswordResetView
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import (
    AppointmentViewSet, BloodReportViewSet, DoctorManagementViewSet,
    RegisterView, RoleLoginView, UserManagementViewSet, ApiRegisterView,
    admin_dashboard, approve_doctor, reject_doctor,
    book_appointment, cancel_appointment, add_report_comment,
    debug_admin, doctor_dashboard, doctor_profile_edit, doctor_appointment_detail,
    doctor_update_appointment,
    healthz, home, n8n_health_report_callback,
    patient_dashboard, patient_profile_edit, patient_appointment_detail,
    update_appointment_status, upload_report, custom_logout,
)

router = DefaultRouter()
router.register("appointments", AppointmentViewSet, basename="appointments")
router.register("reports", BloodReportViewSet, basename="reports")
router.register("users", UserManagementViewSet, basename="users")
router.register("doctor-management", DoctorManagementViewSet, basename="doctor-management")

urlpatterns = [
    path("", home, name="home"),
    path("healthz/", healthz, name="healthz"),
    path("debug-admin/", debug_admin, name="debug_admin"),
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", RoleLoginView.as_view(), name="login"),
    path("logout/", custom_logout, name="logout"),
    path("auth/logout/", custom_logout),
    path("password-reset/", PasswordResetView.as_view(), name="password_reset"),
    path("password-reset/done/", PasswordResetDoneView.as_view(), name="password_reset_done"),
    # Admin
    path("dashboard/admin/", admin_dashboard, name="admin_dashboard"),
    path("admin/doctor/<int:doctor_id>/approve/", approve_doctor, name="approve_doctor"),
    path("admin/doctor/<int:doctor_id>/reject/", reject_doctor, name="reject_doctor"),
    # Patient
    path("patient/dashboard/", patient_dashboard, name="patient_dashboard"),
    path("patient/book/", book_appointment, name="book_appointment"),
    path("patient/appointment/<str:appointment_id>/cancel/", cancel_appointment, name="cancel_appointment"),
    path("patient/appointment/<str:appointment_id>/", patient_appointment_detail, name="patient_appointment_detail"),
    path("patient/appointment/<str:appointment_id>/comment/", add_report_comment, name="patient_add_comment"),
    path("patient/profile/", patient_profile_edit, name="patient_profile_edit"),
    # Doctor
    path("doctor/dashboard/", doctor_dashboard, name="doctor_dashboard"),
    path("doctor/appointment/<str:appointment_id>/status/", update_appointment_status, name="update_appointment_status"),
    path("doctor/appointment/<str:appointment_id>/update/", doctor_update_appointment, name="doctor_update_appointment"),
    path("doctor/appointment/<str:appointment_id>/", doctor_appointment_detail, name="doctor_appointment_detail"),
    path("doctor/appointment/<str:appointment_id>/comment/", add_report_comment, name="doctor_add_comment"),
    path("doctor/profile/", doctor_profile_edit, name="doctor_profile_edit"),
    # Upload
    path("upload-report/", upload_report, name="upload_report"),
    # API
    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/register/", ApiRegisterView.as_view(), name="api_register"),
    path("api/n8n/health-report-callback/", n8n_health_report_callback, name="n8n_health_report_callback"),
    path("api/", include(router.urls)),
]
