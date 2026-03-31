"""
Billing views — plans listing, subscription initiation, portal, and entitlement refresh.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .mainlayer import get_client
from .models import Subscription

logger = logging.getLogger(__name__)


def _get_or_create_subscription(user) -> Subscription:
    """Fetch or lazily create the user's Subscription record."""
    sub, _ = Subscription.objects.get_or_create(user=user)
    return sub


# ---------------------------------------------------------------------------
# Plans / pricing
# ---------------------------------------------------------------------------


def plans_view(request):
    """
    Public pricing page showing Free, Pro, and Enterprise plans.
    Authenticated users see which plan they are currently on.
    """
    plans = [
        {
            "key": key,
            **config,
            "is_current": (
                request.user.is_authenticated
                and hasattr(request.user, "subscription")
                and request.user.subscription.tier == key
                and request.user.subscription.is_active
            ),
        }
        for key, config in settings.MAINLAYER_PLANS.items()
    ]

    return render(request, "billing/plans.html", {"plans": plans})


# ---------------------------------------------------------------------------
# Subscribe
# ---------------------------------------------------------------------------


@login_required
def subscribe_view(request, tier: str):
    """
    Initiate a Mainlayer payment for the requested plan tier.

    Flow:
      1. Validate that `tier` is a known plan key.
      2. Call POST /pay on the Mainlayer API.
      3. On success, redirect the user to the Mainlayer-hosted payment URL.
      4. On failure, show an error and redirect back to the plans page.
    """
    plan = settings.MAINLAYER_PLANS.get(tier)
    if not plan:
        messages.error(request, "Unknown plan selected.")
        return redirect("billing:plans")

    # Free tier — no payment needed
    if plan["price"] == 0:
        sub = _get_or_create_subscription(request.user)
        sub.downgrade_to_free()
        # Sync the shortcut field on User as well
        request.user.subscription_tier = tier
        request.user.subscription_active = False
        request.user.mainlayer_resource_id = ""
        request.user.save(update_fields=["subscription_tier", "subscription_active", "mainlayer_resource_id"])
        messages.success(request, "You are now on the Free plan.")
        return redirect("dashboard:index")

    resource_id = plan.get("resource_id", "")
    if not resource_id:
        logger.error("No resource_id configured for plan %s", tier)
        messages.error(request, "This plan is not available right now. Please try again later.")
        return redirect("billing:plans")

    client = get_client()
    result = client.create_payment(
        resource_id=resource_id,
        amount_usd=float(plan["price"]),
        user_email=request.user.email,
        metadata={
            "user_id": str(request.user.pk),
            "username": request.user.username,
            "tier": tier,
        },
    )

    if result.success and result.payment_url:
        # Store the pending payment so we can pick it up on return
        sub = _get_or_create_subscription(request.user)
        sub.status = Subscription.STATUS_PENDING
        sub.mainlayer_resource_id = resource_id
        if result.payment_id:
            sub.mainlayer_payment_id = result.payment_id
        sub.save(update_fields=["status", "mainlayer_resource_id", "mainlayer_payment_id"])

        return redirect(result.payment_url)

    logger.warning(
        "Payment initiation failed for user=%s tier=%s error=%s",
        request.user.pk,
        tier,
        result.error,
    )
    messages.error(request, f"Payment could not be started: {result.error}")
    return redirect("billing:plans")


# ---------------------------------------------------------------------------
# Post-payment success landing
# ---------------------------------------------------------------------------


@login_required
def success_view(request):
    """
    Landing page after a user returns from the Mainlayer payment flow.

    Reads the `tier` query param (passed by Mainlayer's redirect URL), verifies
    entitlement, and updates the local subscription record.
    """
    tier = request.GET.get("tier", "")
    plan = settings.MAINLAYER_PLANS.get(tier)

    if plan and plan.get("resource_id"):
        client = get_client()
        result = client.check_entitlement(
            resource_id=plan["resource_id"],
            user_email=request.user.email,
        )

        sub = _get_or_create_subscription(request.user)

        if result.active:
            sub.mark_active(
                tier=tier,
                resource_id=plan["resource_id"],
            )
            # Mirror on the User model for quick access
            request.user.subscription_tier = tier
            request.user.subscription_active = True
            request.user.mainlayer_resource_id = plan["resource_id"]
            request.user.save(
                update_fields=["subscription_tier", "subscription_active", "mainlayer_resource_id"]
            )
            messages.success(request, f"You are now subscribed to the {plan['name']} plan.")
        else:
            sub.mark_entitlement_checked(active=False)
            messages.warning(
                request,
                "Payment received — subscription activation is pending. "
                "Please refresh in a moment or contact support.",
            )

    return render(request, "billing/success.html", {"tier": tier, "plan": plan})


# ---------------------------------------------------------------------------
# Customer portal
# ---------------------------------------------------------------------------


@login_required
def portal_view(request):
    """
    Redirect the user to their Mainlayer customer portal for subscription management
    (plan changes, payment history, cancellation).
    """
    client = get_client()
    portal_url = client.get_portal_url(user_email=request.user.email)

    if portal_url:
        return redirect(portal_url)

    messages.error(
        request,
        "The billing portal is temporarily unavailable. Please try again in a moment.",
    )
    return redirect("billing:plans")


# ---------------------------------------------------------------------------
# Entitlement refresh
# ---------------------------------------------------------------------------


@login_required
def refresh_entitlement_view(request):
    """
    Re-check entitlement against Mainlayer and update the local subscription record.

    Useful for users who have just completed a payment and want to confirm
    their access without waiting for a webhook.
    """
    sub = _get_or_create_subscription(request.user)
    resource_id = sub.mainlayer_resource_id or request.user.mainlayer_resource_id

    if not resource_id:
        messages.info(request, "No active subscription to verify.")
        return redirect("billing:plans")

    client = get_client()
    result = client.check_entitlement(
        resource_id=resource_id,
        user_email=request.user.email,
    )

    sub.mark_entitlement_checked(active=result.active)

    if result.active:
        request.user.subscription_active = True
        request.user.save(update_fields=["subscription_active"])
        messages.success(request, "Subscription verified — your access is active.")
    else:
        request.user.subscription_active = False
        request.user.save(update_fields=["subscription_active"])
        messages.warning(
            request,
            "Your subscription could not be verified. "
            f"Details: {result.error or 'no active entitlement found.'}",
        )

    return redirect("dashboard:index")
