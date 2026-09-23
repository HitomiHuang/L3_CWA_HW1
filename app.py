from __future__ import annotations

import html
from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from components.charts import build_rain_chart, build_snapshot_chart, build_temperature_chart
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


def _render_observation_card(observations: pd.DataFrame, city: str, fetched_at: object | None) -> None:
    st.subheader(f"{city} 測站觀測")
    if observations.empty or "county" not in observations:
        st.info("尚無測站觀測資料。按側欄更新按鈕取得最新整點觀測。")
        return
    city_observations = observations[observations["county"] == city].sort_values("observed_at", ascending=False)
    if city_observations.empty:
        st.info(f"目前的觀測批次沒有 {city} 的有效測站資料。")
        return
    usable = city_observations[city_observations[["temperature", "relative_humidity", "wind_speed"]].notna().any(axis=1)]
    observation = (usable if not usable.empty else city_observations).iloc[0]
    top = st.columns(3)
    top[0].metric("測站氣溫", "暫無資料" if pd.isna(observation["temperature"]) else f"{observation['temperature']:g} °C")
    top[1].metric("相對濕度", "暫無資料" if pd.isna(observation["relative_humidity"]) else f"{observation['relative_humidity']:g}%")
    top[2].metric("平均風速", "暫無資料" if pd.isna(observation["wind_speed"]) else f"{observation['wind_speed']:g} m/s")
    observed_time = _format_time(observation["observed_at"], "%Y-%m-%d %H:%M:%S")
    fetched_label = _format_time(fetched_at, "%Y-%m-%d %H:%M:%S") if fetched_at else "未記錄"
    st.caption(f"測站觀測（非縣市預報）｜{_safe(observation['station_name'])}・{_safe(observation['town'], '所在鄉鎮未提供')}｜觀測時間 {observed_time}｜取得時間 {fetched_label}")
    observed_at = pd.to_datetime(observation["observed_at"], errors="coerce", utc=True)
    if not pd.isna(observed_at) and pd.Timestamp.now(tz="UTC") - observed_at > pd.Timedelta(hours=2):
        st.warning("此測站讀值超過 2 小時，請以標示的觀測時間判斷資料新舊。")
    if pd.notna(observation["weather"]):
        st.write(f"觀測天氣現象：{_safe(observation['weather'])}")


def _render_rankings(all_data: pd.DataFrame) -> None:
    with st.expander("全台同時段預報排行"):
        periods = sorted(set(zip(all_data["start_time"].astype(str), all_data["end_time"].astype(str))))
        if not periods:
            st.info("目前沒有可比較的預報時段。")
            return
        chosen = st.selectbox(
            "排行預報有效期間",
            periods,
            format_func=lambda pair: f"{_format_time(pair[0])} – {_format_time(pair[1])}",
            key="ranking_period",
        )
        same_period = all_data[(all_data["start_time"].astype(str) == chosen[0]) & (all_data["end_time"].astype(str) == chosen[1])]
        high, rain = st.columns(2, gap="large")
        with high:
            st.markdown("**預報最高溫 Top 5**")
            ranking = same_period.dropna(subset=["max_temp"]).nlargest(5, "max_temp")[["location", "max_temp"]].rename(columns={"location": "縣市", "max_temp": "最高溫 (°C)"})
            st.dataframe(ranking, width="stretch", hide_index=True)
        with rain:
            st.markdown("**降雨機率 Top 5**")
            ranking = same_period.dropna(subset=["pop"]).nlargest(5, "pop")[["location", "pop"]].rename(columns={"location": "縣市", "pop": "降雨機率 (%)"})
            st.dataframe(ranking, width="stretch", hide_index=True)
        st.caption("排行只比較最新成功批次中，預報有效起訖時間完全相同的縣市資料。")


