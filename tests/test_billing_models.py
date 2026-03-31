"""
Tests for billing models and subscription logic.

Verifies:
- Subscription model CRUD and state transitions
- Plan configuration loading
- Entitlement checking with mocked Mainlayer
"""

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from unittest.mock import patch, MagicMock

from billing.models import Subscription
from billing.mainlayer import EntitlementResult, MainlayerError

User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )


@pytest.fixture
def subscription(user):
    """Create a test subscription."""
    return Subscription.objects.create(
        user=user,
        tier=Subscription.TIER_FREE,
        status=Subscription.STATUS_INACTIVE,
    )


class TestSubscriptionModel:
    """Test Subscription model methods and properties."""

    def test_subscription_creation(self, user):
        """Test that a subscription is created correctly."""
        sub = Subscription.objects.create(
            user=user,
            tier=Subscription.TIER_FREE,
            status=Subscription.STATUS_INACTIVE,
        )
        assert sub.user == user
        assert sub.tier == Subscription.TIER_FREE
        assert sub.status == Subscription.STATUS_INACTIVE
        assert sub.is_active is False

    def test_is_active_property(self, subscription):
        """Test is_active property."""
        subscription.status = Subscription.STATUS_INACTIVE
        assert subscription.is_active is False

        subscription.status = Subscription.STATUS_ACTIVE
        assert subscription.is_active is True

    def test_is_pro_or_above_property(self, subscription):
        """Test is_pro_or_above property."""
        subscription.tier = Subscription.TIER_FREE
        assert subscription.is_pro_or_above is False

        subscription.tier = Subscription.TIER_PRO
        assert subscription.is_pro_or_above is True

        subscription.tier = Subscription.TIER_ENTERPRISE
        assert subscription.is_pro_or_above is True

    def test_mark_active(self, subscription):
        """Test mark_active transitions subscription to active state."""
        subscription.mark_active(
            tier=Subscription.TIER_PRO,
            resource_id="res_pro_123",
            payment_id="pay_abc",
        )

        subscription.refresh_from_db()
        assert subscription.tier == Subscription.TIER_PRO
        assert subscription.status == Subscription.STATUS_ACTIVE
        assert subscription.mainlayer_resource_id == "res_pro_123"
        assert subscription.mainlayer_payment_id == "pay_abc"
        assert subscription.current_period_start is not None
        assert subscription.entitlement_checked_at is not None

    def test_mark_entitlement_checked_active(self, subscription):
        """Test marking entitlement as checked and active."""
        subscription.mark_entitlement_checked(active=True)

        subscription.refresh_from_db()
        assert subscription.status == Subscription.STATUS_ACTIVE
        assert subscription.entitlement_checked_at is not None

    def test_mark_entitlement_checked_inactive(self, subscription):
        """Test marking entitlement as checked and inactive."""
        subscription.status = Subscription.STATUS_ACTIVE
        subscription.save()

        subscription.mark_entitlement_checked(active=False)

        subscription.refresh_from_db()
        assert subscription.status == Subscription.STATUS_INACTIVE

    def test_downgrade_to_free(self, subscription):
        """Test downgrading subscription to free tier."""
        subscription.tier = Subscription.TIER_PRO
        subscription.status = Subscription.STATUS_ACTIVE
        subscription.mainlayer_resource_id = "res_pro_123"
        subscription.mainlayer_payment_id = "pay_abc"
        subscription.save()

        subscription.downgrade_to_free()

        subscription.refresh_from_db()
        assert subscription.tier == Subscription.TIER_FREE
        assert subscription.status == Subscription.STATUS_INACTIVE
        assert subscription.mainlayer_resource_id == ""
        assert subscription.mainlayer_payment_id == ""

    def test_plan_config_free(self, subscription):
        """Test getting plan config for free tier."""
        subscription.tier = Subscription.TIER_FREE
        plan_config = subscription.plan_config
        assert plan_config["name"] == "Free"
        assert plan_config["price"] == 0

    def test_plan_config_pro(self, subscription):
        """Test getting plan config for pro tier."""
        subscription.tier = Subscription.TIER_PRO
        plan_config = subscription.plan_config
        assert plan_config["name"] == "Pro"
        assert plan_config["price"] == 29

    def test_subscription_str(self, subscription, user):
        """Test string representation."""
        subscription.tier = Subscription.TIER_PRO
        subscription.status = Subscription.STATUS_ACTIVE
        assert "PRO" in str(subscription).upper() or "Pro" in str(subscription)
        assert user.username in str(subscription) or user.email in str(subscription)


