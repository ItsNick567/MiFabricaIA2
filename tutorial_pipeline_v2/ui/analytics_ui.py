"""Detailed analytics view."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core.analytics_engine import calculate_revenue_estimate, load_analytics


def _build_platform_df(analytics: dict) -> pd.DataFrame:
    rows = []
    for platform, values in analytics.get("by_platform", {}).items():
        rows.append(
            {
                "platform": platform,
                "published": int(values.get("published", 0) or 0),
                "estimated_reads": int(values.get("estimated_reads", 0) or 0),
                "estimated_revenue": float(values.get("estimated_revenue", 0.0) or 0.0),
            }
        )
    return pd.DataFrame(rows)


def _build_llm_df(analytics: dict) -> pd.DataFrame:
    rows = []
    for engine, values in analytics.get("by_llm_engine", {}).items():
        rows.append(
            {
                "engine": engine,
                "uses": int(values.get("uses", 0) or 0),
                "avg_time": float(values.get("avg_time", 0.0) or 0.0),
                "success_rate": float(values.get("success_rate", 0.0) or 0.0),
            }
        )
    return pd.DataFrame(rows)


def render_analytics_ui() -> None:
    """Render analytics and reporting page."""
    st.title("Analytics detallados")
    analytics = load_analytics()
    global_stats = analytics.get("global", {})

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Generados", int(global_stats.get("total_generated", 0) or 0))
    c2.metric("Publicados", int(global_stats.get("total_published", 0) or 0))
    c3.metric("Success rate", f"{float(global_stats.get('success_rate', 0.0) or 0.0):.1f}%")
    c4.metric("Revenue estimado", f"${calculate_revenue_estimate(analytics):.2f}")

    st.markdown("---")
    st.subheader("Rendimiento por plataforma")
    platform_df = _build_platform_df(analytics)
    if platform_df.empty:
        st.info("No hay datos de plataforma todavia.")
    else:
        st.dataframe(platform_df, use_container_width=True)
        st.bar_chart(platform_df.set_index("platform")[["published", "estimated_reads", "estimated_revenue"]])

    st.markdown("---")
    st.subheader("Rendimiento por motor LLM")
    llm_df = _build_llm_df(analytics)
    if llm_df.empty:
        st.info("No hay datos LLM todavia.")
    else:
        st.dataframe(llm_df, use_container_width=True)
        st.bar_chart(llm_df.set_index("engine")[["uses", "success_rate"]])

    st.markdown("---")
    st.subheader("Timeline")
    timeline = analytics.get("timeline", [])
    if not timeline:
        st.info("No hay timeline todavia.")
    else:
        timeline_df = pd.DataFrame(timeline).sort_values("date")
        st.line_chart(timeline_df.set_index("date")[["generated", "published", "revenue_estimate"]])
