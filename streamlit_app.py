"""
besFundLens web interface.

The engine already answers the question the project exists for: did a fund's
AUM move because markets moved, or because investors added and withdrew money?
Until now that answer only came out as a Markdown file. This puts it on a page
where the whole universe can be seen at once and a single fund can be found in
it.

Run with:  streamlit run streamlit_app.py
"""

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

import besfundlens as bfl
from besfundlens.core.engine import report_label
from besfundlens.data.loaders import load_data

from app_translations import LANGUAGES, MONTHS, UI

st.set_page_config(page_title="besFundLens", page_icon="🔍", layout="wide")

DEFAULT_DB = "data/besfundlens.sqlite"

# The engine's own presets, ordered from short to long
LOOKBACKS = ["1m", "3m", "6m", "1y"]

# How much calendar history to pull for each lookback. A little more than the
# window itself, because the engine counts trading days and needs the window
# fully covered before it will call a record valid.
FETCH_MONTHS = {"1m": 1, "3m": 3, "6m": 6, "1y": 12}

# Measured against the live API: three months of EMK took 15 seconds over four
# chunked requests. TEFAS caps a request at about a month and answers with an
# empty result rather than an error when asked for more, or when asked too
# quickly, so the client chunks and paces itself and the wait grows with range.
FETCH_SECONDS = {"1m": 10, "3m": 15, "6m": 30, "1y": 60}

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


# ------------------------------------------------------------------ language

st.sidebar.title("🔍 besFundLens")
st.sidebar.caption(bfl.BUILD_VERSION)

# Streamlit has written the new choice into session state before this reruns,
# so the selector's own label can be shown in the language being switched to.
current = st.session_state.get("language", "en")

language = st.sidebar.radio(
    "🌐 " + UI[current]["language"],
    list(LANGUAGES),
    format_func=lambda code: f"{LANGUAGES[code][0]} {LANGUAGES[code][1]}",
    key="language",
    horizontal=True,
)


def t(key, **kwargs):
    """Interface string, falling back to English if a translation is missing."""
    text = UI[language].get(key) or UI["en"][key]
    return text.format(**kwargs) if kwargs else text


def label(key):
    """
    A term the generated report also uses.

    Read from the engine rather than restated here, so the page and the report
    call the same thing by the same name.
    """
    return report_label(key, language).lstrip("# ")


def format_date(timestamp):
    """A date written the way the chosen language writes it, not the C locale."""
    return f"{timestamp.day:02d} {MONTHS[language][timestamp.month - 1]} {timestamp.year}"


def months_text(lookback):
    count = FETCH_MONTHS[lookback]
    return t("months_one") if count == 1 else t("months_many", n=count)


# ------------------------------------------------------------------ analysis


def pack(result):
    """Keep only the picklable parts of an analysis, so it can be cached."""
    return (
        result["lens_universe_df"],
        result["market_report"],
        result["markdown"],
        result["lookback_intervals"],
    )


@st.cache_data(show_spinner=False, ttl=6 * 60 * 60)
def analyse_live(lookback, language, valid_only):
    """
    Fetch the window straight from TEFAS, then analyse it.

    There is no stored database behind this. The cost is one fetch per lookback
    per boot, which the six hour cache holds on to, and in exchange whoever
    opens the page gets the latest published day rather than whatever was in a
    snapshot when it was built.
    """
    end = pd.Timestamp.today().normalize()
    start = end - pd.DateOffset(months=FETCH_MONTHS[lookback]) - pd.Timedelta(days=10)

    df_general, df_allocation = load_data(
        source="api", start_date=start, end_date=end, verbose=False
    )
    if df_general.empty or df_allocation.empty:
        return None

    return pack(
        bfl.run_universe_analysis_from_dataframes(
            df_general,
            df_allocation,
            lookback=lookback,
            valid_only=valid_only,
            language=language,
        )
    )


@st.cache_data(show_spinner=False)
def analyse_cache(db_path, lookback, language, valid_only):
    """Analyse a local SQLite cache, which can hold far more history."""
    return pack(
        bfl.run_universe_analysis_from_sqlite(
            db_path=db_path,
            lookback=lookback,
            language=language,
            valid_only=valid_only,
            classify=False,
        )
    )


