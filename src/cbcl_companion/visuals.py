"""Charts and pictograms for the 쉬운 말 해설 tab.

Everything here is drawn from the deterministic facts (rules layer). The model never touches a number
shown in a chart, so the visuals carry the same guarantee as the numbers in the text.
"""
from __future__ import annotations

import altair as alt
import pandas as pd

from .rules import COMPOSITE_CLINICAL, COMPOSITE_SUBCLINICAL, SYNDROME_CLINICAL, SYNDROME_SUBCLINICAL, _PCT_TABLE
from .schema import ScaleFact

BAND_COLORS = {"정상": "#86efac", "준임상": "#fde68a", "임상": "#fca5a5"}
BAND_TEXT = {"정상": "#166534", "준임상": "#854d0e", "임상": "#991b1b"}
T_MIN, T_MAX = 30, 90


def band_chart(scales: list[ScaleFact], kind: str) -> alt.Chart:
    """Horizontal T-score bars over shaded 정상/준임상/임상 bands.

    kind='composite' uses 60/63 thresholds, kind='syndrome' uses 60/70.
    """
    lo, hi = (COMPOSITE_SUBCLINICAL, COMPOSITE_CLINICAL) if kind == "composite" else (SYNDROME_SUBCLINICAL, SYNDROME_CLINICAL)
    df = pd.DataFrame([{"척도": s.label, "T": s.t, "범위": s.band, "base": T_MIN} for s in scales])
    bands = pd.DataFrame([
        {"start": T_MIN, "end": lo, "범위": "정상"},
        {"start": lo, "end": hi, "범위": "준임상"},
        {"start": hi, "end": T_MAX, "범위": "임상"},
    ])
    color = alt.Color("범위:N", scale=alt.Scale(domain=list(BAND_COLORS), range=list(BAND_COLORS.values())),
                      legend=alt.Legend(orient="top", title=None, direction="horizontal"))
    x = alt.X("start:Q", scale=alt.Scale(domain=[T_MIN, T_MAX]), title="T점수 (또래 평균 = 50)")
    bg = alt.Chart(bands).mark_rect(opacity=0.45).encode(x=x, x2="end:Q", color=color)
    mean = alt.Chart(pd.DataFrame({"x": [50]})).mark_rule(strokeDash=[4, 4], color="#6b7280").encode(x="x:Q")
    y = alt.Y("척도:N", sort=None, title=None, scale=alt.Scale(paddingInner=0.35, paddingOuter=0.2),
              axis=alt.Axis(labelFontSize=13, labelLimit=200, labelOverlap=False))
    bars = alt.Chart(df).mark_bar(color="#374151", cornerRadiusEnd=3).encode(y=y, x="base:Q", x2="T:Q")
    text = alt.Chart(df).mark_text(align="left", dx=6, fontWeight="bold", fontSize=13).encode(y=y, x="T:Q", text="T:Q")
    return (alt.layer(bg, mean, bars, text)
            # Streamlit forces autosize=fit unless set; fit collapses band-step heights. fit-x keeps width stretch.
            .properties(height=alt.Step(34), autosize=alt.AutoSizeParams(type="fit-x", contains="padding"))
            .configure_view(strokeWidth=0)
            .configure_axis(grid=False))


def percentile(t: int) -> int:
    """Approximate percentile for a T score (symmetric below 50)."""
    if t >= 50:
        return _PCT_TABLE.get(min(t, 75), 99)
    return max(1, 100 - _PCT_TABLE.get(min(100 - t, 75), 99))


def people_grid_html(scale: ScaleFact) -> str:
    """100 dots = 100 또래. Grey dots score lower than the child, the orange dot is the child."""
    pct = percentile(scale.t)
    dots = []
    for i in range(100):
        if i < pct - 1:
            dots.append('<span class="pg pg-lo"></span>')
        elif i == pct - 1:
            dots.append('<span class="pg pg-me" title="우리 아이"></span>')
        else:
            dots.append('<span class="pg pg-hi"></span>')
    return f"""
<style>
.pgw{{display:grid;grid-template-columns:repeat(20,1fr);gap:4px;max-width:420px;margin:.4em 0 .6em}}
.pg{{display:block;aspect-ratio:1;border-radius:50%}}
.pg-lo{{background:#d1d5db}} .pg-hi{{background:#f3f4f6;border:1px solid #d1d5db}}
.pg-me{{background:#f97316;box-shadow:0 0 0 3px #fed7aa}}
</style>
<div class="pgw">{''.join(dots)}</div>
<p style="margin:0;color:#374151">또래 100명이 한 줄로 섰을 때, <b>{scale.label}</b> 점수는 약 <b>{pct}번째</b>에 있어요.
<span style="color:#9ca3af">(회색 = 우리 아이보다 낮은 또래, 주황 = 우리 아이)</span></p>
"""


def band_badge_html(band: str) -> str:
    return (f'<span style="background:{BAND_COLORS[band]};color:{BAND_TEXT[band]};padding:.15em .6em;'
            f'border-radius:999px;font-weight:600;font-size:.85em">{band} 범위</span>')
