from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from billing.models import Subscription


@login_required
def index_view(request):
    """
    Main dashboard view.

    Shows the user's subscription status and a summary of available features
    for their current plan.
    """
    sub, _ = Subscription.objects.get_or_create(user=request.user)

    context = {
        "subscription": sub,
        "plan_config": sub.plan_config,
    }
    return render(request, "dashboard/index.html", context)