def localize(universe, market_report, language):
    """
    Translate the labels the engine leaves in English.

    ``language`` reaches the Markdown report but not the frame, so archetype,
    quadrant and regime arrive in English however the report was written. They
    are translated here rather than at read time so that the filters, the chart
    legend and the table all agree.
    """
    if language == "en":
        return universe, market_report

    universe = universe.copy()
    universe["archetype"] = universe["archetype"].map(
        lambda v: bfl.translate_archetype(v, language)
    )
    universe["flow_regime"] = universe["flow_regime"].map(
        lambda v: bfl.translate_flow_regime(v, language)
    )
    universe["market_flow_quadrant"] = universe["market_flow_quadrant"].map(
        lambda v: bfl.translate_quadrant_name(v, language)
    )

    market_report = dict(market_report)
    for key, column, translate in (
        ("quadrant_summary", "market_flow_quadrant", bfl.translate_quadrant_name),
        ("archetype_summary", "archetype", bfl.translate_archetype),
    ):
        table = market_report[key].copy()
        table[column] = table[column].map(lambda v: translate(v, language))
        market_report[key] = table

    return universe, market_report


# ------------------------------------------------------------------ helpers


def money(value):
    # AUM figures run to trillions of lira, which is unreadable in full
    value = float(value)
    for limit, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
        if abs(value) >= limit:
            return f"{value / limit:,.2f} {suffix} TL"
    return f"{value:,.0f} TL"


def percent(value):
    """For the _pct columns, which the engine stores as decimals."""
    return "—" if pd.isna(value) else f"{float(value) * 100:.2f}%"


def weight(value):
    """
    For the DNA weight columns, which the engine already stores as percentages.

    lens_universe_df mixes the two conventions: flow_pct is 0.0027 while
    top_asset_weight is 56.17. Running the second through percent() gives 5617%.
    """
    return "—" if pd.isna(value) else f"{float(value):.2f}%"


def axis_limits(series, lower=0.01, upper=0.99, pad=0.1):
    """
    A range that holds the bulk of the values.

    A handful of small funds post flows of several hundred percent, and letting
    them set the axis squeezes everyone else onto a line through zero. The
    outliers stay in the data and can be panned to, they just do not get to
    decide the default view.
    """
    low, high = series.quantile(lower), series.quantile(upper)
    if not pd.notna(low) or not pd.notna(high) or low == high:
        return None
    margin = (high - low) * pad
    return [float(low - margin), float(high + margin)]


def quadrant_chart(df, zoom_to_bulk=True):
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

    x_limits = axis_limits(data["market_effect_display"]) if zoom_to_bulk else None
    y_limits = axis_limits(data["flow_display"]) if zoom_to_bulk else None

    x_scale = alt.Scale(zero=False, domain=x_limits, clamp=True) if x_limits else alt.Scale(zero=False)
    y_scale = alt.Scale(zero=False, domain=y_limits, clamp=True) if y_limits else alt.Scale(zero=False)

    points = (
        alt.Chart(data)
        .mark_circle(opacity=0.65)
        .encode(
            x=alt.X("market_effect_display:Q", title=t("axis_market"), scale=x_scale),
            y=alt.Y("flow_display:Q", title=t("axis_flow"), scale=y_scale),
            size=alt.Size(
                "aum_display:Q",
                title=t("col_aum"),
                scale=alt.Scale(range=[20, 1200]),
                legend=None,
            ),
            color=alt.Color("market_flow_quadrant:N", title=label("quadrant")),
            tooltip=[
                alt.Tooltip("fonKodu:N", title=t("col_code")),
                alt.Tooltip("fonUnvan:N", title=label("fund")),
                alt.Tooltip("market_effect_display:Q", title=t("col_market_effect"), format=".2f"),
                alt.Tooltip("flow_display:Q", title=t("col_flow"), format=".2f"),
                alt.Tooltip("aum_display:Q", title=t("col_aum"), format=",.0f"),
                alt.Tooltip("archetype:N", title=label("archetype")),
            ],
        )
    )

    zero_x = alt.Chart(pd.DataFrame({"v": [0]})).mark_rule(strokeDash=[4, 4]).encode(x="v:Q")
    zero_y = alt.Chart(pd.DataFrame({"v": [0]})).mark_rule(strokeDash=[4, 4]).encode(y="v:Q")

    return (points + zero_x + zero_y).interactive().properties(height=520)


