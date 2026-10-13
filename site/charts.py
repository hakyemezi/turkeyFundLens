"""
Charts as plain inline SVG.

The pages used to carry Vega-Lite specs and load about a megabyte of script to
draw twenty bars. These are drawn when the site is built instead: no script,
nothing to wait for, and a crawler reads what a visitor sees. Colours come from
the page's stylesheet through class names, so the charts follow the light and
dark themes without knowing about either.

Only dates and numbers go into the markup, never a fund's name, so nothing here
needs escaping.
"""

from __future__ import annotations

import math

import pandas as pd

WIDTH, HEIGHT = 720, 240
LEFT, RIGHT, BOTTOM = 50, 12, 26


def _tr(value: float, digits: int = 1) -> str:
    """A number the Turkish way: decimal comma, proper minus sign."""
    text = f"{abs(value):.{digits}f}".replace(".", ",")
    return f"−{text}" if value < 0 else text


def nice_ticks(low: float, high: float, target: int = 4) -> list[float]:
    """Round tick values covering low..high, about ``target`` of them."""
    span = high - low
    if span <= 0:
        return [low]
    raw = span / target
    magnitude = 10 ** math.floor(math.log10(raw))
    step = next(m * magnitude for m in (1, 2, 2.5, 5, 10) if m * magnitude >= raw)
    first = math.ceil(low / step) * step
    ticks = []
    value = first
    while value <= high + step * 1e-9:
        ticks.append(round(value, 10))
        value += step
    return ticks


class _Frame:
    """The shared geometry: a band per day across, a linear scale up."""

    def __init__(self, dates, low: float, high: float, top: int):
        self.dates = [pd.Timestamp(d) for d in dates]
        self.top = top
        pad = (high - low) * 0.08 or 1.0
        self.low, self.high = low - (pad if low < 0 else 0), high + (pad if high > 0 else 0)
        if self.low == self.high:
            self.high = self.low + 1.0
        self.plot_w = WIDTH - LEFT - RIGHT
        self.plot_h = HEIGHT - top - BOTTOM
        self.band = self.plot_w / max(len(self.dates), 1)

    def x(self, i: int) -> float:
        return LEFT + (i + 0.5) * self.band

    def y(self, value: float) -> float:
        return self.top + (self.high - value) / (self.high - self.low) * self.plot_h

    def axes(self, y_title: str, digits: int) -> list[str]:
        out = []
        for tick in nice_ticks(self.low, self.high):
            y = self.y(tick)
            css = "zero" if tick == 0 else "grid"
            out.append(f'<line class="{css}" x1="{LEFT}" x2="{WIDTH - RIGHT}" y1="{y:.1f}" y2="{y:.1f}"/>')
            out.append(f'<text class="ax" x="{LEFT - 6}" y="{y + 3.5:.1f}" text-anchor="end">{_tr(tick, digits)}</text>')
        step = max(1, math.ceil(len(self.dates) / 8))
        for i, date in enumerate(self.dates):
            if i % step == 0:
                out.append(
                    f'<text class="ax" x="{self.x(i):.1f}" y="{HEIGHT - 8}" text-anchor="middle">'
                    f"{date:%d.%m}</text>"
                )
        out.append(
            f'<text class="ax" transform="translate(12 {self.top + self.plot_h / 2:.0f}) rotate(-90)" '
            f'text-anchor="middle">{y_title}</text>'
        )
        return out

    def event(self, event) -> list[str]:
        """A dashed line on the event day, if it falls inside the chart."""
        if event is None:
            return []
        event = pd.Timestamp(event)
        for i, date in enumerate(self.dates):
            if date >= event:
                x = self.x(i)
                return [f'<line class="ev" x1="{x:.1f}" x2="{x:.1f}" y1="{self.top}" y2="{self.top + self.plot_h}"/>']
        return []


def _svg(parts: list[str], label: str) -> str:
    return (
        f'<svg viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-label="{label}" '
        f'xmlns="http://www.w3.org/2000/svg">' + "".join(parts) + "</svg>"
    )


def bar_chart(dates, values, event=None, y_title: str = "", label: str = "") -> str:
    """One bar per day, up for positive and down for negative, in percent."""
    values = [float(v) for v in values]
    if not values:
        return ""
    frame = _Frame(dates, min(0.0, min(values)), max(0.0, max(values)), top=12)
    parts = frame.axes(y_title, digits=0 if max(abs(v) for v in values) >= 10 else 1)
    width = frame.band * 0.7
    zero = frame.y(0)
    for i, (date, value) in enumerate(zip(frame.dates, values)):
        y = frame.y(value)
        top, height = (y, zero - y) if value >= 0 else (zero, y - zero)
        parts.append(
            f'<rect class="{"pos" if value >= 0 else "neg"}" x="{frame.x(i) - width / 2:.1f}" '
            f'y="{top:.1f}" width="{width:.1f}" height="{max(height, 0.6):.1f}">'
            f"<title>{date:%d.%m.%Y}: %{_tr(value, 2)}</title></rect>"
        )
    parts += frame.event(event)
    return _svg(parts, label)


def line_chart(dates, series: dict, event=None, y_title: str = "", label: str = "") -> str:
    """One line per named series, with a legend along the top."""
    names = list(series)
    columns = [[float(v) for v in series[name]] for name in names]
    flat = [v for column in columns for v in column]
    if not flat:
        return ""
    frame = _Frame(dates, min(0.0, min(flat)), max(flat), top=30)
    parts = frame.axes(y_title, digits=0)
    legend_x = LEFT
    for k, (name, column) in enumerate(zip(names, columns)):
        points = " ".join(f"{frame.x(i):.1f},{frame.y(v):.1f}" for i, v in enumerate(column))
        parts.append(f'<polyline class="s{k}" points="{points}"/>')
        for i, (date, value) in enumerate(zip(frame.dates, column)):
            parts.append(
                f'<circle class="s{k}d" cx="{frame.x(i):.1f}" cy="{frame.y(value):.1f}" r="2.6">'
                f"<title>{date:%d.%m.%Y} — {name}: %{_tr(value, 1)}</title></circle>"
            )
        parts.append(f'<rect class="s{k}d" x="{legend_x}" y="6" width="10" height="10" rx="2"/>')
        parts.append(f'<text class="ax" x="{legend_x + 15}" y="15">{name}</text>')
        legend_x += 30 + len(name) * 6.2
    parts += frame.event(event)
    return _svg(parts, label)
