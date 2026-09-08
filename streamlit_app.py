"""
besFundLens web interface.

The engine already answers the question the project exists for: did a fund's
AUM move because markets moved, or because investors added and withdrew money?
Until now that answer only came out as a Markdown file. This puts it on a page
where the whole universe can be seen at once and a single fund can be found in
it.

Run with:  streamlit run streamlit_app.py
"""

import io
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

import besfundlens as bfl

st.set_page_config(page_title="besFundLens", page_icon="🔍", layout="wide")

DEFAULT_DB = "data/besfundlens.sqlite"

# The engine's own presets, ordered from short to long
LOOKBACKS = ["1m", "3m", "6m", "1y"]

LANGUAGES = {"English": "en", "Türkçe": "tr"}

# Columns worth showing by default, in the order they read best
FUND_COLUMNS = [
    "fonKodu",
    "fonUnvan",
    "archetype",
    "end_aum",
    "cumulative_return",
    "aum_change_pct",
    "market_effect_pct",
    "flow_pct",
    "participant_change_pct",
    "end_participants",
    "market_flow_quadrant",
    "flow_regime",
]

PERCENT_COLUMNS = [
    "cumulative_return",
    "aum_change_pct",
    "market_effect_pct",
    "flow_pct",
    "participant_change_pct",
]


@st.cache_data(show_spinner=False)
def load_analysis(db_path, lookback, language, valid_only, classify):
    """
    Run the universe analysis and hand back only the picklable parts.

    Cached on its arguments, so changing a filter in the sidebar does not
    re-read the database and re-run the engine.
    """
    result = bfl.run_universe_analysis_from_sqlite(
        db_path=db_path,
        lookback=lookback,
        language=language,
        valid_only=valid_only,
        classify=classify,
    )
    return (
        result["lens_universe_df"],
        result["market_report"],
        result["markdown"],
        result["lookback_intervals"],
        result.get("classification_df"),
    )


def money(value):
    # AUM figures run to trillions of lira, which is unreadable in full
    value = float(value)
    for limit, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
        if abs(value) >= limit:
            return f"{value / limit:,.2f} {suffix} TL"
    return f"{value:,.0f} TL"


def percent(value):
    return "—" if pd.isna(value) else f"{float(value) * 100:.2f}%"


def quadrant_chart(df):
    """
    Market effect against investor flow, one point per fund.

    The two zero lines split the plane into the quadrants the engine names:
    a fund above the horizontal line took money in, one to the right of the
    vertical line was carried by the market.
    """
    data = df.dropna(subset=["market_effect_pct", "flow_pct"]).copy()
    data["market_effect_display"] = data["market_effect_pct"] * 100
    data["flow_display"] = data["flow_pct"] * 100
    data["aum_display"] = data["end_aum"].fillna(0)

    points = (
        alt.Chart(data)
        .mark_circle(opacity=0.65)
        .encode(
            x=alt.X(
                "market_effect_display:Q",
                title="Market effect (%)",
                scale=alt.Scale(zero=False),
            ),
            y=alt.Y(
                "flow_display:Q",
                title="Estimated investor flow (%)",
                scale=alt.Scale(zero=False),
            ),
            size=alt.Size(
                "aum_display:Q",
                title="AUM",
                scale=alt.Scale(range=[20, 1200]),
                legend=None,
            ),
            color=alt.Color("market_flow_quadrant:N", title="Quadrant"),
            tooltip=[
                alt.Tooltip("fonKodu:N", title="Code"),
                alt.Tooltip("fonUnvan:N", title="Fund"),
                alt.Tooltip("market_effect_display:Q", title="Market effect %", format=".2f"),
                alt.Tooltip("flow_display:Q", title="Flow %", format=".2f"),
                alt.Tooltip("aum_display:Q", title="AUM", format=",.0f"),
                alt.Tooltip("archetype:N", title="Archetype"),
            ],
        )
    )

    zero_x = alt.Chart(pd.DataFrame({"v": [0]})).mark_rule(strokeDash=[4, 4]).encode(x="v:Q")
    zero_y = alt.Chart(pd.DataFrame({"v": [0]})).mark_rule(strokeDash=[4, 4]).encode(y="v:Q")

    return (points + zero_x + zero_y).interactive().properties(height=520)


def summary_table(df, label_column):
    """Format one of the engine's summary frames for display."""
    columns = [
        label_column,
        "fund_count",
        "start_aum_share",
        "weighted_aum_change_pct",
        "weighted_market_effect_pct",
        "weighted_flow_pct",
        "total_net_flow",
    ]
    table = df[[c for c in columns if c in df.columns]].copy()
    return table.sort_values("fund_count", ascending=False)


# ----------------------------------------------------------------- sidebar

st.sidebar.title("🔍 besFundLens")
st.sidebar.caption(bfl.BUILD_VERSION)

db_path = st.sidebar.text_input("SQLite cache", value=DEFAULT_DB)

lookback = st.sidebar.select_slider("Lookback", options=LOOKBACKS, value="1m")

language_name = st.sidebar.radio("Report language", list(LANGUAGES), horizontal=True)
language = LANGUAGES[language_name]

