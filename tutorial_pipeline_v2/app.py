"""Streamlit entrypoint for Tutorial Pipeline v2."""

from __future__ import annotations

import streamlit as st

from config import settings
from ui.analytics_ui import render_analytics_ui
from ui.dashboard import render_dashboard
from ui.generator_ui import render_generator_ui
from ui.scheduler_ui import render_scheduler_ui
from ui.trends_ui import render_trends_view
from utils.logger import setup_logging
from utils.paths import ensure_dirs

ensure_dirs()
setup_logging()

st.set_page_config(page_title="Tutorial Pipeline v2", page_icon=":bar_chart:", layout="wide")


def main() -> None:
    """Main app router."""
    st.sidebar.title("Tutorial Pipeline v2")
    st.sidebar.caption("Generacion + publicacion + analytics")

    pages = ["Dashboard", "Generador", "Tendencias", "Analytics", "Scheduler"]
    if "pending_nav" in st.session_state:
        target = st.session_state.pop("pending_nav")
        if target in pages:
            st.session_state["nav_selector"] = target

    if "nav_selector" not in st.session_state:
        st.session_state["nav_selector"] = "Dashboard"

    current = st.sidebar.radio("Navegacion", options=pages, key="nav_selector")

    st.sidebar.markdown("---")
    st.sidebar.write("Fallback LLM:")
    st.sidebar.code(
        f"1) {settings.LLM_ENGINE_PRIMARY}\n2) {settings.LLM_ENGINE_SECONDARY}\n3) {settings.LLM_ENGINE_FALLBACK}",
        language="text",
    )
    st.sidebar.markdown("---")
    st.sidebar.subheader("Estado rapido")
    st.sidebar.write(
        f"Groq key: {'OK' if settings.GROQ_API_KEY else 'Falta'}\n\n"
        f"Gemini key: {'OK' if settings.GOOGLE_API_KEY else 'Falta'}\n\n"
        f"Modelo local: {settings.LOCAL_LLM_MODEL or 'No definido'}"
    )
    st.sidebar.caption("Las API keys se configuran en tutorial_pipeline_v2/.env")

    if current == "Dashboard":
        render_dashboard()
    elif current == "Generador":
        render_generator_ui()
    elif current == "Tendencias":
        render_trends_view()
    elif current == "Analytics":
        render_analytics_ui()
    elif current == "Scheduler":
        render_scheduler_ui()


if __name__ == "__main__":
    main()
