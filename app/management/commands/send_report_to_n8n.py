"""Management command: (re)send blood reports to the n8n blood-report workflow."""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from app.models import BloodReport, IntegrationConfig
from app.services import build_n8n_payload, trigger_n8n_webhook


class Command(BaseCommand):
    help = (
        "POST blood reports to the n8n webhook synchronously and print n8n's reply. "
        "Use it to verify the workflow or to retry PENDING/FAILED reports."
    )

    def add_arguments(self, parser):
        parser.add_argument("report_ids", nargs="*", type=int, help="BloodReport ids to send.")
        parser.add_argument(
            "--stuck", action="store_true",
            help="Also send every report whose status is PENDING or FAILED.",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Print the payloads (download links included) without calling n8n.",
        )

    def handle(self, *args, **options):
        config = IntegrationConfig.get_config()
        missing = [
            name for name in ("n8n_blood_report_webhook_url", "n8n_webhook_secret", "n8n_callback_token")
            if not getattr(config, name)
        ]
        if missing and not options["dry_run"]:
            raise CommandError(f"Integration Configuration is missing: {', '.join(missing)}")

        reports = BloodReport.objects.select_related("patient__user", "appointment", "uploader")
        selected = reports.filter(pk__in=options["report_ids"])
        if options["stuck"]:
            selected = selected | reports.filter(
                n8n_status__in=[BloodReport.N8nStatus.PENDING, BloodReport.N8nStatus.FAILED]
            )
        selected = selected.distinct().order_by("pk")
        if not selected:
            raise CommandError("No blood reports selected. Pass report ids and/or --stuck.")

        absolute_url = lambda path: f"{settings.PUBLIC_BASE_URL}{path}"  # noqa: E731
        failures = 0
        for report in selected:
            payload = build_n8n_payload(report, absolute_url)
            if options["dry_run"]:
                self.stdout.write(f"#{report.pk}: {payload}")
                continue
            reply = trigger_n8n_webhook(payload)
            if reply:
                report.n8n_status = BloodReport.N8nStatus.PROCESSING
                report.save(update_fields=["n8n_status"])
                self.stdout.write(self.style.SUCCESS(f"#{report.pk}: accepted by n8n {reply}"))
            else:
                failures += 1
                self.stdout.write(self.style.ERROR(f"#{report.pk}: n8n did not accept the webhook (see logs)."))
        if failures:
            raise CommandError(f"{failures} report(s) could not be sent.")
