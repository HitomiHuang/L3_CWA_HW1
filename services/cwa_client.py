from __future__ import annotations

import os
from typing import Any

import truststore

truststore.inject_into_ssl()

import requests
from dotenv import load_dotenv

from config import CWA_API_URL, CWA_DATASET_ID, REQUEST_TIMEOUT_SECONDS


class CWAClientError(RuntimeError):
    """A user-readable error while retrieving CWA data."""


class CWAClient:
    def __init__(self, api_key: str | None = None, timeout: int = REQUEST_TIMEOUT_SECONDS) -> None:
        load_dotenv()
        self.api_key = api_key or os.getenv("CWA_API_KEY", "").strip() or self._streamlit_secret()
        self.timeout = timeout

    @staticmethod
    def _streamlit_secret() -> str:
        try:
            import streamlit as st

            secrets = st.secrets
            value = secrets.get("CWA_API_KEY", "")
            if value:
                return str(value).strip()

            # Also accept the common grouped TOML form: [cwa] api_key = "...".
            for section_name in ("cwa", "CWA"):
                section = secrets.get(section_name, {})
                if hasattr(section, "get"):
                    value = section.get("api_key", "") or section.get("CWA_API_KEY", "")
                    if value:
                        return str(value).strip()
        except Exception:
            pass
        return ""

    def fetch_36_hour_forecast(self) -> dict[str, Any]:
        return self.fetch_dataset(CWA_DATASET_ID)

    def fetch_dataset(self, dataset_id: str) -> dict[str, Any]:
        if not self.api_key:
            raise CWAClientError(
                '找不到 CWA_API_KEY。本機請在 .env 設定；部署至 Streamlit Community Cloud 時，'
                '請在 App settings → Secrets 加入 CWA_API_KEY = "你的授權碼"。'
            )
        try:
            response = requests.get(
                CWA_API_URL.rsplit("/", 1)[0] + "/" + dataset_id,
                params={"Authorization": self.api_key, "format": "JSON"},
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.Timeout as exc:
            raise CWAClientError(f"連線中央氣象署逾時（{self.timeout} 秒）。請稍後重試。") from exc
        except requests.RequestException as exc:
            message = str(exc).replace(self.api_key, "[redacted]")
            raise CWAClientError(f"無法取得中央氣象署資料：{message}") from exc
        try:
            payload = response.json()
        except ValueError as exc:
            raise CWAClientError("中央氣象署回傳內容不是有效 JSON。") from exc
        success = payload.get("success")
        if success is not None and str(success).lower() not in {"true", "1"}:
            error = payload.get("error")
            message = error.get("message") if isinstance(error, dict) else error
            message = message or payload.get("message") or "請確認 API Key 與資料集權限。"
            message = str(message).replace(self.api_key, "[redacted]")
            raise CWAClientError(f"中央氣象署 API 回報失敗：{message}")
        records = payload.get("records")
        if not isinstance(records, dict) or not records:
            raise CWAClientError(f"API 回傳成功，但資料集 {dataset_id} 沒有資料；請稍後重試。")
        return payload
