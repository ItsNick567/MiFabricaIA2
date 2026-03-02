"""Trends and opportunity UI."""

from __future__ import annotations

import streamlit as st

from core.content_optimizer import (
    analyze_historical_performance,
    detect_content_opportunities,
    generate_content_suggestions,
)
from core.trend_analyzer import get_trends_cached


def render_trends_view() -> None:
    """Render trends, historical analysis, and idea suggestions."""
    st.title("Tendencias y oportunidades")
    tab1, tab2, tab3 = st.tabs(["Trending Now", "Analisis Historico", "Sugerencias"])

    with tab1:
        st.subheader("Temas mas demandados")
        category_options = ["programming", "python", "javascript", "react", "devops"]
        category = st.selectbox("Categoria", options=category_options, index=0)
        trends = get_trends_cached(category)
        if not trends:
            st.info("No se pudo cargar tendencias.")
        else:
            for idx, (topic, score) in enumerate(trends[:10], start=1):
                c1, c2, c3 = st.columns([6, 2, 2])
                with c1:
                    st.markdown(f"**{idx}. {topic}**")
                with c2:
                    st.progress(min(100, max(0, int(score))) / 100)
                    st.caption(f"Score: {score}/100")
                with c3:
                    if st.button("Generar", key=f"trend_gen_{category}_{idx}"):
                        st.session_state["auto_topic"] = topic
                        st.session_state["pending_nav"] = "Generador"
                        st.rerun()
            st.caption("Fuentes: Dev.to + Hashnode + GitHub + Reddit")

    with tab2:
        st.subheader("Rendimiento historico")
        performance = analyze_historical_performance()

        st.markdown("### Tus mejores topics")
        if not performance["best_topics"]:
            st.info("Sin historial suficiente todavia.")
        else:
            for topic_data in performance["best_topics"][:5]:
                st.write(f"- {topic_data['topic']} | Score: {topic_data['score']}/100")

        c1, c2 = st.columns(2)
        with c1:
            st.metric("Longitud optima", f"{performance['optimal_length']} palabras")
        with c2:
            best_platform = performance["best_platforms"][0] if performance["best_platforms"] else "n/a"
            st.metric("Mejor plataforma", best_platform.capitalize())

        st.markdown("### Tags mas efectivos")
        tags = performance["recommended_tags"][:10]
        st.write(", ".join(tags) if tags else "Sin datos.")

    with tab3:
        st.subheader("Ideas sugeridas")
        suggestions = generate_content_suggestions(limit=15)
        opportunities = detect_content_opportunities(limit=10)

        if not suggestions:
            st.info("Sin sugerencias nuevas por ahora.")
        else:
            for suggestion in suggestions:
                c1, c2 = st.columns([8, 2])
                with c1:
                    st.markdown(f"**{suggestion['title']}**")
                    st.caption(f"Categoria: {suggestion['category']} | Dificultad: {suggestion['difficulty']}")
                    st.caption(f"Score: {suggestion['trend_score']}")
                with c2:
                    if st.button("Usar", key=f"use_{suggestion['id']}"):
                        st.session_state["selected_suggestion"] = suggestion
                        st.session_state["auto_topic"] = suggestion["topic"]
                        st.session_state["pending_nav"] = "Generador"
                        st.rerun()

        st.markdown("---")
        st.markdown("### Oportunidades detectadas")
        if not opportunities:
            st.info("Sin oportunidades detectadas.")
        else:
            for opportunity in opportunities:
                st.write(f"- [{opportunity['type']}] {opportunity['topic']} (score {opportunity['score']})")
                st.caption(opportunity["reason"])
