from django.contrib import admin

from .models import Subscription


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "tier",
        "status",
        "mainlayer_resource_id",
        "current_period_start",
        "entitlement_checked_at",
    )
    list_filter = ("tier", "status")
    search_fields = ("user__username", "user__email", "mainlayer_resource_id", "mainlayer_payment_id")
    readonly_fields = ("id", "created_at", "updated_at", "entitlement_checked_at")
    raw_id_fields = ("user",)
