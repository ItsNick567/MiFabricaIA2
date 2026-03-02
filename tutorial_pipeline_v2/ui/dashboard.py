"""Main dashboard view."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core.analytics_engine import calculate_revenue_estimate, get_top_performing_tutorials, load_analytics


def _timeline_frame(analytics: dict) -> pd.DataFrame:
    timeline = analytics.get("timeline", [])
    if not timeline:
        return pd.DataFrame({"date": [], "generated": [], "published": [], "revenue_estimate": []})
    df = pd.DataFrame(timeline)
    return df.sort_values("date")


def _platform_frame(analytics: dict) -> pd.DataFrame:
    by_platform = analytics.get("by_platform", {})
    rows = []
    for platform, values in by_platform.items():
        rows.append(
            {
                "platform": platform,
                "published": int(values.get("published", 0) or 0),
                "estimated_reads": int(values.get("estimated_reads", 0) or 0),
                "estimated_revenue": float(values.get("estimated_revenue", 0.0) or 0.0),
            }
        )
    return pd.DataFrame(rows)


def render_dashboard() -> None:
    """Dashboard with global KPIs and top tutorials."""
    st.title("Tutorial Pipeline v2 - Dashboard")
    analytics = load_analytics()

    global_stats = analytics.get("global", {})
    total_generated = int(global_stats.get("total_generated", 0) or 0)
    total_published = int(global_stats.get("total_published", 0) or 0)
    success_rate = float(global_stats.get("success_rate", 0.0) or 0.0)
    revenue = calculate_revenue_estimate(analytics)

    timeline_df = _timeline_frame(analytics)
    published_delta = int(timeline_df["published"].tail(7).sum()) if not timeline_df.empty else 0
    generated_delta = int(timeline_df["generated"].tail(7).sum()) if not timeline_df.empty else 0
    revenue_delta = float(timeline_df["revenue_estimate"].tail(30).sum()) if not timeline_df.empty else 0.0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Generados", total_generated, delta=f"+{generated_delta} (7d)")
    col2.metric("Publicados", total_published, delta=f"+{published_delta} (7d)")
    col3.metric("Ingreso Estimado", f"${revenue:.2f}", delta=f"+${revenue_delta:.2f} (30d)")
    col4.metric("Tasa de Exito", f"{success_rate:.1f}%")

    st.markdown("---")
    left, right = st.columns(2)

    with left:
        st.subheader("Publicaciones por fecha")
        if timeline_df.empty:
            st.info("Todavia no hay datos de timeline.")
        else:
            chart_df = timeline_df.set_index("date")[["generated", "published"]]
            st.line_chart(chart_df)

    with right:
        st.subheader("Rendimiento por plataforma")
        platform_df = _platform_frame(analytics)
        if platform_df.empty:
            st.info("Todavia no hay datos por plataforma.")
        else:
            st.bar_chart(platform_df.set_index("platform")[["published", "estimated_reads"]])

    st.markdown("---")
    st.subheader("Top tutoriales")
    top_tutorials = get_top_performing_tutorials(limit=5)
    if not top_tutorials:
        st.info("No hay tutoriales con score para mostrar.")
        return

    for index, tutorial in enumerate(top_tutorials, start=1):
        title = tutorial.get("title") or tutorial.get("topic") or "Tutorial"
        score = tutorial.get("performance_score", 0)
        with st.expander(f"{index}. {title} | Score: {score}/100"):
            st.write(f"Topic: {tutorial.get('topic', '-')}")
            st.write(f"Plataformas: {', '.join(tutorial.get('platforms_published', [])) or '-'}")
            st.write(f"Lecturas estimadas: {tutorial.get('estimated_reads', 0)}")
            st.write(f"Ingreso estimado: ${float(tutorial.get('estimated_revenue', 0.0) or 0.0):.2f}")
