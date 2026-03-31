"""
Mainlayer billing client.

Thin, Django-aware wrapper around the Mainlayer REST API.
All network I/O is synchronous so it can be called directly from Django views.
Use the module-level `client` singleton after Django settings are loaded.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

MAINLAYER_BASE_URL = "https://api.mainlayer.fr"
DEFAULT_TIMEOUT = 15.0  # seconds


@dataclass
class PaymentResult:
    success: bool
    payment_url: str = ""
    payment_id: str = ""
    status: str = ""
    error: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class EntitlementResult:
    active: bool
    tier: str = ""
    resource_id: str = ""
    error: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


class MainlayerError(Exception):
    """Raised when the Mainlayer API returns an unexpected response."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class MainlayerClient:
    """
    Synchronous HTTP client for the Mainlayer payment API.

    Instantiate once at module level and reuse across requests — httpx.Client
    keeps an internal connection pool for efficiency.

    Args:
        api_key: Mainlayer API key (Bearer token).
        base_url: Override the default API base URL.
        timeout: Per-request timeout in seconds.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = MAINLAYER_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._http = httpx.Client(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=timeout,
        )

    # ------------------------------------------------------------------
    # Payment initiation
    # ------------------------------------------------------------------

    def create_payment(
        self,
        resource_id: str,
        amount_usd: float,
        user_email: str,
        metadata: dict[str, Any] | None = None,
    ) -> PaymentResult:
        """
        Initiate a payment for a given resource.

        POST /pay

        Args:
            resource_id: Mainlayer resource identifier for the plan.
            amount_usd: Dollar amount to charge (e.g. 29.00).
            user_email: End-user email for receipt / identification.
            metadata: Optional key-value bag forwarded to the API.

        Returns:
            PaymentResult with a ``payment_url`` the user should be redirected to,
            or ``success=False`` with an ``error`` description.
        """
        payload: dict[str, Any] = {
            "resource_id": resource_id,
            "amount": amount_usd,
            "currency": "usd",
            "customer_email": user_email,
        }
        if metadata:
            payload["metadata"] = metadata

        try:
            resp = self._http.post("/pay", json=payload)
            data = resp.json()
        except httpx.TimeoutException:
            logger.warning("Mainlayer /pay timed out for resource_id=%s", resource_id)
            return PaymentResult(success=False, error="Payment service timed out. Please try again.")
        except httpx.RequestError as exc:
            logger.error("Mainlayer /pay network error: %s", exc)
            return PaymentResult(success=False, error="Unable to reach the payment service.")
        except Exception as exc:  # noqa: BLE001
            logger.error("Mainlayer /pay unexpected error: %s", exc)
            return PaymentResult(success=False, error="An unexpected error occurred.")

        if resp.status_code in (200, 201, 202):
            return PaymentResult(
                success=True,
                payment_url=data.get("payment_url", data.get("url", "")),
                payment_id=data.get("payment_id", data.get("id", "")),
                status=data.get("status", "pending"),
                raw=data,
            )

        error_msg = data.get("error", data.get("message", f"HTTP {resp.status_code}"))
        logger.warning(
            "Mainlayer /pay failed: status=%s error=%s resource_id=%s",
            resp.status_code,
            error_msg,
            resource_id,
        )
        return PaymentResult(success=False, error=error_msg, raw=data)

    # ------------------------------------------------------------------
    # Entitlement checks
    # ------------------------------------------------------------------

    def check_entitlement(
        self,
        resource_id: str,
        user_email: str,
    ) -> EntitlementResult:
        """
        Verify whether a user has active access to a resource.

        GET /entitlements/check?resource_id=<id>&customer_email=<email>

        Args:
            resource_id: Mainlayer resource identifier.
            user_email: End-user email used at payment time.

        Returns:
            EntitlementResult with ``active=True`` when the subscription is valid.
        """
        try:
            resp = self._http.get(
                "/entitlements/check",
                params={"resource_id": resource_id, "customer_email": user_email},
            )
            data = resp.json()
        except httpx.TimeoutException:
            logger.warning("Mainlayer entitlement check timed out for %s", user_email)
            return EntitlementResult(active=False, error="Entitlement service timed out.")
        except httpx.RequestError as exc:
            logger.error("Mainlayer entitlement network error: %s", exc)
            return EntitlementResult(active=False, error="Unable to reach the entitlement service.")
        except Exception as exc:  # noqa: BLE001
            logger.error("Mainlayer entitlement unexpected error: %s", exc)
            return EntitlementResult(active=False, error="An unexpected error occurred.")

        if resp.status_code == 200:
            active = bool(data.get("active", data.get("entitled", False)))
            return EntitlementResult(
                active=active,
                tier=data.get("tier", ""),
                resource_id=resource_id,
                raw=data,
            )

        error_msg = data.get("error", data.get("message", f"HTTP {resp.status_code}"))
        logger.warning(
            "Mainlayer entitlement check failed: status=%s error=%s",
            resp.status_code,
            error_msg,
        )
        return EntitlementResult(active=False, error=error_msg, raw=data)

    # ------------------------------------------------------------------
    # Customer portal
    # ------------------------------------------------------------------

    def get_portal_url(self, user_email: str) -> str | None:
        """
        Retrieve a short-lived customer portal URL for subscription management.

        POST /portal

        Returns the URL string, or None if unavailable.
        """
        try:
            resp = self._http.post("/portal", json={"customer_email": user_email})
            data = resp.json()
        except (httpx.RequestError, httpx.TimeoutException) as exc:
            logger.warning("Mainlayer /portal error: %s", exc)
            return None

        if resp.status_code in (200, 201):
            return data.get("url", data.get("portal_url"))

        return None

    def close(self) -> None:
        """Release the underlying HTTP connection pool."""
        self._http.close()

    def __enter__(self) -> "MainlayerClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


def get_client() -> MainlayerClient:
    """
    Return the module-level Mainlayer client, constructed from Django settings.

    Call this inside a view or signal handler — not at module import time —
    so Django settings are guaranteed to be configured.
    """
    global _client  # noqa: PLW0603
    if _client is None:
        _client = MainlayerClient(api_key=settings.MAINLAYER_API_KEY)
    return _client


_client: MainlayerClient | None = None
