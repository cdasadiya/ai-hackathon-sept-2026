from rest_framework.permissions import BasePermission

from .models import User


class IsActiveUser(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_active)


class RolePermission(BasePermission):
    allowed_roles: tuple[str, ...] = tuple()

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_active
            and request.user.role in self.allowed_roles
        )


class IsAdmin(RolePermission):
    allowed_roles = (User.Role.ADMIN,)


class IsDoctor(RolePermission):
    allowed_roles = (User.Role.DOCTOR,)


class IsPatient(RolePermission):
    allowed_roles = (User.Role.PATIENT,)


class IsDoctorOrAdmin(RolePermission):
    allowed_roles = (User.Role.DOCTOR, User.Role.ADMIN)