valid_only = st.sidebar.checkbox(
    "Valid universe records only",
    value=True,
    help="Drops funds whose history does not cover the whole lookback window.",
)

classify = st.sidebar.checkbox(
    "Run allocation classification",
    value=False,
    help="Fits the v2 clustering model over the window. Slower, and only needed for the Classification tab.",
)

if not Path(db_path).exists():
    st.warning(
        f"No SQLite cache at `{db_path}`.\n\n"
        "Build one first:\n\n"
        "```bash\n"
        "python scripts/fetch_history.py --start 2021-06-15 --end 2026-06-15 "
        "--db-path data/besfundlens.sqlite\n"
        "```"
    )
    st.stop()

# ----------------------------------------------------------------- analysis

with st.spinner(f"Running the {lookback} analysis"):
    universe, market_report, markdown, intervals, classification = load_analysis(
        db_path, lookback, language, valid_only, classify
    )

summary = market_report["universe_summary"]

st.title("Did the market move it, or did investors?")
st.caption(
    f"{int(summary['fund_count']):,} funds · {lookback} lookback "
    f"({intervals} trading intervals) · "
    f"{universe['start_date'].max():%Y-%m-%d} to {universe['end_date'].max():%Y-%m-%d}"
)

kpi = st.columns(5)
kpi[0].metric("End AUM", money(summary["total_end_aum"]))
kpi[1].metric(
    "AUM change",
    percent(summary["total_end_aum"] / summary["total_start_aum"] - 1),
)
kpi[2].metric("Market effect", money(summary["total_market_effect"]))
kpi[3].metric("Net investor flow", money(summary["total_net_flow"]))
kpi[4].metric(
    "Flow as % of start AUM",
    percent(summary["total_net_flow"] / summary["total_start_aum"]),
)

market_tab, funds_tab, report_tab = st.tabs(["Market map", "Funds", "Report"])

# ----------------------------------------------------------------- market

with market_tab:
    st.altair_chart(quadrant_chart(universe), use_container_width=True)
    st.caption(
        "Each circle is a fund, sized by AUM. Right of the vertical line the market "
        "lifted it; above the horizontal line investors put money in. The interesting "
        "funds are the ones off the diagonal — growing on flows while the market fell, "
        "or losing investors through a rally."
    )

    left, right = st.columns(2)
    with left:
        st.subheader("By quadrant")
        st.dataframe(
            summary_table(market_report["quadrant_summary"], "market_flow_quadrant"),
            use_container_width=True,
            hide_index=True,
        )
    with right:
        st.subheader("By archetype")
        st.dataframe(
            summary_table(market_report["archetype_summary"], "archetype"),
            use_container_width=True,
            hide_index=True,
        )

# ----------------------------------------------------------------- funds

with funds_tab:
    filters = st.columns([2, 2, 3])

    archetypes = sorted(universe["archetype"].dropna().unique())
    chosen_archetypes = filters[0].multiselect("Archetype", archetypes)

    quadrants = sorted(universe["market_flow_quadrant"].dropna().unique())
    chosen_quadrants = filters[1].multiselect("Quadrant", quadrants)

    search = filters[2].text_input("Search code or name")

    view = universe.copy()
    if chosen_archetypes:
        view = view[view["archetype"].isin(chosen_archetypes)]
    if chosen_quadrants:
        view = view[view["market_flow_quadrant"].isin(chosen_quadrants)]
    if search:
        pattern = search.strip()
        view = view[
            view["fonKodu"].str.contains(pattern, case=False, na=False)
            | view["fonUnvan"].str.contains(pattern, case=False, na=False)
        ]

    st.caption(f"{len(view):,} of {len(universe):,} funds")

    st.dataframe(
        view[[c for c in FUND_COLUMNS if c in view.columns]],
        use_container_width=True,
        hide_index=True,
        height=560,
        column_config={
            "fonKodu": st.column_config.TextColumn("Code", width="small"),
            "fonUnvan": st.column_config.TextColumn("Fund", width="large"),
            "archetype": st.column_config.TextColumn("Archetype"),
            "end_aum": st.column_config.NumberColumn("AUM", format="%,.0f"),
            "end_participants": st.column_config.NumberColumn("Participants", format="%,.0f"),
            "market_flow_quadrant": st.column_config.TextColumn("Quadrant"),
            "flow_regime": st.column_config.TextColumn("Flow regime"),
            **{
                column: st.column_config.NumberColumn(
                    column.replace("_pct", "").replace("_", " ").capitalize() + " %",
                    format="percent",
                )
                for column in PERCENT_COLUMNS
                if column in view.columns
            },
        },
    )

    st.download_button(
        "Download this view as CSV",
        view.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"besfundlens_{lookback}.csv",
        mime="text/csv",
    )

# ----------------------------------------------------------------- report

with report_tab:
    st.download_button(
        "Download the report as Markdown",
        markdown.encode("utf-8"),
        file_name=f"besfundlens_report_{language}_{lookback}.md",
        mime="text/markdown",
    )
    st.markdown(markdown)
