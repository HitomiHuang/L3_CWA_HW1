from __future__ import annotations

import html
from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from components.charts import build_rain_chart, build_temperature_chart
from components.map_view import build_forecast_map
from config import CITY_NAMES, DATABASE_PATH
from database.repository import ForecastRepository
from services.weather_service import WeatherService


ROOT = Path(__file__).resolve().parent


def _load_css() -> None:
    css_path = ROOT / "assets" / "style.css"
    if css_path.exists():
        st.markdown(f"<style>{css_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def _safe(value: object, fallback: str = "暫無資料") -> str:
    if value is None or pd.isna(value) or str(value).strip() == "":
        return fallback
    return html.escape(str(value))


def _format_time(value: object, fmt: str = "%m/%d %H:%M") -> str:
    parsed = pd.to_datetime(value, errors="coerce")
    return parsed.strftime(fmt) if not pd.isna(parsed) else "暫無資料"


def _forecast_is_stale(fetched_at: object) -> bool:
    parsed = pd.to_datetime(fetched_at, errors="coerce", utc=True)
    return not pd.isna(parsed) and (pd.Timestamp.now(tz="UTC") - parsed) > pd.Timedelta(hours=12)


def _weather_period_cards(city_data: pd.DataFrame) -> None:
    st.subheader("時段預報")
    if city_data.empty:
        st.info("目前沒有可顯示的預報時段。請先更新資料，或稍後再試。")
        return
    columns = st.columns(min(len(city_data), 3))
    for index, (_, row) in enumerate(city_data.head(3).iterrows()):
        with columns[index % len(columns)]:
            start = _format_time(row["start_time"])
            end = _format_time(row["end_time"])
            low = "暫無資料" if pd.isna(row["min_temp"]) else f"{row['min_temp']:g}°"
            high = "暫無資料" if pd.isna(row["max_temp"]) else f"{row['max_temp']:g}°"
            pop = "暫無資料" if pd.isna(row["pop"]) else f"{row['pop']:g}%"
            st.markdown(
                f"""
                <div class="period-card">
                    <div class="period-time">{html.escape(start)} – {html.escape(end)}</div>
                    <div class="period-weather">{_safe(row['wx'])}</div>
                    <div class="period-temp">{low}<span> / </span>{high}</div>
                    <div class="period-caption">最低 / 最高　・　降雨 {pop}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _render_data_table(city_data: pd.DataFrame) -> None:
    display = city_data[["start_time", "end_time", "wx", "min_temp", "max_temp", "pop", "comfort"]].copy()
    display.columns = ["開始時間", "結束時間", "天氣現象", "最低溫 (°C)", "最高溫 (°C)", "降雨機率 (%)", "舒適度"]
    for column in ("開始時間", "結束時間"):
        display[column] = pd.to_datetime(display[column], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")
    st.dataframe(display, width="stretch", hide_index=True)


def main() -> None:
    st.set_page_config(page_title="台灣天氣預報", page_icon="🌦️", layout="wide")
    _load_css()

    repository = ForecastRepository(DATABASE_PATH)
    repository.initialize()
    service = WeatherService(repository)

    st.markdown(
        """
        <div class="weather-header">
            <div class="eyebrow">TAIWAN WEATHER · 36-HOUR FORECAST</div>
            <h1>台灣天氣預報</h1>
            <p>掌握各縣市未來時段的天氣、溫度與降雨機率。</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.markdown("### 資料控制")
        st.caption("資料來源：中央氣象署 F-C0032-001")
        if st.button("⟳　更新預報資料", type="primary", use_container_width=True):
            with st.spinner("正在向中央氣象署取得最新預報…"):
                try:
                    _, count = service.refresh()
                    st.session_state["refresh_message"] = f"已更新 {count} 筆預報資料。"
                    st.session_state["refresh_error"] = None
                except Exception as exc:  # Keep the existing saved forecast available on API errors.
                    st.session_state["refresh_error"] = str(exc)
                    st.session_state["refresh_message"] = None
            st.rerun()

        if st.session_state.get("refresh_message"):
            st.success(st.session_state["refresh_message"])
        if st.session_state.get("refresh_error"):
            st.error(st.session_state["refresh_error"])

    latest_run = repository.get_latest_run()
    if latest_run:
        all_data = repository.get_run_periods(int(latest_run["id"]))
        updated = _format_time(latest_run["fetched_at"], "%Y-%m-%d %H:%M:%S")
        issue_time = latest_run.get("issue_time")
    else:
        all_data = pd.DataFrame(columns=["location", "start_time", "end_time", "wx", "weather_code", "min_temp", "max_temp", "pop", "comfort", "fetched_at"])
        updated = "尚無資料"
        issue_time = None

    top_left, top_right = st.columns([3, 1])
    with top_left:
        st.markdown(f"<div class='update-label'>資料取得時間　<strong>{html.escape(updated)}</strong></div>", unsafe_allow_html=True)
    with top_right:
        st.markdown("<div class='source-label'>預報資料 · Asia/Taipei</div>", unsafe_allow_html=True)

    if all_data.empty:
        st.info("資料庫目前沒有預報。請在左側設定 `.env` 的 `CWA_API_KEY`，再按「更新預報資料」。")
        st.markdown("API Key 申請方式與操作說明請參考專案內的 README。")
        return

    if _forecast_is_stale(latest_run["fetched_at"]):
        st.warning("目前顯示的資料已超過 12 小時未更新；可按側欄按鈕取得最新預報。")

    available_cities = [name for name in CITY_NAMES if name in set(all_data["location"])]
    available_cities.extend(name for name in sorted(set(all_data["location"])) if name not in CITY_NAMES)
    default_city = "臺中市" if "臺中市" in available_cities else available_cities[0]
    selected_city = st.selectbox("選擇縣市", available_cities, index=available_cities.index(default_city), label_visibility="collapsed")
    city_data = all_data[all_data["location"] == selected_city].sort_values("start_time").reset_index(drop=True)

    if city_data.empty:
        st.warning(f"{selected_city} 暫無預報資料。")
        return

    first = city_data.iloc[0]
    start_label, end_label = _format_time(first["start_time"]), _format_time(first["end_time"])
    hero, map_column = st.columns([0.92, 1.08], gap="large")
    with hero:
        low_hero = "–" if pd.isna(first["min_temp"]) else f"{first['min_temp']:g}°"
        high_hero = "–" if pd.isna(first["max_temp"]) else f"{first['max_temp']:g}°"
        st.markdown(
            f"""
            <div class="hero-card">
                <div class="hero-topline">{html.escape(selected_city)}　<span>縣市代表點預報</span></div>
                <div class="hero-condition">{_safe(first['wx'])}</div>
                <div class="hero-temperature"><span>{low_hero}</span><span class="temp-divider">/</span><span>{high_hero}</span></div>
                <div class="hero-caption">預報有效期間　{html.escape(start_label)} – {html.escape(end_label)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        low_metric = "暫無資料" if pd.isna(first["min_temp"]) else f"{first['min_temp']:g} °C"
        high_metric = "暫無資料" if pd.isna(first["max_temp"]) else f"{first['max_temp']:g} °C"
        pop_metric = "暫無資料" if pd.isna(first["pop"]) else f"{first['pop']:g}%"
        comfort = _safe(first["comfort"])
        metrics_top = st.columns(2)
        metrics_top[0].metric("預報最低", low_metric)
        metrics_top[1].metric("預報最高", high_metric)
        metrics_bottom = st.columns(2)
        metrics_bottom[0].metric("降雨機率", pop_metric)
        metrics_bottom[1].metric("舒適度", comfort)
    with map_column:
        st.subheader("全台縣市預報地圖")
        selected_start = str(first["start_time"])
        map_data = all_data[all_data["start_time"].astype(str) == selected_start]
        if map_data.empty:
            map_data = city_data.iloc[[0]].copy()
        forecast_map = build_forecast_map(map_data)
        st_folium(forecast_map, height=450, use_container_width=True, returned_objects=[])
        st.caption(f"各點皆為同一預報時段（{start_label}–{end_label}）的縣市代表點；圖例依預報最高溫分類。")

    _weather_period_cards(city_data)

    st.subheader("溫度與降雨趨勢")
    chart_left, chart_right = st.columns(2, gap="large")
    with chart_left:
        st.plotly_chart(build_temperature_chart(city_data), width="stretch")
    with chart_right:
        st.plotly_chart(build_rain_chart(city_data), width="stretch")

    st.subheader(f"{selected_city} 預報資料表")
    st.caption("以下資料由 SQLite 最新成功批次查詢；有效期間為預報時段，不是資料抓取時間。")
    _render_data_table(city_data)

    with st.expander("歷次預報批次"):
        recent_runs = repository.get_recent_runs()
        if recent_runs.empty:
            st.caption("尚無歷次成功批次。")
        else:
            recent_runs["fetched_at"] = recent_runs["fetched_at"].map(lambda value: _format_time(value, "%Y-%m-%d %H:%M:%S"))
            recent_runs["issue_time"] = recent_runs["issue_time"].map(lambda value: _format_time(value, "%Y-%m-%d %H:%M:%S") if value else "來源未提供")
            recent_runs["source_updated"] = recent_runs["source_updated"].map(lambda value: _format_time(value, "%Y-%m-%d %H:%M:%S") if value else "來源未提供")
            recent_runs.columns = ["批次", "資料集", "資料取得時間", "來源發布時間", "來源更新時間", "資料筆數"]
            st.dataframe(recent_runs, width="stretch", hide_index=True)

    with st.expander("資料來源與時間說明"):
        issue_display = _format_time(issue_time, "%Y-%m-%d %H:%M:%S") if issue_time else "來源未提供"
        st.write(f"資料集：中央氣象署一般天氣預報－今明 36 小時天氣預報（F-C0032-001）。來源發布時間：{issue_display}。")
        st.write("地圖標記是縣市代表座標，並非測站位置；畫面只呈現預報，不代表即時觀測。")


if __name__ == "__main__":
    main()
