from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "subscription_tier", "subscription_active", "date_joined")
    list_filter = ("subscription_tier", "subscription_active", "is_staff", "is_active")
    search_fields = ("username", "email", "wallet_address")
    readonly_fields = ("subscription_checked_at",)

    fieldsets = BaseUserAdmin.fieldsets + (
        (
            "Mainlayer Billing",
            {
                "fields": (
                    "wallet_address",
                    "subscription_tier",
                    "mainlayer_resource_id",
                    "subscription_active",
                    "subscription_checked_at",
                )
            },
        ),
    )
