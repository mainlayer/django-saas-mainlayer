from __future__ import annotations

import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone


class Subscription(models.Model):
    """
    Local mirror of a user's Mainlayer subscription state.

    This record is updated after each payment and entitlement check so the app
    can make fast, offline decisions (e.g. feature-gating) without hitting the
    Mainlayer API on every request.
    """

    STATUS_ACTIVE = "active"
    STATUS_INACTIVE = "inactive"
    STATUS_PENDING = "pending"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_INACTIVE, "Inactive"),
        (STATUS_PENDING, "Pending"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    TIER_FREE = "free"
    TIER_PRO = "pro"
    TIER_ENTERPRISE = "enterprise"

    TIER_CHOICES = [
        (TIER_FREE, "Free"),
        (TIER_PRO, "Pro"),
        (TIER_ENTERPRISE, "Enterprise"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscription",
    )
    tier = models.CharField(max_length=20, choices=TIER_CHOICES, default=TIER_FREE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_INACTIVE)

    # Mainlayer identifiers
    mainlayer_resource_id = models.CharField(
        max_length=200,
        blank=True,
        help_text="The Mainlayer resource_id for the current plan.",
    )
    mainlayer_payment_id = models.CharField(
        max_length=200,
        blank=True,
        help_text="The payment_id returned by POST /pay on the most recent charge.",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    entitlement_checked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Subscription"
        verbose_name_plural = "Subscriptions"

    def __str__(self) -> str:
        return f"{self.user} — {self.tier} ({self.status})"

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    @property
    def is_active(self) -> bool:
        return self.status == self.STATUS_ACTIVE

    @property
    def is_pro_or_above(self) -> bool:
        return self.tier in (self.TIER_PRO, self.TIER_ENTERPRISE)

    @property
    def plan_config(self) -> dict:
        """Return the matching entry from settings.MAINLAYER_PLANS."""
        return settings.MAINLAYER_PLANS.get(self.tier, {})

    def mark_active(self, tier: str, resource_id: str, payment_id: str = "") -> None:
        """Transition subscription to active state after a successful payment."""
        self.tier = tier
        self.status = self.STATUS_ACTIVE
        self.mainlayer_resource_id = resource_id
        if payment_id:
            self.mainlayer_payment_id = payment_id
        self.current_period_start = timezone.now()
        self.entitlement_checked_at = timezone.now()
        self.save()

    def mark_entitlement_checked(self, active: bool) -> None:
        """Update entitlement verification timestamp and status."""
        self.entitlement_checked_at = timezone.now()
        self.status = self.STATUS_ACTIVE if active else self.STATUS_INACTIVE
        self.save(update_fields=["entitlement_checked_at", "status"])

    def downgrade_to_free(self) -> None:
        """Revert subscription to the free tier."""
        self.tier = self.TIER_FREE
        self.status = self.STATUS_INACTIVE
        self.mainlayer_resource_id = ""
        self.mainlayer_payment_id = ""
        self.save()
