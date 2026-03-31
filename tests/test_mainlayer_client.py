"""
Unit tests for the Mainlayer billing client.

All HTTP calls are mocked with httpx's built-in mock transport —
no real API key or network access required.
"""

from __future__ import annotations

import pytest
import httpx

from billing.mainlayer import MainlayerClient, PaymentResult, EntitlementResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class MockTransport(httpx.BaseTransport):
    """Simple mock transport that returns a predetermined response."""

    def __init__(self, status_code: int, json_body: dict) -> None:
        self._status_code = status_code
        self._json_body = json_body

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=self._status_code,
            json=self._json_body,
            request=request,
        )


def make_client(status_code: int, json_body: dict) -> MainlayerClient:
    """Return a MainlayerClient wired to a mock transport."""
    client = MainlayerClient(api_key="test-key")
    client._http = httpx.Client(
        base_url="https://api.mainlayer.fr",
        transport=MockTransport(status_code, json_body),
    )
    return client


# ---------------------------------------------------------------------------
# create_payment
# ---------------------------------------------------------------------------


class TestCreatePayment:
    def test_successful_payment_returns_url(self):
        client = make_client(200, {
            "payment_url": "https://pay.mainlayer.fr/session/abc123",
            "payment_id": "pay_abc123",
            "status": "pending",
        })
        result = client.create_payment(
            resource_id="res_pro",
            amount_usd=29.0,
            user_email="user@example.com",
        )
        assert result.success is True
        assert result.payment_url == "https://pay.mainlayer.fr/session/abc123"
        assert result.payment_id == "pay_abc123"
        assert result.status == "pending"

    def test_201_status_is_treated_as_success(self):
        client = make_client(201, {
            "payment_url": "https://pay.mainlayer.fr/session/xyz",
            "payment_id": "pay_xyz",
        })
        result = client.create_payment("res_pro", 29.0, "user@example.com")
        assert result.success is True

    def test_api_error_returns_failure(self):
        client = make_client(400, {"error": "invalid resource_id"})
        result = client.create_payment("bad_id", 29.0, "user@example.com")
        assert result.success is False
        assert "invalid resource_id" in result.error

    def test_500_returns_failure_with_http_code(self):
        client = make_client(500, {"message": "internal error"})
        result = client.create_payment("res_pro", 29.0, "user@example.com")
        assert result.success is False

    def test_timeout_returns_failure(self):
        class TimeoutTransport(httpx.BaseTransport):
            def handle_request(self, request):
                raise httpx.TimeoutException("timed out", request=request)

        client = MainlayerClient(api_key="test-key")
        client._http = httpx.Client(
            base_url="https://api.mainlayer.fr",
            transport=TimeoutTransport(),
        )
        result = client.create_payment("res_pro", 29.0, "user@example.com")
        assert result.success is False
        assert "timed out" in result.error.lower()

    def test_metadata_is_forwarded(self):
        """Ensure extra metadata does not break the call."""
        client = make_client(200, {"payment_url": "https://pay.mainlayer.fr/x", "payment_id": "p1"})
        result = client.create_payment(
            "res_pro", 29.0, "user@example.com",
            metadata={"user_id": "42", "tier": "pro"},
        )
        assert result.success is True


# ---------------------------------------------------------------------------
# check_entitlement
# ---------------------------------------------------------------------------


class TestCheckEntitlement:
    def test_active_entitlement(self):
        client = make_client(200, {"active": True, "tier": "pro"})
        result = client.check_entitlement("res_pro", "user@example.com")
        assert result.active is True
        assert result.tier == "pro"

    def test_inactive_entitlement(self):
        client = make_client(200, {"active": False})
        result = client.check_entitlement("res_pro", "user@example.com")
        assert result.active is False

    def test_api_error_returns_inactive(self):
        client = make_client(404, {"error": "not found"})
        result = client.check_entitlement("res_pro", "user@example.com")
        assert result.active is False
        assert result.error

    def test_entitled_field_alias(self):
        """The API may return 'entitled' instead of 'active'."""
        client = make_client(200, {"entitled": True})
        result = client.check_entitlement("res_pro", "user@example.com")
        assert result.active is True

    def test_timeout_returns_inactive(self):
        class TimeoutTransport(httpx.BaseTransport):
            def handle_request(self, request):
                raise httpx.TimeoutException("timed out", request=request)

        client = MainlayerClient(api_key="test-key")
        client._http = httpx.Client(
            base_url="https://api.mainlayer.fr",
            transport=TimeoutTransport(),
        )
        result = client.check_entitlement("res_pro", "user@example.com")
        assert result.active is False


# ---------------------------------------------------------------------------
# get_portal_url
# ---------------------------------------------------------------------------


class TestGetPortalUrl:
    def test_returns_url_on_success(self):
        client = make_client(200, {"url": "https://portal.mainlayer.fr/cust_abc"})
        url = client.get_portal_url("user@example.com")
        assert url == "https://portal.mainlayer.fr/cust_abc"

    def test_portal_url_field_alias(self):
        client = make_client(200, {"portal_url": "https://portal.mainlayer.fr/cust_abc"})
        url = client.get_portal_url("user@example.com")
        assert url == "https://portal.mainlayer.fr/cust_abc"

    def test_returns_none_on_error(self):
        client = make_client(400, {"error": "bad request"})
        url = client.get_portal_url("user@example.com")
        assert url is None

    def test_returns_none_on_network_error(self):
        class ErrorTransport(httpx.BaseTransport):
            def handle_request(self, request):
                raise httpx.ConnectError("connection refused", request=request)

        client = MainlayerClient(api_key="test-key")
        client._http = httpx.Client(
            base_url="https://api.mainlayer.fr",
            transport=ErrorTransport(),
        )
        url = client.get_portal_url("user@example.com")
        assert url is None
