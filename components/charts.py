from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go


def _base_layout(figure: go.Figure, title: str) -> go.Figure:
    figure.update_layout(
        title={"text": title, "font": {"size": 16, "color": "#1E293B"}},
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "sans-serif", "color": "#475569"},
        margin={"l": 12, "r": 16, "t": 48, "b": 12},
        legend={"orientation": "h", "y": 1.08, "x": 0}, hovermode="x unified",
    )
    figure.update_xaxes(showgrid=False, tickformat="%m/%d\n%H:%M", title=None)
    figure.update_yaxes(gridcolor="#E8EDF4", zeroline=False)
    return figure


def build_temperature_chart(data: pd.DataFrame) -> go.Figure:
    figure = go.Figure()
    x_values = pd.to_datetime(data["start_time"], errors="coerce")
    if data["max_temp"].notna().any():
        figure.add_trace(go.Scatter(x=x_values, y=data["max_temp"], name="最高溫", mode="lines+markers", line={"color": "#F59E0B", "width": 3}, marker={"size": 8}, connectgaps=False))
    if data["min_temp"].notna().any():
        figure.add_trace(go.Scatter(x=x_values, y=data["min_temp"], name="最低溫", mode="lines+markers", line={"color": "#4A90E2", "width": 3}, marker={"size": 8}, connectgaps=False))
    figure.update_yaxes(title="溫度 (°C)")
    return _base_layout(figure, "預報溫度")


def build_rain_chart(data: pd.DataFrame) -> go.Figure:
    figure = go.Figure()
    x_values = pd.to_datetime(data["start_time"], errors="coerce")
    if data["pop"].notna().any():
        end_values = pd.to_datetime(data["end_time"], errors="coerce")
        widths = ((end_values - x_values).dt.total_seconds() * 800).fillna(7_200_000).tolist()
        figure.add_trace(go.Bar(x=x_values, y=data["pop"], name="降雨機率", marker_color="#60A5FA", width=widths))
    figure.update_yaxes(title="降雨機率 (%)", range=[0, 100])
    return _base_layout(figure, "時段降雨機率")