def decomposition_chart(fund):
    """
    The two forces behind one fund's AUM change, in lira.

    This is the project's whole argument narrowed to a single fund: the bar on
    the left is what the market did to the money already there, the one on the
    right is what investors put in or took out.
    """
    data = pd.DataFrame(
        {
            "part": [t("bar_market_effect"), t("bar_flow")],
            "value": [
                float(fund["total_market_effect"] or 0),
                float(fund["total_net_flow"] or 0),
            ],
        }
    )
    data["sign"] = data["value"].map(lambda v: "+" if v >= 0 else "-")

    bars = (
        alt.Chart(data)
        .mark_bar()
        .encode(
            x=alt.X("value:Q", title="TL"),
            y=alt.Y("part:N", title=None, sort=None),
            color=alt.Color(
                "sign:N",
                scale=alt.Scale(domain=["+", "-"], range=["#2e9e83", "#d1495b"]),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("part:N", title=""),
                alt.Tooltip("value:Q", title="TL", format=",.0f"),
            ],
        )
    )
    zero = alt.Chart(pd.DataFrame({"v": [0]})).mark_rule(color="#888").encode(x="v:Q")
    return (bars + zero).properties(height=140)


def universe_with_highlight(df, fund_code):
    """The universe scatter with one fund ringed and the rest faded back."""
    data = df.dropna(subset=["market_effect_pct", "flow_pct"]).copy()
    data["market_effect_display"] = data["market_effect_pct"] * 100
    data["flow_display"] = data["flow_pct"] * 100

    x_limits = axis_limits(data["market_effect_display"])
    y_limits = axis_limits(data["flow_display"])
    x_scale = alt.Scale(zero=False, domain=x_limits, clamp=True) if x_limits else alt.Scale(zero=False)
    y_scale = alt.Scale(zero=False, domain=y_limits, clamp=True) if y_limits else alt.Scale(zero=False)

    base = alt.Chart(data).encode(
        x=alt.X("market_effect_display:Q", title=t("axis_market"), scale=x_scale),
        y=alt.Y("flow_display:Q", title=t("axis_flow"), scale=y_scale),
    )

    others = base.transform_filter(alt.datum.fonKodu != fund_code).mark_circle(
        opacity=0.18, color="#9aa0a6", size=45
    )
    chosen = base.transform_filter(alt.datum.fonKodu == fund_code).mark_point(
        size=260, filled=True, opacity=0.95, color="#d1495b", stroke="#000", strokeWidth=1
    ).encode(
        tooltip=[
            alt.Tooltip("fonKodu:N", title=t("col_code")),
            alt.Tooltip("market_effect_display:Q", title=t("col_market_effect"), format=".2f"),
            alt.Tooltip("flow_display:Q", title=t("col_flow"), format=".2f"),
        ]
    )

    zero_x = alt.Chart(pd.DataFrame({"v": [0]})).mark_rule(strokeDash=[4, 4]).encode(x="v:Q")
    zero_y = alt.Chart(pd.DataFrame({"v": [0]})).mark_rule(strokeDash=[4, 4]).encode(y="v:Q")

    return (others + zero_x + zero_y + chosen).properties(height=420)


def summary_table(df, label_column, heading):
    """Format one of the engine's summary frames for display."""
    columns = {
        label_column: heading,
        "fund_count": label("fund_count"),
        "start_aum_share": label("aum_share"),
        "weighted_aum_change_pct": label("aum_change"),
        "weighted_market_effect_pct": label("market_effect"),
        "weighted_flow_pct": label("weighted_flow"),
        "total_net_flow": label("total_net_flow"),
    }
    present = [c for c in columns if c in df.columns]
    return df[present].sort_values("fund_count", ascending=False).rename(columns=columns)


# ------------------------------------------------------------------ sidebar

source = st.sidebar.radio(
    t("data"),
    [t("source_live"), t("source_cache")],
    help=t("source_help"),
)
live = source == t("source_live")

db_path = DEFAULT_DB
if not live:
    db_path = st.sidebar.text_input(t("cache_path"), value=DEFAULT_DB)

lookback = st.sidebar.select_slider(t("lookback"), options=LOOKBACKS, value="1m")

if live:
    st.sidebar.caption(
        t("fetch_estimate", months=months_text(lookback), seconds=FETCH_SECONDS[lookback])
    )

valid_only = st.sidebar.checkbox(
    t("valid_only"), value=True, help=t("valid_only_help")
)

st.sidebar.divider()
st.sidebar.markdown(
    f"**{t('deeper_title')}**\n\n"
    f"{t('deeper_body')}\n\n"
    "```bash\n"
    "python scripts/fetch_history.py \\\n"
    "  --start 2021-06-15 --end 2026-06-15 \\\n"
    "  --db-path data/besfundlens.sqlite\n"
    "```\n\n"
    f"{t('deeper_turkeyfundsdata')}"
)

if not live and not Path(db_path).exists():
    st.warning(t("no_cache", path=db_path, live=t("source_live")))
    st.stop()

