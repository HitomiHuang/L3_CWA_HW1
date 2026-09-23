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


def build_forecast_map(period_data: pd.DataFrame) -> folium.Map:
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
        folium.CircleMarker(
            location=coordinates, radius=9, color="white", weight=2,
            fill=True, fill_color=_temperature_color(row["max_temp"]), fill_opacity=0.92,
            tooltip=location, popup=folium.Popup(popup_html, max_width=260),
        ).add_to(forecast_map)
    legend = """
    <div style="position:fixed;bottom:24px;left:24px;z-index:9999;background:white;padding:10px 12px;border-radius:10px;box-shadow:0 2px 10px #0002;font:12px sans-serif;color:#334155">
      <b>預報最高溫</b><br><span style="color:#DC2626">●</span> ≥ 35°C　<span style="color:#F97316">●</span> 30–34°C<br>
      <span style="color:#FBBF24">●</span> 25–29°C　<span style="color:#60A5FA">●</span> 20–24°C<br>
      <span style="color:#2563EB">●</span> &lt; 20°C　<span style="color:#94A3B8">●</span> 無資料
    </div>
    """
    forecast_map.get_root().html.add_child(folium.Element(legend))
    return forecast_map
