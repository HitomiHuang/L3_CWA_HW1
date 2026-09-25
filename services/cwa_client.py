"""Fetch CWA JSON for the local crawler and Streamlit app."""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from config import CWA_API_URL, CWA_DATASET_ID, REQUEST_TIMEOUT_SECONDS, ROOT_DIR


class CWAClientError(RuntimeError):
    pass


def local_api_key() -> str:
    key = os.environ.get("CWA_API_KEY", "").strip()
    if key:
        return key
    path = Path(ROOT_DIR) / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            name, separator, value = line.strip().partition("=")
            if separator and name.strip() == "CWA_API_KEY":
                return value.strip().strip("\"'")
    try:
        import streamlit as st
        return str(st.secrets.get("CWA_API_KEY", "") or st.secrets.get("cwa", {}).get("api_key", "")).strip()
    except Exception:
        return ""


class CWAClient:
    def __init__(self, api_key: str | None = None, timeout: int = REQUEST_TIMEOUT_SECONDS) -> None:
        self.api_key = api_key if api_key is not None else local_api_key()
        self.timeout = timeout

    def fetch_36_hour_forecast(self) -> dict:
        return self.fetch_dataset(CWA_DATASET_ID)

    def fetch_dataset(self, dataset_id: str) -> dict:
        if not self.api_key:
            raise CWAClientError("找不到 CWA_API_KEY；請在 .env 或環境變數設定。")
        url = CWA_API_URL.rsplit("/", 1)[0] + "/" + dataset_id
        url += "?" + urlencode({"Authorization": self.api_key, "format": "JSON"})
        try:
            with urlopen(url, timeout=self.timeout) as response:
                payload = json.load(response)
        except HTTPError as exc:
            raise CWAClientError(f"中央氣象署回應 HTTP {exc.code}；請檢查授權碼與資料集權限。") from exc
        except (URLError, TimeoutError) as exc:
            raise CWAClientError("無法連線中央氣象署，請稍後重試。") from exc
        except (ValueError, UnicodeError) as exc:
            raise CWAClientError("中央氣象署回傳內容不是有效 JSON。") from exc
        if str(payload.get("success", "true")).lower() not in {"true", "1"}:
            raise CWAClientError("中央氣象署 API 回報失敗；請檢查授權碼與資料集權限。")
        if not isinstance(payload.get("records"), dict) or not payload["records"]:
            raise CWAClientError(f"資料集 {dataset_id} 沒有可用資料。")
        return payload

    def fetch_file(self, dataset_id: str, format: str = "XML") -> bytes:
        """Download a CWA file dataset, which is distinct from the REST datastore."""
        if not self.api_key:
            raise CWAClientError("找不到 CWA_API_KEY；請在 .env 或環境變數設定。")
        url = f"https://opendata.cwa.gov.tw/fileapi/v1/opendataapi/{dataset_id}"
        url += "?" + urlencode({"Authorization": self.api_key, "format": format})
        try:
            with urlopen(url, timeout=self.timeout) as response:
                return response.read()
        except HTTPError as exc:
            raise CWAClientError(f"中央氣象署檔案下載回應 HTTP {exc.code}。") from exc
        except (URLError, TimeoutError) as exc:
            raise CWAClientError("無法連線中央氣象署檔案下載服務，請稍後重試。") from exc
