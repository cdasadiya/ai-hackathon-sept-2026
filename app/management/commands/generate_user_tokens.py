"""Management command: generate (or refresh) UserToken for all active users."""
from django.core.management.base import BaseCommand
from app.models import User, UserToken


class Command(BaseCommand):
    help = "Generate or regenerate UserToken for all active Patient/Doctor users."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Regenerate even if token already exists.")

    def handle(self, *args, **options):
        force = options["force"]
        users = User.objects.filter(is_active=True, role__in=[User.Role.PATIENT, User.Role.DOCTOR])
        created = updated = skipped = 0
        for user in users:
            token, was_created = UserToken.objects.get_or_create(user=user)
            if was_created:
                token.generate()
                created += 1
            elif force or not token.access_token:
                token.generate()
                updated += 1
            else:
                skipped += 1
        self.stdout.write(self.style.SUCCESS(
            f"Done — created: {created}, updated: {updated}, skipped: {skipped}"
        ))