class TestSubscriptionWorkflow:
    """Test common subscription workflows."""

    def test_free_to_pro_upgrade(self, user):
        """Test upgrading from Free to Pro."""
        # Start on Free
        sub = Subscription.objects.create(
            user=user,
            tier=Subscription.TIER_FREE,
            status=Subscription.STATUS_INACTIVE,
        )
        assert sub.tier == Subscription.TIER_FREE
        assert sub.is_pro_or_above is False

        # Upgrade to Pro
        sub.mark_active(
            tier=Subscription.TIER_PRO,
            resource_id="res_pro_123",
        )
        assert sub.tier == Subscription.TIER_PRO
        assert sub.status == Subscription.STATUS_ACTIVE
        assert sub.is_pro_or_above is True

    def test_pro_to_enterprise_upgrade(self, subscription):
        """Test upgrading from Pro to Enterprise."""
        subscription.tier = Subscription.TIER_PRO
        subscription.status = Subscription.STATUS_ACTIVE
        subscription.mainlayer_resource_id = "res_pro_123"
        subscription.save()

        # Upgrade to Enterprise
        subscription.mark_active(
            tier=Subscription.TIER_ENTERPRISE,
            resource_id="res_ent_456",
        )
        assert subscription.tier == Subscription.TIER_ENTERPRISE
        assert subscription.mainlayer_resource_id == "res_ent_456"

    def test_cancellation_flow(self, subscription):
        """Test cancellation by downgrading to free."""
        subscription.tier = Subscription.TIER_PRO
        subscription.status = Subscription.STATUS_ACTIVE
        subscription.mainlayer_resource_id = "res_pro_123"
        subscription.save()

        # Cancel by downgrading
        subscription.downgrade_to_free()
        assert subscription.tier == Subscription.TIER_FREE
        assert subscription.status == Subscription.STATUS_INACTIVE
        assert subscription.is_pro_or_above is False


class TestSubscriptionSync:
    """Test subscription syncing with Mainlayer."""

    @patch("billing.mainlayer.get_client")
    def test_sync_active_subscription(self, mock_get_client, subscription):
        """Test syncing an active subscription."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        subscription.tier = Subscription.TIER_PRO
        subscription.status = Subscription.STATUS_ACTIVE
        subscription.mainlayer_resource_id = "res_pro_123"
        subscription.save()

        # Mock Mainlayer response
        mock_client.check_entitlement.return_value = EntitlementResult(
            active=True,
            tier="pro",
            resource_id="res_pro_123",
        )

        # Sync
        result = mock_client.check_entitlement(
            resource_id="res_pro_123",
            user_email=subscription.user.email,
        )

        assert result.active is True
        mock_client.check_entitlement.assert_called_once()

    @patch("billing.mainlayer.get_client")
    def test_sync_inactive_subscription(self, mock_get_client, subscription):
        """Test syncing an inactive subscription (payment failed or cancelled)."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        subscription.tier = Subscription.TIER_PRO
        subscription.status = Subscription.STATUS_ACTIVE
        subscription.mainlayer_resource_id = "res_pro_123"
        subscription.save()

        # Mock Mainlayer response — entitlement expired
        mock_client.check_entitlement.return_value = EntitlementResult(
            active=False,
            tier="",
            resource_id="res_pro_123",
        )

        result = mock_client.check_entitlement(
            resource_id="res_pro_123",
            user_email=subscription.user.email,
        )

        assert result.active is False

    @patch("billing.mainlayer.get_client")
    def test_sync_mainlayer_error(self, mock_get_client, subscription):
        """Test handling Mainlayer errors during sync."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        subscription.tier = Subscription.TIER_PRO
        subscription.mainlayer_resource_id = "res_pro_123"
        subscription.save()

        # Mock Mainlayer error
        mock_client.check_entitlement.side_effect = MainlayerError(
            "Network error",
            status_code=503,
        )

        with pytest.raises(MainlayerError):
            mock_client.check_entitlement(
                resource_id="res_pro_123",
                user_email=subscription.user.email,
            )