# ------------------------------------------------------------------ run

spinner_text = (
    t("spinner_live", months=months_text(lookback), seconds=FETCH_SECONDS[lookback])
    if live
    else t("spinner_cache", lookback=lookback)
)

with st.spinner(spinner_text):
    analysis = (
        analyse_live(lookback, language, valid_only)
        if live
        else analyse_cache(db_path, lookback, language, valid_only)
    )

if analysis is None:
    st.error(t("empty_response"))
    st.stop()

universe, market_report, markdown, intervals = analysis
universe, market_report = localize(universe, market_report, language)
summary = market_report["universe_summary"]

# ------------------------------------------------------------------ header

last_date = format_date(universe["end_date"].max())
first_date = format_date(universe["start_date"].max())
fund_count = f"{int(summary['fund_count']):,}"

st.title(t("title"))
st.caption(
    "**" + t("data_through", date=last_date) + "** "
    + f"({t('via_live') if live else t('via_cache')}) · "
    + t("funds_count", n=fund_count) + " · "
    + t("window", lookback=lookback, intervals=intervals, date=first_date)
)

kpi = st.columns(5)
kpi[0].metric(t("kpi_end_aum"), money(summary["total_end_aum"]))
kpi[1].metric(
    label("aum_change"),
    percent(summary["total_end_aum"] / summary["total_start_aum"] - 1),
)
kpi[2].metric(label("market_effect"), money(summary["total_market_effect"]))
kpi[3].metric(label("total_net_flow"), money(summary["total_net_flow"]))
kpi[4].metric(
    t("kpi_flow_share"),
    percent(summary["total_net_flow"] / summary["total_start_aum"]),
)

# A dataframe mounted inside a hidden st.tabs pane measures itself at zero width
# and paints only its first column, so the views are switched with a control that
# renders one at a time. It also keeps the report markdown from being built on
# every run when nobody is looking at it.
# Selected by a stable key rather than by its translated label, so switching
# language keeps you on the view you were reading.
# The chosen view is remembered outside the widget. Keying the widget itself
# was not enough: changing language re-renders it and it comes back with
# nothing selected, which used to drop you back on the market map.
VIEWS = ["market", "funds", "detail", "report"]
remembered = st.session_state.get("last_view", "market")

selected = st.segmented_control(
    "View",
    VIEWS,
    default=remembered,
    format_func=lambda name: t(f"view_{name}"),
    label_visibility="collapsed",
)

view = selected or remembered
st.session_state["last_view"] = view

# ------------------------------------------------------------------ market

if view == "market":
    zoom_to_bulk = st.checkbox(t("zoom"), value=True, help=t("zoom_help"))

    st.altair_chart(quadrant_chart(universe, zoom_to_bulk))

    caption = t("chart_caption")
    if zoom_to_bulk:
        plotted = universe.dropna(subset=["market_effect_pct", "flow_pct"])
        x_range = axis_limits(plotted["market_effect_pct"] * 100)
        y_range = axis_limits(plotted["flow_pct"] * 100)
        if x_range and y_range:
            outside = (
                ~(plotted["market_effect_pct"] * 100).between(*x_range)
                | ~(plotted["flow_pct"] * 100).between(*y_range)
            ).sum()
            if outside:
                caption += " " + t("chart_outliers", n=outside)
    st.caption(caption)

    left, right = st.columns(2)
    with left:
        st.subheader(t("by_quadrant"))
        st.dataframe(
            summary_table(market_report["quadrant_summary"], "market_flow_quadrant", label("quadrant")),
            hide_index=True,
        )
    with right:
        st.subheader(t("by_archetype"))
        st.dataframe(
            summary_table(market_report["archetype_summary"], "archetype", label("archetype")),
            hide_index=True,
        )

# ------------------------------------------------------------------ funds

