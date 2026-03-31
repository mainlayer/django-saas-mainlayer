"""
Integration tests for the billing views.

Uses Django's test client and mocks the Mainlayer client to avoid real API calls.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django.test import TestCase, Client
from django.urls import reverse

from accounts.models import User
from billing.mainlayer import PaymentResult, EntitlementResult
from billing.models import Subscription


@pytest.mark.django_db
class TestPlansView(TestCase):
    def test_plans_page_is_publicly_accessible(self):
        resp = self.client.get("/billing/plans/")
        assert resp.status_code == 200

    def test_plans_page_shows_three_plans(self):
        resp = self.client.get("/billing/plans/")
        content = resp.content.decode()
        assert "Free" in content
        assert "Pro" in content
        assert "Enterprise" in content

    def test_authenticated_user_sees_current_plan(self):
        user = User.objects.create_user(username="tester", password="pass1234", email="t@example.com")
        sub = Subscription.objects.create(user=user, tier="pro", status="active")
        self.client.force_login(user)
        resp = self.client.get("/billing/plans/")
        assert resp.status_code == 200


@pytest.mark.django_db
class TestSubscribeView(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="buyer", password="pass1234", email="buyer@example.com"
        )
        self.client.force_login(self.user)

    def test_redirects_anonymous_users_to_login(self):
        anon_client = Client()
        resp = anon_client.get("/billing/subscribe/pro/")
        assert resp.status_code == 302
        assert "/accounts/login/" in resp["Location"]

    def test_unknown_tier_redirects_to_plans(self):
        resp = self.client.get("/billing/subscribe/nonexistent/")
        self.assertRedirects(resp, "/billing/plans/", fetch_redirect_response=False)

    def test_free_tier_skips_payment(self):
        resp = self.client.get("/billing/subscribe/free/")
        assert resp.status_code == 302
        sub = Subscription.objects.get(user=self.user)
        assert sub.tier == "free"

    @patch("billing.views.get_client")
    def test_pro_subscription_redirects_to_payment_url(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.create_payment.return_value = PaymentResult(
            success=True,
            payment_url="https://pay.mainlayer.xyz/session/test",
            payment_id="pay_test",
            status="pending",
        )
        mock_get_client.return_value = mock_client

        with self.settings(
            MAINLAYER_PLANS={
                "pro": {
                    "name": "Pro",
                    "resource_id": "res_pro_123",
                    "price": 29,
                    "features": ["Feature A"],
                }
            }
        ):
            resp = self.client.get("/billing/subscribe/pro/")

        assert resp.status_code == 302
        assert resp["Location"] == "https://pay.mainlayer.xyz/session/test"

    @patch("billing.views.get_client")
    def test_payment_failure_shows_error_and_redirects_to_plans(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.create_payment.return_value = PaymentResult(
            success=False,
            error="Card declined",
        )
        mock_get_client.return_value = mock_client

        with self.settings(
            MAINLAYER_PLANS={
                "pro": {
                    "name": "Pro",
                    "resource_id": "res_pro_123",
                    "price": 29,
                    "features": [],
                }
            }
        ):
            resp = self.client.get("/billing/subscribe/pro/", follow=True)

        self.assertRedirects(resp, "/billing/plans/")
        content = resp.content.decode()
        assert "Card declined" in content


@pytest.mark.django_db
class TestSuccessView(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="success_user", password="pass1234", email="s@example.com"
        )
        self.client.force_login(self.user)

    @patch("billing.views.get_client")
    def test_active_entitlement_upgrades_subscription(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.check_entitlement.return_value = EntitlementResult(
            active=True, tier="pro"
        )
        mock_get_client.return_value = mock_client

        with self.settings(
            MAINLAYER_PLANS={
                "pro": {
                    "name": "Pro",
                    "resource_id": "res_pro_123",
                    "price": 29,
                    "features": [],
                }
            }
        ):
            resp = self.client.get("/billing/success/?tier=pro")

        assert resp.status_code == 200
        sub = Subscription.objects.get(user=self.user)
        assert sub.tier == "pro"
        assert sub.status == "active"

    def test_success_page_renders_without_tier_param(self):
        resp = self.client.get("/billing/success/")
        assert resp.status_code == 200


@pytest.mark.django_db
class TestRefreshEntitlementView(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="refresher", password="pass1234", email="r@example.com"
        )
        self.client.force_login(self.user)

    def test_no_subscription_redirects_to_plans(self):
        resp = self.client.get("/billing/refresh/")
        assert resp.status_code == 302

    @patch("billing.views.get_client")
    def test_active_entitlement_keeps_subscription_active(self, mock_get_client):
        Subscription.objects.create(
            user=self.user,
            tier="pro",
            status="active",
            mainlayer_resource_id="res_pro_123",
        )
        mock_client = MagicMock()
        mock_client.check_entitlement.return_value = EntitlementResult(active=True)
        mock_get_client.return_value = mock_client

        resp = self.client.get("/billing/refresh/")
        assert resp.status_code == 302
        sub = Subscription.objects.get(user=self.user)
        assert sub.status == "active"
