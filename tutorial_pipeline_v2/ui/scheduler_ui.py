"""Scheduler and queue management UI."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core.scheduler import PublicationQueue, execute_pending_jobs, optimal_publishing_strategy


def render_scheduler_ui() -> None:
    """Render scheduler planning and queue controls."""
    st.title("Scheduler de publicaciones")
    queue = PublicationQueue()

    st.subheader("Estrategia recomendada")
    per_week = st.slider("Tutoriales por semana", min_value=1, max_value=7, value=3)
    suggested = optimal_publishing_strategy(tutorial_count_per_week=per_week)
    for slot in suggested:
        st.write(f"- {slot.strftime('%Y-%m-%d %H:%M')}")

    st.markdown("---")
    st.subheader("Cola de publicacion")
    if not queue.queue:
        st.info("No hay publicaciones programadas.")
    else:
        table = pd.DataFrame(queue.queue)
        st.dataframe(table, use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Ejecutar jobs pendientes ahora"):
            result = execute_pending_jobs(queue)
            if not result:
                st.info("No habia jobs pendientes para ejecutar.")
            else:
                st.success(f"Jobs procesados: {len(result)}")
                st.json(result)
                st.rerun()

    with c2:
        if st.button("Recargar cola"):
            st.rerun()

    st.markdown("---")
    st.subheader("Programar el ultimo tutorial generado")
    tutorial = st.session_state.get("last_tutorial")
    if not tutorial:
        st.info("Primero genera un tutorial en la seccion Generador.")
        return

    st.write(f"Tutorial actual: {tutorial.get('title') or tutorial.get('topic')}")
    platforms = st.multiselect(
        "Plataformas",
        options=["devto", "hashnode", "telegram", "blogger"],
        default=["devto", "hashnode"],
        key="scheduler_platforms",
    )
    date_col, time_col = st.columns(2)
    with date_col:
        date_value = st.date_input("Fecha")
    with time_col:
        time_value = st.time_input("Hora")

    if st.button("Agregar a cola", disabled=not platforms):
        from datetime import datetime

        scheduled_for = datetime.combine(date_value, time_value)
        job_id = queue.schedule(tutorial_data=tutorial, platforms=platforms, publish_datetime=scheduled_for)
        st.success(f"Job agregado: {job_id}")