if view == "funds":
    filters = st.columns([2, 2, 3])

    archetypes = sorted(universe["archetype"].dropna().unique())
    chosen_archetypes = filters[0].multiselect(label("archetype"), archetypes)

    quadrants = sorted(universe["market_flow_quadrant"].dropna().unique())
    chosen_quadrants = filters[1].multiselect(label("quadrant"), quadrants)

    search = filters[2].text_input(t("filter_search"))

    view_df = universe.copy()
    if chosen_archetypes:
        view_df = view_df[view_df["archetype"].isin(chosen_archetypes)]
    if chosen_quadrants:
        view_df = view_df[view_df["market_flow_quadrant"].isin(chosen_quadrants)]
    if search:
        pattern = search.strip()
        view_df = view_df[
            view_df["fonKodu"].str.contains(pattern, case=False, na=False)
            | view_df["fonUnvan"].str.contains(pattern, case=False, na=False)
        ]

    st.caption(t("showing", shown=f"{len(view_df):,}", total=f"{len(universe):,}"))

    st.dataframe(
        view_df[[c for c in FUND_COLUMNS if c in view_df.columns]],
        hide_index=True,
        height=560,
        column_config={
            "fonKodu": st.column_config.TextColumn(t("col_code"), width="small"),
            "fonUnvan": st.column_config.TextColumn(label("fund"), width="large"),
            "archetype": st.column_config.TextColumn(label("archetype")),
            "end_aum": st.column_config.NumberColumn(t("col_aum"), format="compact"),
            "end_participants": st.column_config.NumberColumn(t("col_participants"), format="localized"),
            "market_flow_quadrant": st.column_config.TextColumn(t("col_quadrant")),
            "flow_regime": st.column_config.TextColumn(t("col_regime")),
            "cumulative_return": st.column_config.NumberColumn(t("col_return"), format="percent"),
            "aum_change_pct": st.column_config.NumberColumn(t("col_aum_change"), format="percent"),
            "market_effect_pct": st.column_config.NumberColumn(t("col_market_effect"), format="percent"),
            "flow_pct": st.column_config.NumberColumn(t("col_flow"), format="percent"),
            "participant_change_pct": st.column_config.NumberColumn(t("col_participant_change"), format="percent"),
        },
    )

    st.download_button(
        t("download_csv"),
        view_df.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"besfundlens_{lookback}_{language}.csv",
        mime="text/csv",
    )

# ------------------------------------------------------------------ fund detail

if view == "detail":
    options = universe.sort_values("fonKodu")["fonKodu"].tolist()
    names = universe.set_index("fonKodu")["fonUnvan"].to_dict()

    code = st.selectbox(
        t("pick_fund"),
        options,
        format_func=lambda c: f"{c} — {names.get(c, '')}",
    )
    fund = universe[universe["fonKodu"] == code].iloc[0]

    st.subheader(fund["fonUnvan"])
    st.caption(f"{fund['archetype']} · {fund['market_flow_quadrant']} · {fund['flow_regime']}")

    top = st.columns(5)
    top[0].metric(t("detail_start_aum"), money(fund["start_aum"]))
    top[1].metric(t("kpi_end_aum"), money(fund["end_aum"]))
    top[2].metric(label("return"), percent(fund["cumulative_return"]))
    top[3].metric(t("detail_participants"), f"{int(fund['end_participants']):,}")
    top[4].metric(
        t("detail_participant_change"),
        percent(fund["participant_change_pct"]),
        delta=f"{int(fund['participant_change']):,}",
    )

    left, right = st.columns([3, 2])

    with left:
        st.markdown(f"**{t('detail_what_moved')}**")
        st.altair_chart(decomposition_chart(fund))

        parts = st.columns(3)
        parts[0].metric(label("aum_change"), percent(fund["aum_change_pct"]))
        parts[1].metric(label("market_effect"), percent(fund["market_effect_pct"]))
        parts[2].metric(label("flow"), percent(fund["flow_pct"]))
        st.caption(t("detail_decomp_note"))

    with right:
        st.markdown(f"**{t('detail_dna')}**")
        dna = pd.DataFrame(
            {
                " ": [
                    t("detail_top_asset"),
                    t("detail_scope"),
                    t("detail_currency"),
                    t("detail_lookthrough"),
                ],
                "  ": [
                    f"{bfl.translate_asset_group(fund['top_asset_group'], language)} "
                    f"— {weight(fund['top_asset_weight'])}",
                    f"{bfl.translate_market_scope(fund['top_scope'], language)} "
                    f"— {weight(fund['top_scope_weight'])}",
                    f"{bfl.translate_currency_exposure(fund['top_currency'], language)} "
                    f"— {weight(fund['top_currency_weight'])}",
                    weight(fund["lookthrough_weight"]),
                ],
            }
        )
        st.dataframe(dna, hide_index=True)
        st.caption(t("detail_lookthrough_help"))

    st.markdown(f"**{t('detail_position')}**")
    st.altair_chart(universe_with_highlight(universe, code))
    st.caption(t("detail_highlighted"))


# ------------------------------------------------------------------ report

if view == "report":
    st.download_button(
        t("download_report"),
        markdown.encode("utf-8"),
        file_name=f"besfundlens_report_{language}_{lookback}.md",
        mime="text/markdown",
    )
    st.markdown(markdown)
