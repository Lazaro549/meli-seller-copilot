"""Mercado Libre API client.

Supports:
- OAuth 2.0 authorization code + refresh token flow
- Public search
- Item details
- Seller items search (authenticated)
- User info
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlencode

import httpx

from src.config import Settings, get_settings

logger = logging.getLogger(__name__)

API_BASE = "https://api.mercadolibre.com"

AUTH_HOSTS = {
    "MLA": "https://auth.mercadolibre.com.ar",
    "MLB": "https://auth.mercadolivre.com.br",
    "MLM": "https://auth.mercadolibre.com.mx",
    "MLC": "https://auth.mercadolibre.cl",
    "MCO": "https://auth.mercadolibre.com.co",
    "MLU": "https://auth.mercadolibre.com.uy",
    "MPE": "https://auth.mercadolibre.com.pe",
}


class MeliAPIError(Exception):
    """Raised when the Mercado Libre API returns an error."""

    def __init__(self, status_code: int, message: str, payload: dict | None = None):
        self.status_code = status_code
        self.message = message
        self.payload = payload or {}
        super().__init__(f"[{status_code}] {message}")


class MeliClient:
    """Async-friendly but sync-first client for Mercado Libre APIs."""

    def __init__(
        self,
        settings: Settings | None = None,
        access_token: str | None = None,
        timeout: float = 30.0,
    ):
        self.settings = settings or get_settings()
        self._access_token = access_token or self.settings.meli_access_token or None
        self._refresh_token = self.settings.meli_refresh_token or None
        self._timeout = timeout
        self._client = httpx.Client(
            base_url=API_BASE,
            timeout=timeout,
            headers={"Accept": "application/json", "User-Agent": "meli-seller-copilot/0.1"},
        )

    # ------------------------------------------------------------------
    # OAuth
    # ------------------------------------------------------------------

    def authorization_url(self, state: str | None = None) -> str:
        """Build the URL to redirect the seller for authorization."""
        host = AUTH_HOSTS.get(self.settings.meli_site_id, AUTH_HOSTS["MLA"])
        params = {
            "response_type": "code",
            "client_id": self.settings.meli_client_id,
            "redirect_uri": self.settings.meli_redirect_uri,
        }
        if state:
            params["state"] = state
        return f"{host}/authorization?{urlencode(params)}"

    def exchange_code(self, code: str) -> dict[str, Any]:
        """Exchange authorization code for access + refresh tokens."""
        data = {
            "grant_type": "authorization_code",
            "client_id": self.settings.meli_client_id,
            "client_secret": self.settings.meli_client_secret,
            "code": code,
            "redirect_uri": self.settings.meli_redirect_uri,
        }
        response = httpx.post(
            f"{API_BASE}/oauth/token",
            data=data,
            headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
            timeout=self._timeout,
        )
        payload = response.json()
        if response.status_code >= 400:
            raise MeliAPIError(response.status_code, payload.get("message", "token exchange failed"), payload)

        self._access_token = payload["access_token"]
        self._refresh_token = payload.get("refresh_token")
        logger.info("Tokens obtained for user_id=%s", payload.get("user_id"))
        return payload

    def refresh_access_token(self) -> dict[str, Any]:
        """Refresh the access token using the current refresh token."""
        if not self._refresh_token:
            raise MeliAPIError(401, "No refresh_token available")

        data = {
            "grant_type": "refresh_token",
            "client_id": self.settings.meli_client_id,
            "client_secret": self.settings.meli_client_secret,
            "refresh_token": self._refresh_token,
        }
        response = httpx.post(
            f"{API_BASE}/oauth/token",
            data=data,
            headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
            timeout=self._timeout,
        )
        payload = response.json()
        if response.status_code >= 400:
            raise MeliAPIError(response.status_code, payload.get("message", "refresh failed"), payload)

        self._access_token = payload["access_token"]
        # Refresh tokens are single-use; always store the new one.
        if "refresh_token" in payload:
            self._refresh_token = payload["refresh_token"]
        logger.info("Access token refreshed")
        return payload

    def set_tokens(self, access_token: str, refresh_token: str | None = None) -> None:
        self._access_token = access_token
        if refresh_token:
            self._refresh_token = refresh_token

    @property
    def access_token(self) -> str | None:
        return self._access_token

    @property
    def refresh_token(self) -> str | None:
        return self._refresh_token

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _headers(self, auth: bool = True) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if auth and self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json: dict | None = None,
        auth: bool = True,
        retry_on_401: bool = True,
    ) -> dict[str, Any] | list[Any]:
        response = self._client.request(
            method,
            path,
            params=params,
            json=json,
            headers=self._headers(auth=auth),
        )

        if response.status_code == 401 and retry_on_401 and self._refresh_token:
            logger.info("Received 401 – attempting token refresh")
            self.refresh_access_token()
            return self._request(
                method, path, params=params, json=json, auth=auth, retry_on_401=False
            )

        if response.status_code >= 400:
            try:
                payload = response.json()
            except Exception:
                payload = {"message": response.text}
            raise MeliAPIError(
                response.status_code,
                payload.get("message") or payload.get("error") or "API error",
                payload,
            )

        if response.status_code == 204:
            return {}
        return response.json()

    # ------------------------------------------------------------------
    # Public / common resources
    # ------------------------------------------------------------------

    def get_item(self, item_id: str) -> dict[str, Any]:
        """Get full item details by ID (e.g. MLA123456789)."""
        return self._request("GET", f"/items/{item_id}", auth=bool(self._access_token))

    def get_items(self, item_ids: list[str]) -> list[dict[str, Any]]:
        """Get multiple items (max 20 per call)."""
        if not item_ids:
            return []
        ids = ",".join(item_ids[:20])
        result = self._request("GET", "/items", params={"ids": ids}, auth=bool(self._access_token))
        # API returns list of {"code": 200, "body": {...}}
        if isinstance(result, list):
            return [r["body"] for r in result if r.get("code") == 200 and "body" in r]
        return []

    def search(
        self,
        query: str,
        *,
        site_id: str | None = None,
        limit: int = 20,
        offset: int = 0,
        category: str | None = None,
        seller_id: int | None = None,
        sort: str | None = None,
        price_min: float | None = None,
        price_max: float | None = None,
        condition: str | None = None,
    ) -> dict[str, Any]:
        """Public catalog search."""
        site = site_id or self.settings.meli_site_id
        params: dict[str, Any] = {
            "q": query,
            "limit": min(limit, 50),
            "offset": offset,
        }
        if category:
            params["category"] = category
        if seller_id:
            params["seller_id"] = seller_id
        if sort:
            params["sort"] = sort
        if condition:
            params["condition"] = condition
        if price_min is not None or price_max is not None:
            # format: price_min-price_max or *-price_max etc.
            low = str(int(price_min)) if price_min is not None else "*"
            high = str(int(price_max)) if price_max is not None else "*"
            params["price"] = f"{low}-{high}"

        return self._request("GET", f"/sites/{site}/search", params=params, auth=False)

    def search_seller_items(
        self,
        user_id: int | str,
        *,
        status: str | None = "active",
        limit: int = 50,
        offset: int = 0,
        search_type: str | None = None,
    ) -> dict[str, Any]:
        """List items belonging to a seller (requires authentication)."""
        params: dict[str, Any] = {"limit": min(limit, 50), "offset": offset}
        if status:
            params["status"] = status
        if search_type:
            params["search_type"] = search_type
        return self._request("GET", f"/users/{user_id}/items/search", params=params)

    def get_user(self, user_id: int | str | None = None) -> dict[str, Any]:
        """Get user info. If user_id is None, returns the authenticated user (/users/me)."""
        path = "/users/me" if user_id is None else f"/users/{user_id}"
        return self._request("GET", path)

    def get_item_description(self, item_id: str) -> dict[str, Any]:
        return self._request("GET", f"/items/{item_id}/description", auth=bool(self._access_token))

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "MeliClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
