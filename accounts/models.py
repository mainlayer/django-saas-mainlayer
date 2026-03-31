from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Extended user model with Mainlayer billing fields."""

    TIER_CHOICES = [
        ("free", "Free"),
        ("pro", "Pro"),
        ("enterprise", "Enterprise"),
    ]

    wallet_address = models.CharField(
        max_length=100,
        blank=True,
        help_text="Mainlayer wallet address used for billing identification.",
    )
    subscription_tier = models.CharField(
        max_length=20,
        choices=TIER_CHOICES,
        default="free",
    )
    mainlayer_resource_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="Active Mainlayer resource ID for subscription entitlement checks.",
    )
    subscription_active = models.BooleanField(
        default=False,
        help_text="Whether the user has a verified active subscription.",
    )
    subscription_checked_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time the subscription status was verified with Mainlayer.",
    )

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self) -> str:
        return self.email or self.username

    @property
    def is_pro_or_above(self) -> bool:
        return self.subscription_tier in ("pro", "enterprise")

    @property
    def display_tier(self) -> str:
        return dict(self.TIER_CHOICES).get(self.subscription_tier, "Free")
