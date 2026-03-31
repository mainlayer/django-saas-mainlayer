"""Unit tests for the Subscription model."""

from __future__ import annotations

import pytest
from django.utils import timezone

from accounts.models import User
from billing.models import Subscription


@pytest.mark.django_db
class TestSubscriptionModel:
    def _make_user(self, username="testuser") -> User:
        return User.objects.create_user(
            username=username, password="pass1234", email=f"{username}@example.com"
        )

    def test_create_subscription_defaults(self):
        user = self._make_user()
        sub = Subscription.objects.create(user=user)
        assert sub.tier == Subscription.TIER_FREE
        assert sub.status == Subscription.STATUS_INACTIVE
        assert sub.is_active is False
        assert sub.is_pro_or_above is False

    def test_mark_active_sets_correct_fields(self):
        user = self._make_user("mark_active_user")
        sub = Subscription.objects.create(user=user)
        sub.mark_active(tier="pro", resource_id="res_pro", payment_id="pay_123")
        assert sub.tier == "pro"
        assert sub.status == Subscription.STATUS_ACTIVE
        assert sub.is_active is True
        assert sub.mainlayer_resource_id == "res_pro"
        assert sub.mainlayer_payment_id == "pay_123"
        assert sub.current_period_start is not None

    def test_is_pro_or_above(self):
        user = self._make_user("pro_user")
        sub = Subscription.objects.create(user=user, tier="pro", status="active")
        assert sub.is_pro_or_above is True

    def test_is_pro_or_above_enterprise(self):
        user = self._make_user("ent_user")
        sub = Subscription.objects.create(user=user, tier="enterprise", status="active")
        assert sub.is_pro_or_above is True

    def test_downgrade_to_free(self):
        user = self._make_user("downgrade_user")
        sub = Subscription.objects.create(
            user=user, tier="pro", status="active",
            mainlayer_resource_id="res_pro", mainlayer_payment_id="pay_x"
        )
        sub.downgrade_to_free()
        assert sub.tier == Subscription.TIER_FREE
        assert sub.status == Subscription.STATUS_INACTIVE
        assert sub.mainlayer_resource_id == ""
        assert sub.mainlayer_payment_id == ""

    def test_mark_entitlement_checked_active(self):
        user = self._make_user("ent_check_user")
        sub = Subscription.objects.create(user=user, tier="pro", status="active")
        sub.mark_entitlement_checked(active=True)
        sub.refresh_from_db()
        assert sub.status == Subscription.STATUS_ACTIVE
        assert sub.entitlement_checked_at is not None

    def test_mark_entitlement_checked_inactive(self):
        user = self._make_user("ent_check_inactive")
        sub = Subscription.objects.create(user=user, tier="pro", status="active")
        sub.mark_entitlement_checked(active=False)
        sub.refresh_from_db()
        assert sub.status == Subscription.STATUS_INACTIVE

    def test_str_representation(self):
        user = self._make_user("str_user")
        sub = Subscription.objects.create(user=user, tier="pro", status="active")
        assert "str_user" in str(sub)
        assert "pro" in str(sub)