def main() -> None:
    st.set_page_config(page_title="台灣天氣預報", page_icon="🌦️", layout="wide", initial_sidebar_state="collapsed")
    _load_css()

    repository = ForecastRepository(DATABASE_PATH)
    repository.initialize()
    service = WeatherService(repository)

    title_column, action_column = st.columns([4.1, 1], vertical_alignment="center")
    with title_column:
        st.markdown(
            """
            <div class="weather-header">
                <div class="eyebrow">TAIWAN WEATHER · FORECAST & OBSERVATIONS</div>
                <h1>台灣天氣預報</h1>
                <p>整合短期與一週預報、測站觀測和全台同時段排行。</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with action_column:
        if st.button("⟳　更新所有資料", type="primary", width="stretch"):
            completed, failures = [], []
            refresh_jobs = [
                ("36 小時預報", service.refresh),
                ("一週預報", service.refresh_weekly_forecast),
                ("測站觀測", service.refresh_observations),
            ]
            with st.spinner("正在更新預報與測站資料…"):
                for label, refresh in refresh_jobs:
                    try:
                        _, count = refresh()
                        completed.append(f"{label} {count} 筆")
                    except Exception as exc:
                        failures.append(f"{label}：{exc}")
            st.session_state["refresh_message"] = "已更新：" + "；".join(completed) if completed else None
            st.session_state["refresh_errors"] = failures
            st.rerun()

    if st.session_state.get("refresh_message"):
        st.success(st.session_state["refresh_message"])
    if st.session_state.get("refresh_errors"):
        st.warning("部分資料更新失敗：" + "；".join(st.session_state["refresh_errors"]))

    latest_run = repository.get_latest_run()
    if latest_run:
        all_data = repository.get_run_periods(int(latest_run["id"]))
        updated = _format_time(latest_run["fetched_at"], "%Y-%m-%d %H:%M:%S")
        issue_time = latest_run.get("issue_time")
    else:
        all_data = pd.DataFrame(columns=["location", "start_time", "end_time", "wx", "weather_code", "min_temp", "max_temp", "pop", "comfort", "fetched_at"])
        updated = "尚無資料"
        issue_time = None

    weekly_run = repository.get_latest_weekly_run()
    weekly_data = repository.get_weekly_periods(int(weekly_run["id"])) if weekly_run else pd.DataFrame(
        columns=["location", "start_time", "end_time", "wx", "description", "min_temp", "max_temp", "pop", "relative_humidity", "fetched_at"]
    )
    observation_run = repository.get_latest_observation_run()
    observations = repository.get_observations(int(observation_run["id"])) if observation_run else pd.DataFrame(
        columns=["station_id", "station_name", "county", "town", "observed_at", "latitude", "longitude", "weather", "temperature", "relative_humidity", "wind_speed"]
    )

    top_left, top_right = st.columns([3, 1])
    with top_left:
        st.markdown(f"<div class='update-label'>資料取得時間　<strong>{html.escape(updated)}</strong></div>", unsafe_allow_html=True)
    with top_right:
        st.markdown("<div class='source-label'>預報資料 · Asia/Taipei</div>", unsafe_allow_html=True)

    if all_data.empty:
        st.info("資料庫目前沒有預報。設定 CWA_API_KEY 後，按上方「更新所有資料」載入資料。")
        st.markdown("本機請填入 `.env`；Streamlit Community Cloud 請在 App settings → Secrets 貼上：")
        st.code('CWA_API_KEY = "你的中央氣象署授權碼"', language="toml")
        st.markdown("API Key 申請方式與操作說明請參考專案內的 README。")
        return

    if _forecast_is_stale(latest_run["fetched_at"]):
        st.warning("目前顯示的資料已超過 12 小時未更新；可按側欄按鈕取得最新預報。")

    available_cities = [name for name in CITY_NAMES if name in set(all_data["location"])]
    available_cities.extend(name for name in sorted(set(all_data["location"])) if name not in CITY_NAMES)
    default_city = "臺中市" if "臺中市" in available_cities else available_cities[0]
    periods = sorted(set(zip(all_data["start_time"].astype(str), all_data["end_time"].astype(str))))
    city_control, period_control, layer_control = st.columns([1.0, 1.5, 1.15], gap="medium")
    with city_control:
        selected_city = st.selectbox("縣市", available_cities, index=available_cities.index(default_city), key="map_city")
    city_data = all_data[all_data["location"] == selected_city].sort_values("start_time").reset_index(drop=True)

    with period_control:
        default_period = (str(city_data.iloc[0]["start_time"]), str(city_data.iloc[0]["end_time"]))
        selected_period = st.selectbox(
            "預報時段",
            periods,
            index=periods.index(default_period) if default_period in periods else 0,
            format_func=lambda pair: f"{_format_time(pair[0])} – {_format_time(pair[1])}",
            key="map_period",
        )
    with layer_control:
        selected_layer = st.radio("地圖圖層", ["最高溫", "降雨機率"], horizontal=True, key="map_layer")

    city_data = all_data[all_data["location"] == selected_city].sort_values("start_time").reset_index(drop=True)

    if city_data.empty:
        st.warning(f"{selected_city} 暫無預報資料。")
        return

    first = city_data.iloc[0]
    selected_city_period = city_data[
        (city_data["start_time"].astype(str) == selected_period[0])
        & (city_data["end_time"].astype(str) == selected_period[1])
    ]
    focus = selected_city_period.iloc[0] if not selected_city_period.empty else first
    start_label, end_label = _format_time(selected_period[0]), _format_time(selected_period[1])
    map_data = all_data[
        (all_data["start_time"].astype(str) == selected_period[0])
        & (all_data["end_time"].astype(str) == selected_period[1])
    ]

    st.markdown(f"### 全台預報地圖　<span class='map-period-label'>{html.escape(start_label)} – {html.escape(end_label)}</span>", unsafe_allow_html=True)
    forecast_map = build_forecast_map(map_data, "rain" if selected_layer == "降雨機率" else "temperature")
    st_folium(forecast_map, height=640, use_container_width=True, returned_objects=[])
    if selected_layer == "降雨機率":
        st.caption("圓點顏色與大小表示各縣市代表點的降雨機率；圓點越大、顏色越深，機率越高。點選標記可查看完整預報。")
    else:
        st.caption("圓點顏色表示各縣市代表點的預報最高溫。點選標記可查看天氣現象、最低溫、最高溫與降雨機率。")

    st.markdown(f"#### {html.escape(selected_city)}・{_safe(focus['wx'])}")
    focus_metrics = st.columns(4)
    focus_metrics[0].metric("預報最低", "暫無資料" if pd.isna(focus["min_temp"]) else f"{focus['min_temp']:g} °C")
    focus_metrics[1].metric("預報最高", "暫無資料" if pd.isna(focus["max_temp"]) else f"{focus['max_temp']:g} °C")
    focus_metrics[2].metric("降雨機率", "暫無資料" if pd.isna(focus["pop"]) else f"{focus['pop']:g}%")
    focus_metrics[3].metric("舒適度", _safe(focus["comfort"]))
    if selected_city_period.empty:
        st.caption(f"{selected_city} 沒有這個全台預報時段的資料，目前摘要顯示該縣市最新一筆時段。")

    _render_observation_card(observations, selected_city, observation_run.get("fetched_at") if observation_run else None)

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

    with st.expander("未來一週預報（12 小時區間）"):
        weekly_city = weekly_data[weekly_data["location"] == selected_city].sort_values("start_time").reset_index(drop=True)
        if weekly_city.empty:
            st.info("目前沒有一週預報資料。按上方「更新所有資料」取得 F-D0047-091。")
        else:
            weekly_fetched = _format_time(weekly_run["fetched_at"], "%Y-%m-%d %H:%M:%S")
            st.caption(f"資料集 F-D0047-091｜資料取得時間 {weekly_fetched}｜每筆為 12 小時預報有效期間。")
            weekly_chart_left, weekly_chart_right = st.columns(2, gap="large")
            with weekly_chart_left:
                st.plotly_chart(build_temperature_chart(weekly_city, "未來一週溫度"), width="stretch")
            with weekly_chart_right:
                st.plotly_chart(build_rain_chart(weekly_city, "未來一週 12 小時降雨機率"), width="stretch")
            weekly_display = weekly_city[["start_time", "end_time", "wx", "min_temp", "max_temp", "pop", "relative_humidity", "description"]].copy()
            weekly_display.columns = ["開始時間", "結束時間", "天氣現象", "最低溫 (°C)", "最高溫 (°C)", "12 小時降雨機率 (%)", "平均相對濕度 (%)", "預報描述"]
            for column in ("開始時間", "結束時間"):
                weekly_display[column] = pd.to_datetime(weekly_display[column], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")
            st.dataframe(weekly_display, width="stretch", hide_index=True)

    _render_rankings(all_data)

    with st.expander("同一時段的歷次預報版本比較"):
        snapshot_history = repository.get_snapshot_history(selected_city, str(focus["start_time"]), str(focus["end_time"]))
        st.caption(f"比較 {selected_city} 在同一有效期間（{start_label}–{end_label}）的不同抓取版本；這是預報修訂紀錄，不是歷史實測氣溫。")
        if snapshot_history.empty:
            st.info("尚無可比較的預報快照。")
        else:
            st.plotly_chart(build_snapshot_chart(snapshot_history), width="stretch")
            snapshot_display = snapshot_history.copy()
            snapshot_display["fetched_at"] = pd.to_datetime(snapshot_display["fetched_at"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")
            snapshot_display = snapshot_display[["run_id", "fetched_at", "wx", "min_temp", "max_temp", "pop"]]
            snapshot_display.columns = ["批次", "資料取得時間", "天氣現象", "最低溫 (°C)", "最高溫 (°C)", "降雨機率 (%)"]
            st.dataframe(snapshot_display, width="stretch", hide_index=True)

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
