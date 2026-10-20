import json
from collections import defaultdict

import plotly.graph_objects as go

# Светлая тема: сетка/оси/ховер подобраны под белый фон карточек.
GRID = "rgba(15,23,42,0.08)"
LINE = "rgba(15,23,42,0.18)"
TICK = dict(color="#64748b", size=10)
CONFIG = {
    "displayModeBar": False,
    "responsive": True,
    "scrollZoom": True,
    "doubleClick": "reset",
}

COLORS = {
    "temp": "#0284c7", "hum": "#ea580c", "p_st": "#7c3aed",
    "wind_avg": "#ca8a04", "wind_dir": "#0891b2",
    "prec": "#059669", "snow": "#64748b", "battery": "#d97706",
}

RUMBES = ["С", "ССВ", "СВ", "ВСВ", "В", "ВЮВ", "ЮВ", "ЮЮВ",
          "Ю", "ЮЮЗ", "ЮЗ", "ЗЮЗ", "З", "ЗСЗ", "СЗ", "ССЗ"]

_PLOT_SPECS = {
    "temperature":    dict(field="air_temperature_average_at_2m",           unit="°C",  dec=1, label="Температура, °C", color=COLORS["temp"],     fill=False),
    "humidity":       dict(field="relative_humidity_average_at_2m",         unit="%",   dec=0, label="Влажность, %",    color=COLORS["hum"],      fill=True,  yrange=[0, 100]),
    "pressure":       dict(field="atmospheric_pressure_average_at_station", unit="гПа", dec=1, label="Давление, гПа",   color=COLORS["p_st"],     fill=False),
    "wind":           dict(field="wind_speed_average_at_10m",               unit="м/с", dec=1, label="Ветер, м/с",      color=COLORS["wind_avg"], fill=False, rangemode="tozero"),
    "wind_direction": dict(field="wind_direction_average_at_10m",           unit="°",   dec=0, label="Направление, °",  color=COLORS["wind_dir"], polar=True),
    "precipitation":  dict(field="precipitation_sum",                       unit="мм",  dec=1, label="Осадки, мм",      color=COLORS["prec"],     bar=True,   rangemode="tozero"),
    "snow":           dict(field="snow_depth_average",                      unit="см",  dec=1, label="Снег, см",        color=COLORS["snow"],     fill=False, rangemode="tozero"),
    "battery":        dict(field="battery_instantaneous_voltage",           unit="В",   dec=1, label="Батарея, В",      color=COLORS["battery"],  fill=True,  rangemode="tozero"),
}


def _axis(title=None, color=None, **extra):
    ax = dict(tickfont=TICK, gridcolor=GRID, zerolinecolor=LINE,
              showline=True, linecolor=LINE)
    if title:
        ax["title"] = dict(text=title, font=dict(color=color or "#64748b", size=10))
    ax.update(extra)
    return ax


def _layout(uirevision=None, **extra):
    base = dict(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Manrope, 'Segoe UI', sans-serif", size=11, color="#334155"),
        margin=dict(l=40, r=10, t=8, b=26),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="#ffffff", bordercolor="#cbd5e1",
                        font=dict(color="#0f172a", size=11)),
        showlegend=False,
        autosize=True,
        dragmode="pan",
    )
    if uirevision is not None:
        base["uirevision"] = uirevision
    base.update(extra)
    return base


def _columns(data):
    s = sorted(data, key=lambda d: d["observation_timestamp"])
    g = lambda d, k: d.get(k)
    out = {"t": [d["observation_timestamp"] for d in s]}
    for name, spec in _PLOT_SPECS.items():
        out[name] = [g(d, spec["field"]) for d in s]
    return out


def _break_circular(x, y):
    xb, yb = [], []
    prev = None
    for xi, yi in zip(x, y):
        if yi is None:
            xb.append(xi); yb.append(None); prev = None
            continue
        if prev is not None and abs(float(yi) - float(prev)) > 180:
            xb.append(xi); yb.append(None)
        xb.append(xi); yb.append(yi)
        prev = yi
    return xb, yb


def _hex_to_rgba(hex_color, alpha):
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def _plot_wind_rose(c):
    """Роза ветров: средняя скорость по 16 румбам."""
    buckets = defaultdict(list)
    # Используем правильные ключи из _columns: wind_direction и wind
    for deg, spd in zip(c["wind_direction"], c["wind"]):
        if deg is None:
            continue
        idx = int(((float(deg) + 11.25) % 360) // 22.5)
        buckets[idx].append(float(spd) if spd is not None else 0.0)

    r = [(sum(buckets[i]) / len(buckets[i]) if buckets[i] else 0) for i in range(16)]

    fig = go.Figure(go.Barpolar(
        r=r, theta=RUMBES, name="Средняя скорость, м/с",
        marker=dict(color="rgba(8,145,178,0.45)", line=dict(color=COLORS["wind_dir"], width=1)),
    ))
    fig.update_layout(_layout(
        showlegend=False,
        margin=dict(l=30, r=30, t=10, b=10),
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            angularaxis=dict(direction="clockwise", rotation=90,
                             tickfont=TICK, gridcolor=GRID, linecolor=LINE),
            radialaxis=dict(tickfont=TICK, gridcolor=GRID, linecolor=LINE,
                            showline=True, rangemode="tozero", visible=False),
        ),
    ))
    return fig


def _build_figure(name, c):
    spec = _PLOT_SPECS[name]
    if spec.get("polar"):
        return _plot_wind_rose(c)

    x = c["t"]
    y = c[name]
    if spec.get("circular"):
        x, y = _break_circular(x, y)

    fig = go.Figure()
    if spec.get("bar"):
        fig.add_trace(go.Bar(
            x=x, y=y, name=spec["label"],
            marker=dict(color=spec["color"], opacity=0.85),
            hovertemplate="%{x|%d.%m %H:%M}<br>%{y:.1f} " + spec["unit"] + "<extra></extra>",
        ))
    else:
        fig.add_trace(go.Scatter(
            x=x, y=y, name=spec["label"], mode="lines",
            line=dict(color=spec["color"], width=2, shape="linear"),
            connectgaps=False,
            fill="tozeroy" if spec.get("fill") else None,
            fillcolor=_hex_to_rgba(spec["color"], 0.10) if spec.get("fill") else None,
            hovertemplate="%{x|%d.%m %H:%M}<br>%{y:.1f} " + spec["unit"] + "<extra></extra>",
        ))

    yaxis = _axis(spec["unit"], spec["color"])
    if spec.get("yrange"):
        yaxis["range"] = spec["yrange"]
    if spec.get("rangemode"):
        yaxis["rangemode"] = spec["rangemode"]

    fig.update_layout(_layout(uirevision=name, yaxis=yaxis,
                              xaxis=_axis(tickformat="%d.%m %H:%M")))
    return fig


def _fig_payload(name, fig):
    payload = json.loads(fig.to_json())
    payload["config"] = CONFIG
    spec = _PLOT_SPECS[name]
    payload["meta"] = {
        "field": spec["field"], "unit": spec["unit"],
        "decimals": spec["dec"], "label": spec["label"],
        "is_bar": bool(spec.get("bar") or spec.get("polar")),
    }
    return payload


def build_plots_payload(data: list[dict]) -> dict:
    if not data:
        return {}
    c = _columns(data)
    return {name: _fig_payload(name, _build_figure(name, c)) for name in _PLOT_SPECS}