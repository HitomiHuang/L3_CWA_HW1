from __future__ import annotations

import html

import folium
import pandas as pd

from config import CITY_COORDINATES


def _temperature_color(value: object) -> str:
    if value is None or pd.isna(value):
        return "#94A3B8"
    temperature = float(value)
    if temperature >= 35:
        return "#DC2626"
    if temperature >= 30:
        return "#F97316"
    if temperature >= 25:
        return "#FBBF24"
    if temperature >= 20:
        return "#60A5FA"
    return "#2563EB"


def _rain_color(value: object) -> str:
    if value is None or pd.isna(value):
        return "#94A3B8"
    probability = float(value)
    if probability >= 80:
        return "#1E3A8A"
    if probability >= 60:
        return "#1D4ED8"
    if probability >= 40:
        return "#3B82F6"
    if probability >= 20:
        return "#93C5FD"
    return "#DBEAFE"


def build_forecast_map(period_data: pd.DataFrame, metric: str = "temperature") -> folium.Map:
    show_rain = metric == "rain"
    forecast_map = folium.Map(location=[23.7, 120.9], zoom_start=7, min_zoom=6, max_zoom=11, tiles="OpenStreetMap", control_scale=True)
    for _, row in period_data.iterrows():
        location = str(row["location"])
        coordinates = CITY_COORDINATES.get(location)
        if coordinates is None:
            continue
        low = "暫無資料" if pd.isna(row["min_temp"]) else f"{row['min_temp']:g} °C"
        high = "暫無資料" if pd.isna(row["max_temp"]) else f"{row['max_temp']:g} °C"
        pop = "暫無資料" if pd.isna(row["pop"]) else f"{row['pop']:g}%"
        wx = html.escape(str(row["wx"])) if pd.notna(row["wx"]) else "暫無資料"
        popup_html = f"<div style='font-family:sans-serif;min-width:150px'><b>{html.escape(location)}・縣市代表點</b><br>天氣：{wx}<br>最低 / 最高：{low} / {high}<br>降雨機率：{pop}</div>"
        value = row["pop"] if show_rain else row["max_temp"]
        fill_color = _rain_color(value) if show_rain else _temperature_color(value)
        if show_rain:
            radius = 6 if pd.isna(value) else 6 + min(max(float(value), 0), 100) * 0.09
            measure = f"降雨 {pop}"
        else:
            radius = 9
            measure = f"最高 {high}"
        folium.CircleMarker(
            location=coordinates, radius=radius, color="white", weight=2,
            fill=True, fill_color=fill_color, fill_opacity=0.92,
            tooltip=f"{html.escape(location)}｜{measure}", popup=folium.Popup(popup_html, max_width=260),
        ).add_to(forecast_map)
    if show_rain:
        legend = """
        <div style="position:fixed;bottom:24px;left:24px;z-index:9999;background:white;padding:11px 14px;border-radius:12px;box-shadow:0 2px 14px #0f172a22;font:12px/1.8 sans-serif;color:#334155">
          <b>降雨機率</b><br><span style="color:#1E3A8A">●</span> 80–100%　<span style="color:#1D4ED8">●</span> 60–79%<br>
          <span style="color:#3B82F6">●</span> 40–59%　<span style="color:#93C5FD">●</span> 20–39%<br>
          <span style="color:#DBEAFE">●</span> 0–19%　<span style="color:#94A3B8">●</span> 無資料<br>
          圓點越大，降雨機率越高
        </div>
        """
    else:
        legend = """
        <div style="position:fixed;bottom:24px;left:24px;z-index:9999;background:white;padding:11px 14px;border-radius:12px;box-shadow:0 2px 14px #0f172a22;font:12px/1.8 sans-serif;color:#334155">
          <b>預報最高溫</b><br><span style="color:#DC2626">●</span> ≥ 35°C　<span style="color:#F97316">●</span> 30–34°C<br>
          <span style="color:#FBBF24">●</span> 25–29°C　<span style="color:#60A5FA">●</span> 20–24°C<br>
          <span style="color:#2563EB">●</span> &lt; 20°C　<span style="color:#94A3B8">●</span> 無資料
        </div>
        """
    forecast_map.get_root().html.add_child(folium.Element(legend))
    return forecast_map
