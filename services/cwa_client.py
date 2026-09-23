from __future__ import annotations

import os
from typing import Any

import truststore

truststore.inject_into_ssl()

import requests
from dotenv import load_dotenv

from config import CWA_API_URL, REQUEST_TIMEOUT_SECONDS


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

            return str(st.secrets.get("CWA_API_KEY", "")).strip()
        except Exception:
            return ""

    def fetch_36_hour_forecast(self) -> dict[str, Any]:
        if not self.api_key:
            raise CWAClientError("找不到 CWA_API_KEY。請複製 .env.example 為 .env，填入中央氣象署授權碼後再更新資料。")
        try:
            response = requests.get(
                CWA_API_URL,
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
        if not isinstance(records, dict) or not records.get("location"):
            raise CWAClientError("API 回傳成功，但找不到預報縣市資料；請稍後重試。")
        return payload
