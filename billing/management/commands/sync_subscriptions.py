"""
Management command: sync_subscriptions

Verifies all active paid subscriptions with Mainlayer and updates local state.

Usage:
    python manage.py sync_subscriptions
    python manage.py sync_subscriptions --update-user-fields
    python manage.py sync_subscriptions --verbosity 2
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from billing.mainlayer import get_client, MainlayerError
from billing.models import Subscription


class Command(BaseCommand):
    help = "Sync subscription status with Mainlayer for all active paid subscriptions"

    def add_arguments(self, parser):
        parser.add_argument(
            "--update-user-fields",
            action="store_true",
            help="Also update the shortcut fields on the User model (subscription_tier, subscription_active)",
        )
        parser.add_argument(
            "--tier",
            type=str,
            choices=["pro", "enterprise"],
            help="Sync only a specific tier (pro or enterprise)",
        )

    def handle(self, *args, **options):
        update_user_fields = options.get("update_user_fields", False)
        tier_filter = options.get("tier")

        client = get_client()

        # Query subscriptions to sync
        queryset = Subscription.objects.filter(
            status__in=[Subscription.STATUS_ACTIVE, Subscription.STATUS_PENDING],
            tier__in=[Subscription.TIER_PRO, Subscription.TIER_ENTERPRISE],
        )

        if tier_filter:
            queryset = queryset.filter(tier=tier_filter)

        total = queryset.count()
        self.stdout.write(f"Syncing {total} subscription(s) with Mainlayer...")

        updated_count = 0
        error_count = 0

        for sub in queryset:
            user = sub.user
            resource_id = sub.mainlayer_resource_id

            if not resource_id:
                self.stdout.write(
                    self.style.WARNING(
                        f"  Subscription {sub.id} (user: {user.email}) has no resource_id"
                    )
                )
                error_count += 1
                continue

            try:
                result = client.check_entitlement(
                    resource_id=resource_id,
                    user_email=user.email,
                )

                old_status = sub.status
                new_active = result.active
                new_status = (
                    Subscription.STATUS_ACTIVE if new_active else Subscription.STATUS_INACTIVE
                )

                if old_status != new_status:
                    sub.status = new_status
                    sub.entitlement_checked_at = timezone.now()
                    sub.save(update_fields=["status", "entitlement_checked_at"])

                    if options["verbosity"] >= 2:
                        self.stdout.write(
                            f"  Updated {user.email}: {old_status} → {new_status}"
                        )

                    updated_count += 1

                    # Optionally sync to User model
                    if update_user_fields:
                        user.subscription_active = new_active
                        user.save(update_fields=["subscription_active"])

                elif options["verbosity"] >= 2:
                    self.stdout.write(f"  No change: {user.email} ({new_status})")

            except MainlayerError as exc:
                self.stdout.write(
                    self.style.ERROR(
                        f"  Mainlayer error for {user.email}: {exc}"
                    )
                )
                error_count += 1
            except Exception as exc:  # noqa: BLE001
                self.stdout.write(
                    self.style.ERROR(
                        f"  Unexpected error for {user.email}: {exc}"
                    )
                )
                error_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"✓ Sync complete: {updated_count} updated, {error_count} errors"
            )
        )

        if error_count > 0:
            raise CommandError(f"Sync completed with {error_count} errors")
