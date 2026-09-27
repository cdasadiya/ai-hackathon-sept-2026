"""Sign-in that accepts role words and ignores username case.

People type admin / doctor / patient into the login box. Those words are not
stored usernames; the demo accounts are admin1, doctor1, and patient1.
"""

from django.contrib.auth.backends import ModelBackend

from .models import User

ROLE_ALIASES = {
    "admin": "admin1",
    "administrator": "admin1",
    "doctor": "doctor1",
    "patient": "patient1",
}


class RoleAliasBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        raw = str(username).strip()
        if not raw:
            return None
        lookup = ROLE_ALIASES.get(raw.lower(), raw)
        user = User.objects.filter(username__iexact=lookup).order_by("id").first()
        if user is None:
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
