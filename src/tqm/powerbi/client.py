"""Power BI REST API client with OAuth2 token acquisition.

Supports two auth modes:
  1. Service Principal (client_credentials) — preferred for automation
  2. Interactive (device code flow) — useful for one-off ops

Reference: https://learn.microsoft.com/en-us/rest/api/power-bi/
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

log = logging.getLogger(__name__)

_BASE = "https://api.powerbi.com/v1.0/myorg"
_AUTHORITY = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
_SCOPE = "https://analysis.windows.net/powerbi/api/.default"


class PowerBIClient:
    """Thin wrapper around the Power BI REST API."""

    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        workspace_id: str = "",
    ) -> None:
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.workspace_id = workspace_id
        self._token: str | None = None
        self._token_expiry: float = 0.0

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def _ensure_token(self) -> str:
        if self._token and time.time() < self._token_expiry - 60:
            return self._token

        url = _AUTHORITY.format(tenant_id=self.tenant_id)
        resp = httpx.post(
            url,
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": _SCOPE,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        self._token_expiry = time.time() + data.get("expires_in", 3600)
        log.debug("Acquired Power BI token, expires in %ss", data.get("expires_in"))
        return self._token  # type: ignore[return-value]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._ensure_token()}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Generic request helpers
    # ------------------------------------------------------------------

    @retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=2, max=16))
    def _get(self, path: str, workspace: bool = True) -> Any:
        url = self._url(path, workspace)
        resp = httpx.get(url, headers=self._headers(), timeout=30)
        resp.raise_for_status()
        return resp.json()

    @retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=2, max=16))
    def _post(self, path: str, body: dict, workspace: bool = True) -> Any:
        url = self._url(path, workspace)
        resp = httpx.post(url, headers=self._headers(), json=body, timeout=60)
        resp.raise_for_status()
        return resp.json() if resp.content else {}

    @retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=2, max=16))
    def _patch(self, path: str, body: dict, workspace: bool = True) -> Any:
        url = self._url(path, workspace)
        resp = httpx.patch(url, headers=self._headers(), json=body, timeout=60)
        resp.raise_for_status()
        return resp.json() if resp.content else {}

    @retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=2, max=16))
    def _delete(self, path: str, workspace: bool = True) -> None:
        url = self._url(path, workspace)
        resp = httpx.delete(url, headers=self._headers(), timeout=30)
        resp.raise_for_status()

    def _url(self, path: str, workspace: bool) -> str:
        if workspace and self.workspace_id:
            return f"{_BASE}/groups/{self.workspace_id}/{path.lstrip('/')}"
        return f"{_BASE}/{path.lstrip('/')}"

    # ------------------------------------------------------------------
    # Workspaces
    # ------------------------------------------------------------------

    def list_workspaces(self) -> list[dict]:
        return self._get("groups", workspace=False).get("value", [])

    # ------------------------------------------------------------------
    # Datasets
    # ------------------------------------------------------------------

    def list_datasets(self) -> list[dict]:
        return self._get("datasets").get("value", [])

    def get_dataset(self, dataset_id: str) -> dict:
        return self._get(f"datasets/{dataset_id}")

    def create_dataset(self, schema: dict) -> dict:
        return self._post("datasets", schema)

    def delete_dataset(self, dataset_id: str) -> None:
        self._delete(f"datasets/{dataset_id}")

    def push_rows(self, dataset_id: str, table_name: str, rows: list[dict]) -> None:
        """Push rows to a Push Dataset table (up to 10k rows per call)."""
        CHUNK = 10_000
        for i in range(0, len(rows), CHUNK):
            chunk = rows[i : i + CHUNK]
            self._post(f"datasets/{dataset_id}/tables/{table_name}/rows", {"rows": chunk})
            log.info("Pushed %d rows to %s", len(chunk), table_name)

    def clear_table(self, dataset_id: str, table_name: str) -> None:
        self._delete(f"datasets/{dataset_id}/tables/{table_name}/rows")

    # ------------------------------------------------------------------
    # Reports
    # ------------------------------------------------------------------

    def list_reports(self) -> list[dict]:
        return self._get("reports").get("value", [])

    def get_report(self, report_id: str) -> dict:
        return self._get(f"reports/{report_id}")

    def clone_report(self, report_id: str, name: str, target_workspace_id: str = "") -> dict:
        body: dict = {"name": name}
        if target_workspace_id:
            body["targetWorkspaceId"] = target_workspace_id
        return self._post(f"reports/{report_id}/Clone", body)

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def trigger_refresh(self, dataset_id: str) -> None:
        self._post(f"datasets/{dataset_id}/refreshes", {"notifyOption": "MailOnFailure"})
        log.info("Triggered refresh for dataset %s", dataset_id)

    def get_refresh_history(self, dataset_id: str) -> list[dict]:
        return self._get(f"datasets/{dataset_id}/refreshes").get("value", [])
