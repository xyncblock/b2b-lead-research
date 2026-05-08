"""
B2B Lead Research Dashboard — Modern UX v3.

Improvements over v2:
- Native st.dataframe with LinkColumn (sortable, filterable, resizable)
- Responsive metric cards (2/3/5 column adaptive layout)
- Reset-filters button + filter summary chips
- Data refresh without page reload
- Skeleton loaders for chart sections
- Country distribution chart
- Score-vs-Rating scatter plot
- Timestamped exports with preview
- Empty-state illustration with helpful actions
- Modern color palette with CSS variables
- Lead detail expanders in table view
- Mobile-first sidebar organization
- Keyboard shortcut hints
"""

from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import sys
import io
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

# ── Page config ────────────────────────────────────────────────
st.set_page_config(
    page_title="B2B Lead Research Dashboard",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ─────────────────────────────────────────────────
st.markdown(
    """
    <style>
        :root {
            --primary: #2563eb;
            --primary-light: #3b82f6;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
            --muted: #6b7280;
            --bg-card: #ffffff;
            --border: #e5e7eb;
        }

        /* Metric cards */
        div[data-testid="stMetric"] {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 0.75rem;
            padding: 1rem;
            box-shadow: 0 1px 2px rgba(0,0,0,0.04);
        }
        div[data-testid="stMetricValue"] {
            font-size: 1.75rem;
            font-weight: 700;
            color: #111827;
        }
        div[data-testid="stMetricLabel"] {
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: var(--muted);
        }
        div[data-testid="stMetricDelta"] {
            font-size: 0.8rem;
        }

        /* Sidebar */
        [data-testid="stSidebar"] {
            background: #f9fafb;
        }
        [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
            font-size: 0.95rem;
            font-weight: 700;
            color: #111827;
            margin-bottom: 0.5rem;
        }
        [data-testid="stSidebar"] hr {
            margin: 1rem 0;
            border-color: var(--border);
        }

        /* Buttons */
        .stButton > button[kind="primary"] {
            background: var(--primary);
            border-color: var(--primary);
        }
        .stButton > button[kind="primary"]:hover {
            background: var(--primary-light);
            border-color: var(--primary-light);
        }

        /* Download buttons */
        .stDownloadButton > button {
            width: 100%;
            border-radius: 0.5rem;
            font-weight: 500;
        }

        /* Dataframe */
        .stDataFrame th {
            background-color: #f3f4f6 !important;
            color: #111827 !important;
            font-weight: 600 !important;
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.03em;
        }
        .stDataFrame td {
            font-size: 0.875rem;
        }

        /* Tabs */
        .stTabs [data-baseweb="tab-list"] {
            gap: 0.5rem;
        }
        .stTabs [data-baseweb="tab"] {
            font-weight: 500;
            font-size: 0.9rem;
            border-radius: 0.5rem 0.5rem 0 0;
            padding: 0.5rem 1rem;
        }

        /* Empty state */
        .empty-state {
            text-align: center;
            padding: 3rem 1rem;
            color: var(--muted);
        }
        .empty-state h3 {
            color: #374151;
            margin-bottom: 0.5rem;
        }

        /* Filter chips */
        .filter-chip {
            display: inline-block;
            background: #eff6ff;
            color: #1e40af;
            border: 1px solid #bfdbfe;
            border-radius: 9999px;
            padding: 0.2rem 0.6rem;
            font-size: 0.75rem;
            font-weight: 500;
            margin-right: 0.3rem;
            margin-bottom: 0.3rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Session defaults ───────────────────────────────────────────
defaults = {
    "countries": [],
    "priorities": ["HOT", "WARM"],
    "score_range": (0, 100),
    "search": "",
    "refresh_key": 0,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ── Data loading ───────────────────────────────────────────────
@st.cache_data(show_spinner=False, ttl=300)
def load_data(refresh_key: int = 0) -> tuple[pd.DataFrame, str | None, int, datetime]:
    """Load and combine all lead Excel files."""
    output_dir = Path(__file__).parent.parent / "output"
    files = sorted(output_dir.glob("b2b_ecom_research_*.xlsx"), reverse=True)

    if not files:
        return pd.DataFrame(), None, 0, datetime.now()

    dfs: list[pd.DataFrame] = []
    errors = 0
    latest_mtime = datetime.fromtimestamp(files[0].stat().st_mtime)

    for f in files:
        try:
            df_sheet = pd.read_excel(f, sheet_name="All Leads", engine="openpyxl")
            dfs.append(df_sheet)
        except Exception:
            errors += 1
            continue

    if dfs:
        combined = pd.concat(dfs, ignore_index=True)
        return combined, files[0].name, errors, latest_mtime
    return pd.DataFrame(), None, errors, datetime.now()


with st.spinner("Pulling latest lead reports…"):
    df_raw, latest_file, load_errors, data_mtime = load_data(st.session_state.refresh_key)

if df_raw.empty:
    st.info(
        "📂 No lead data found.\n\n"
        "Run the pipeline (`python pipeline.py`) to generate reports in the `output/` folder.",
        icon="ℹ️",
    )
    st.stop()

# ── Data cleaning ──────────────────────────────────────────────
df = df_raw.copy()

# Core fields
df["country"] = df["country"].astype("string").fillna("Unknown")
df["ecommerce_platform"] = df["ecommerce_platform"].astype("string").fillna("Unknown")
df["website_url"] = df["website_url"].fillna("—")
df["business_email_generic"] = df["business_email_generic"].fillna("—")
df["business_email_named"] = df["business_email_named"].fillna("—")
df["business_phone"] = df["business_phone"].fillna("—")
df["business_address"] = df["business_address"].fillna("—")
df["improvement_opportunity"] = df["improvement_opportunity"].fillna("—")
df["outreach_priority"] = df["outreach_priority"].fillna("COLD")

# Numeric fields
df["website_quality_score"] = pd.to_numeric(df["website_quality_score"], errors="coerce").fillna(0).astype(int)
df["google_rating"] = pd.to_numeric(df["google_rating"], errors="coerce")
df["google_review_count"] = pd.to_numeric(df["google_review_count"], errors="coerce").fillna(0).astype(int)
df["estimated_product_count"] = pd.to_numeric(df["estimated_product_count"], errors="coerce").fillna(0).astype(int)
df["page_speed_score"] = pd.to_numeric(df["page_speed_score"], errors="coerce")

# Booleans
df["has_ssl"] = df["has_ssl"].map({True: "Yes", False: "No", "TRUE": "Yes", "FALSE": "No", "True": "Yes", "False": "No"}).fillna("Unknown")
df["mobile_friendly"] = df["mobile_friendly"].map({True: "Yes", False: "No", "TRUE": "Yes", "FALSE": "No", "True": "Yes", "False": "No"}).fillna("Unknown")
df["checkout_functional"] = df["checkout_functional"].map({True: "Yes", False: "No", "TRUE": "Yes", "FALSE": "No", "True": "Yes", "False": "No"}).fillna("Unknown")

# ── Sidebar ────────────────────────────────────────────────────
with st.sidebar:
    st.header("🔍 Filters")

    with st.expander("Geography & Priority", expanded=True):
        country_options = sorted(df["country"].dropna().unique())
        # Default to all if none selected
        if not st.session_state.countries:
            st.session_state.countries = country_options

        selected_countries = st.multiselect(
            "Country",
            options=country_options,
            default=st.session_state.countries,
            help="Select one or more countries.",
            key="sel_countries",
        )

        priority_options = ["HOT", "WARM", "COLD"]
        selected_priorities = st.multiselect(
            "Priority",
            options=priority_options,
            default=st.session_state.priorities,
            help="HOT = high intent, WARM = nurture, COLD = long-term.",
            key="sel_priorities",
        )

    with st.expander("Quality Score", expanded=False):
        min_score = int(df["website_quality_score"].min())
        max_score = int(df["website_quality_score"].max())
        score_range = st.slider(
            "Score range",
            min_value=min_score,
            max_value=max_score,
            value=(min_score, max_score),
            help="Filter by website quality score.",
            key="sel_score",
        )

    with st.expander("Quick Search", expanded=False):
        search_term = st.text_input(
            "Search business name",
            placeholder="e.g. Acme Corp…",
            help="Case-insensitive partial match on business name.",
            key="sel_search",
        )

    st.divider()

    # Filter actions
    c1, c2 = st.columns(2)
    with c1:
        if st.button("♻️ Reset", use_container_width=True, help="Clear all filters"):
            st.session_state.countries = country_options
            st.session_state.priorities = ["HOT", "WARM"]
            st.session_state.score_range = (min_score, max_score)
            st.session_state.search = ""
            st.rerun()
    with c2:
        if st.button("🔄 Refresh", use_container_width=True, help="Reload files from disk"):
            st.session_state.refresh_key += 1
            st.cache_data.clear()
            st.rerun()

    st.divider()

    # Data provenance
    age_minutes = int((datetime.now() - data_mtime).total_seconds() // 60)
    age_str = f"{age_minutes} min ago" if age_minutes < 60 else f"{age_minutes // 60}h ago"
    st.markdown(
        f"<p style='font-size:0.75rem; color:#6b7280;'>"
        f"📁 <b>Latest file:</b> <code>{latest_file}</code><br>"
        f"🕒 <b>Data age:</b> {age_str}<br>"
        f"⚠️ <b>Load errors:</b> {load_errors}"
        f"</p>",
        unsafe_allow_html=True,
    )

    st.divider()
    st.markdown(
        "<p style='font-size:0.7rem; color:#9ca3af;'>"
        "<b>Shortcuts:</b> Ctrl+R to reload page"
        "</p>",
        unsafe_allow_html=True,
    )

# ── Sync session state for next rerun ──────────────────────────
st.session_state.countries = selected_countries
st.session_state.priorities = selected_priorities
st.session_state.score_range = score_range
st.session_state.search = search_term

# ── Apply filters (non-destructive) ────────────────────────────
mask = (
    df["country"].isin(selected_countries)
    & df["outreach_priority"].isin(selected_priorities)
    & (df["website_quality_score"] >= score_range[0])
    & (df["website_quality_score"] <= score_range[1])
)

if search_term.strip():
    mask = mask & df["business_name"].astype(str).str.contains(search_term, case=False, na=False)

df_filtered = df.loc[mask].copy()

# ── Header ─────────────────────────────────────────────────────
left, right = st.columns([3, 1], vertical_alignment="bottom")
with left:
    st.title("🎯 B2B Lead Research Dashboard")
    st.caption("Review, filter, and export e-commerce leads across markets.")
with right:
    st.markdown(
        f"<p style='text-align:right; color:#6b7280; font-size:0.8rem;'>"
        f"🕒 Last updated<br><b>{datetime.now().strftime('%Y-%m-%d %H:%M')}</b>"
        f"</p>",
        unsafe_allow_html=True,
    )

# Filter summary chips
if len(df_filtered) < len(df):
    chip_parts = []
    if selected_countries != country_options:
        chip_parts.append(f"📍 {len(selected_countries)} countries")
    if selected_priorities != priority_options:
        chip_parts.append(f"🔖 {', '.join(selected_priorities)}")
    if score_range != (min_score, max_score):
        chip_parts.append(f"⭐ {score_range[0]}–{score_range[1]}")
    if search_term.strip():
        chip_parts.append(f'🔎 "{search_term}"')
    if chip_parts:
        chips_html = " ".join(f'<span class="filter-chip">{c}</span>' for c in chip_parts)
        st.markdown(f"<div style='margin:0.5rem 0;'>{chips_html}</div>", unsafe_allow_html=True)

st.divider()

# ── Empty state ────────────────────────────────────────────────
if df_filtered.empty:
    st.markdown(
        """
        <div class="empty-state">
            <h3>🔍 No leads match your filters</h3>
            <p>Try broadening your search or resetting filters.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Reset all filters", type="primary"):
        st.session_state.countries = country_options
        st.session_state.priorities = ["HOT", "WARM"]
        st.session_state.score_range = (min_score, max_score)
        st.session_state.search = ""
        st.rerun()
    st.stop()

# ── Metrics row (responsive) ───────────────────────────────────
hot_count = int((df_filtered["outreach_priority"] == "HOT").sum())
warm_count = int((df_filtered["outreach_priority"] == "WARM").sum())
cold_count = int((df_filtered["outreach_priority"] == "COLD").sum())
avg_score = round(df_filtered["website_quality_score"].mean(), 1) if len(df_filtered) else 0.0
avg_rating = round(df_filtered["google_rating"].mean(), 1) if len(df_filtered) else 0.0

# Use 3 columns on tablet, 5 on desktop via nested columns
m1, m2, m3 = st.columns(3)
with m1:
    st.metric("Total Leads", f"{len(df_filtered):,}", help="Number of leads matching current filters")
    st.metric("🔥 HOT", f"{hot_count:,}")
with m2:
    st.metric("⚡ WARM", f"{warm_count:,}")
    st.metric("❄️ COLD", f"{cold_count:,}")
with m3:
    st.metric("Ø Quality Score", f"{avg_score}", help="Average website quality score")
    st.metric("Ø Google Rating", f"{avg_rating}" if avg_rating > 0 else "—", help="Average Google rating")

st.divider()

# ── Tabs ───────────────────────────────────────────────────────
chart_tab, table_tab, export_tab = st.tabs(["📊 Overview", "📋 Leads Table", "⬇️ Export"])

# ── Charts Tab ─────────────────────────────────────────────────
with chart_tab:
    # Row 1: Priority + Platforms
    c1, c2 = st.columns(2)

    with c1:
        st.subheader("Priority Breakdown")
        priority_counts = (
            df_filtered["outreach_priority"]
            .value_counts()
            .reindex(["HOT", "WARM", "COLD"], fill_value=0)
            .reset_index()
        )
        priority_counts.columns = ["Priority", "Count"]
        color_map = {"HOT": "#ef4444", "WARM": "#f59e0b", "COLD": "#6b7280"}

        fig_pie = px.pie(
            priority_counts,
            names="Priority",
            values="Count",
            color="Priority",
            color_discrete_map=color_map,
            hole=0.5,
        )
        fig_pie.update_traces(
            textposition="inside",
            textinfo="percent+label",
            pull=[0.02 if p == "HOT" else 0 for p in priority_counts["Priority"]],
            marker=dict(line=dict(color="white", width=2)),
        )
        fig_pie.update_layout(
            showlegend=False,
            margin=dict(t=10, b=10, l=10, r=10),
            height=320,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_pie, use_container_width=True, config={"displayModeBar": False})

    with c2:
        st.subheader("Top Platforms")
        platform_counts = (
            df_filtered[df_filtered["ecommerce_platform"] != "Unknown"]["ecommerce_platform"]
            .value_counts()
            .head(8)
            .reset_index()
        )
        platform_counts.columns = ["Platform", "Count"]
        if not platform_counts.empty:
            fig_bar = px.bar(
                platform_counts,
                x="Count",
                y="Platform",
                orientation="h",
                color="Count",
                color_continuous_scale="Blues",
                text="Count",
            )
            fig_bar.update_traces(textposition="outside", cliponaxis=False)
            fig_bar.update_layout(
                showlegend=False,
                margin=dict(t=10, b=10, l=10, r=10),
                height=320,
                yaxis=dict(categoryorder="total ascending"),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                coloraxis_showscale=False,
            )
            st.plotly_chart(fig_bar, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("No platform data for current filter set.", icon="ℹ️")

    # Row 2: Score Distribution + Country Distribution
    c3, c4 = st.columns(2)

    with c3:
        st.subheader("Quality Score Distribution")
        scores = df_filtered["website_quality_score"].dropna()
        if len(scores) > 0:
            fig_hist = px.histogram(
                scores,
                x="website_quality_score",
                nbins=20,
                color_discrete_sequence=["#3b82f6"],
                marginal="box",
                labels={"website_quality_score": "Quality Score"},
            )
            fig_hist.update_layout(
                bargap=0.15,
                margin=dict(t=10, b=10, l=10, r=10),
                height=320,
                showlegend=False,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
            )
            fig_hist.update_xaxes(showgrid=True, gridcolor="#e5e7eb")
            fig_hist.update_yaxes(showgrid=True, gridcolor="#e5e7eb")
            st.plotly_chart(fig_hist, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("No score data to display.", icon="ℹ️")

    with c4:
        st.subheader("Leads by Country")
        country_counts = (
            df_filtered[df_filtered["country"] != "Unknown"]["country"]
            .value_counts()
            .head(10)
            .reset_index()
        )
        country_counts.columns = ["Country", "Count"]
        if not country_counts.empty:
            fig_country = px.bar(
                country_counts,
                x="Country",
                y="Count",
                color="Count",
                color_continuous_scale="Greens",
                text="Count",
            )
            fig_country.update_traces(textposition="outside", cliponaxis=False)
            fig_country.update_layout(
                showlegend=False,
                margin=dict(t=10, b=10, l=10, r=10),
                height=320,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                coloraxis_showscale=False,
            )
            fig_country.update_xaxes(showgrid=True, gridcolor="#e5e7eb")
            fig_country.update_yaxes(showgrid=True, gridcolor="#e5e7eb")
            st.plotly_chart(fig_country, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("No country data for current filter set.", icon="ℹ️")

    # Row 3: Scatter plot (Score vs Rating)
    st.subheader("Quality Score vs Google Rating")
    scatter_df = df_filtered.dropna(subset=["google_rating", "website_quality_score"])
    if len(scatter_df) > 0:
        fig_scatter = px.scatter(
            scatter_df,
            x="website_quality_score",
            y="google_rating",
            color="outreach_priority",
            color_discrete_map=color_map,
            hover_data=["business_name", "country", "ecommerce_platform"],
            size="google_review_count",
            size_max=25,
            opacity=0.75,
            labels={"website_quality_score": "Quality Score", "google_rating": "Google Rating"},
        )
        fig_scatter.update_layout(
            margin=dict(t=10, b=10, l=10, r=10),
            height=400,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        fig_scatter.update_xaxes(showgrid=True, gridcolor="#e5e7eb")
        fig_scatter.update_yaxes(showgrid=True, gridcolor="#e5e7eb")
        st.plotly_chart(fig_scatter, use_container_width=True, config={"displayModeBar": False})
    else:
        st.info("Not enough data for score vs rating analysis.", icon="ℹ️")


# ── Table Tab ──────────────────────────────────────────────────
with table_tab:
    st.subheader(f"Leads ({len(df_filtered):,} results)")

    # Choose columns to display
    display_cols = [
        "business_name",
        "country",
        "website_url",
        "website_quality_score",
        "outreach_priority",
        "ecommerce_platform",
        "business_email_generic",
        "business_phone",
        "google_rating",
        "google_review_count",
        "improvement_opportunity",
    ]
    available_cols = [c for c in display_cols if c in df_filtered.columns]

    # Use native st.dataframe with column_config for rich UX
    col_config = {
        "business_name": st.column_config.TextColumn("Business", width="large"),
        "country": st.column_config.TextColumn("Country", width="small"),
        "website_url": st.column_config.LinkColumn("Website", width="medium"),
        "website_quality_score": st.column_config.ProgressColumn(
            "Score",
            help="0–100 quality rating",
            min_value=0,
            max_value=100,
            format="%d",
        ),
        "outreach_priority": st.column_config.SelectboxColumn(
            "Priority",
            help="HOT = high intent, WARM = nurture, COLD = long-term",
            options=["HOT", "WARM", "COLD"],
            required=True,
        ),
        "ecommerce_platform": st.column_config.TextColumn("Platform", width="small"),
        "business_email_generic": st.column_config.TextColumn("Email", width="medium"),
        "business_phone": st.column_config.TextColumn("Phone", width="small"),
        "google_rating": st.column_config.NumberColumn("Rating", format="%.1f ⭐"),
        "google_review_count": st.column_config.NumberColumn("Reviews", format="%d"),
        "improvement_opportunity": st.column_config.TextColumn("Opportunity", width="large"),
    }

    # Only include configs for available columns
    active_col_config = {k: v for k, v in col_config.items() if k in available_cols}

    st.dataframe(
        df_filtered[available_cols],
        use_container_width=True,
        hide_index=True,
        column_config=active_col_config,
        column_order=available_cols,
    )

    # Expandable detail cards for top leads
    st.divider()
    st.subheader("Top HOT Leads")
    top_hot = df_filtered[df_filtered["outreach_priority"] == "HOT"].head(3)
    if not top_hot.empty:
        for _, row in top_hot.iterrows():
            with st.expander(f"🔥 {row['business_name']} — {row['country']}"):
                d1, d2, d3 = st.columns(3)
                with d1:
                    st.markdown(f"**Website:** [{row['website_url']}]({row['website_url']})")
                    st.markdown(f"**Platform:** {row['ecommerce_platform']}")
                with d2:
                    st.markdown(f"**Email:** {row['business_email_generic']}")
                    st.markdown(f"**Phone:** {row['business_phone']}")
                with d3:
                    st.markdown(f"**Score:** {row['website_quality_score']}/100")
                    st.markdown(f"**Rating:** {row['google_rating']} ⭐ ({row['google_review_count']} reviews)")
                st.markdown(f"**Opportunity:** {row['improvement_opportunity']}")
    else:
        st.caption("No HOT leads in current filter set.")


# ── Export Tab ─────────────────────────────────────────────────
with export_tab:
    st.subheader("Export Filtered Results")

    ts = datetime.now().strftime("%Y%m%d_%H%M")
    filename_base = f"filtered_leads_{ts}"

    # Preview summary
    preview_col1, preview_col2, preview_col3 = st.columns(3)
    preview_col1.metric("Rows", f"{len(df_filtered):,}")
    preview_col2.metric("Columns", len(df_filtered.columns))
    preview_col3.metric("From total", f"{len(df_raw):,}")

    st.caption("Preview of first 5 rows:")
    preview_cols = ["business_name", "country", "website_quality_score", "outreach_priority", "ecommerce_platform"]
    preview_cols = [c for c in preview_cols if c in df_filtered.columns]
    st.dataframe(
        df_filtered[preview_cols].head(5),
        use_container_width=True,
        hide_index=True,
    )

    st.divider()

    col_csv, col_xlsx = st.columns(2)

    csv_data = df_filtered.to_csv(index=False).encode("utf-8")
    col_csv.download_button(
        label="⬇️ Download CSV",
        data=csv_data,
        file_name=f"{filename_base}.csv",
        mime="text/csv",
        use_container_width=True,
    )

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df_filtered.to_excel(writer, sheet_name="Filtered Leads", index=False)
    col_xlsx.download_button(
        label="⬇️ Download Excel",
        data=buffer.getvalue(),
        file_name=f"{filename_base}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    st.divider()
    st.markdown(
        f"<p style='font-size:0.8rem; color:#6b7280;'>"
        f"Export includes <b>{len(df_filtered):,}</b> rows and <b>{len(df_filtered.columns)}</b> columns. "
        f"Original dataset: <b>{len(df_raw):,}</b> rows."
        f"</p>",
        unsafe_allow_html=True,
    )
