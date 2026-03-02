"""Tutorial generation UI."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, cast

import streamlit as st

from core.analytics_engine import update_analytics
from core.content_generator import TutorialGenerator
from core.content_optimizer import analyze_historical_performance, suggest_improvements
from core.scheduler import PublicationQueue
from core.template_manager import get_template_by_name, list_templates, save_template
from publishers import publish_to_platforms
from utils.historial import append_item, update_item


def _parse_tags(raw_tags: str) -> List[str]:
    return [item.strip().lower() for item in raw_tags.split(",") if item.strip()]


def _render_publish_results(results: dict) -> None:
    st.subheader("Resultados de publicacion")
    for platform, result in results.items():
        if result.get("success"):
            st.success(f"{platform}: publicado")
            if result.get("url"):
                st.write(result["url"])
        else:
            st.error(f"{platform}: {result.get('error', 'Error desconocido')}")


def render_generator_ui() -> None:
    """Render generation and publication workflow."""
    st.title("Generador de tutoriales")
    st.caption("Flujo simple: 1) tema 2) generar 3) publicar/programar")
    generator = TutorialGenerator()
    history_insights = analyze_historical_performance()

    auto_topic = st.session_state.get("auto_topic", "")
    selected_suggestion = st.session_state.get("selected_suggestion", {})
    suggested_topic = selected_suggestion.get("topic", "")
    default_topic = auto_topic or suggested_topic

    templates = list_templates()
    template_names = [item["name"] for item in templates]
    template_choice = cast(str, st.selectbox("Template", options=["(ninguno)"] + template_names, index=0))
    selected_template = (
        get_template_by_name(template_choice)
        if template_choice and template_choice != "(ninguno)"
        else None
    )

    topic = st.text_input("Topic del tutorial", value=default_topic, placeholder="Ej: Como usar Git desde terminal")
    col1, col2, col3 = st.columns(3)
    with col1:
        default_length = selected_template.get("length", "medium") if selected_template else "medium"
        length_options = ["short", "medium", "long"]
        length_index = length_options.index(default_length) if default_length in length_options else 1
        length = st.selectbox("Longitud", options=length_options, index=length_index)
    with col2:
        default_type = selected_template.get("tutorial_type", "technical") if selected_template else "technical"
        type_options = ["technical", "conceptual", "quickstart"]
        type_index = type_options.index(default_type) if default_type in type_options else 0
        tutorial_type = st.selectbox(
            "Tipo",
            options=type_options,
            index=type_index,
        )
    with col3:
        st.metric("Longitud historica optima", f"{history_insights['optimal_length']} palabras")

    default_tags = ",".join(selected_template.get("tags", [])) if selected_template else ""
    tag_input = st.text_input("Tags (coma separada)", value=default_tags)

    template_name = st.text_input("Guardar como template", value="")
    if st.button("Guardar template actual"):
        try:
            payload = save_template(
                {
                    "name": template_name,
                    "structure": [],
                    "tone": "educational",
                    "includes_code": tutorial_type in {"technical", "quickstart"},
                    "avg_performance": 0,
                    "tutorial_type": tutorial_type,
                    "length": length,
                    "tags": _parse_tags(tag_input),
                }
            )
            st.success(f"Template guardado: {payload['name']}")
        except ValueError as exc:
            st.error(str(exc))

    status = generator.get_engine_status()
    with st.expander("Motores LLM disponibles"):
        st.write("Orden fallback: Groq -> Local (Ollama) -> Gemini")
        st.write(f"Groq: {status['groq']['configured']} - {status['groq']['detail']}")
        st.write(f"Ollama: {status['ollama']['configured']} - {status['ollama']['detail']}")
        st.write(f"Gemini: {status['gemini']['configured']} - {status['gemini']['detail']}")

    has_any_engine = any(item["configured"] == "yes" for item in status.values())
    if not has_any_engine:
        st.error("No hay motores LLM listos.")
        st.info(
            "Configura al menos uno: GROQ_API_KEY, o GOOGLE_API_KEY, o instala Ollama con un modelo local "
            "(ej: qwen2.5:14b). Luego reinicia la app."
        )

    if st.button("Generar tutorial", type="primary"):
        if not topic.strip():
            st.error("Debes ingresar un topic.")
        elif not has_any_engine:
            st.error("No se puede generar: no hay motores configurados.")
        else:
            try:
                with st.spinner("Generando tutorial con fallback automatico..."):
                    generated_tutorial = generator.generate_tutorial_with_fallback(
                        topic=topic.strip(),
                        length=length,
                        tutorial_type=tutorial_type,
                        tags=_parse_tags(tag_input),
                    )
                append_item(generated_tutorial)
                st.session_state["last_tutorial"] = generated_tutorial
                st.success(f"Tutorial generado con {generated_tutorial['llm_used']}.")
            except RuntimeError as exc:
                st.error("No se pudo generar con ningun motor.")
                st.code(str(exc), language="text")
                st.info("Revisa tutorial_pipeline_v2/.env y confirma que Ollama este corriendo si usas local.")
            except Exception as exc:  # pragma: no cover
                st.error(f"Error inesperado: {exc}")

    tutorial = cast(Dict[str, Any] | None, st.session_state.get("last_tutorial"))
    if not tutorial:
        st.info("Genera un tutorial para ver preview y opciones de publicacion.")
        return

    st.markdown("---")
    st.subheader("Preview")
    st.write(f"Titulo: {tutorial.get('title', '-')}")
    st.write(f"Words: {tutorial.get('word_count', 0)}")
    st.write(f"Motor usado: {tutorial.get('llm_used', '-')}")
    st.write(f"Tiempo generacion: {tutorial.get('generation_time', 0)}s")

    quality = tutorial.get("quality", {})
    score = int(quality.get("score", tutorial.get("performance_score", 0)))
    st.progress(min(100, max(0, score)) / 100)
    st.caption(f"Score de calidad: {score}/100")
    if quality.get("issues"):
        st.warning("Problemas detectados: " + "; ".join(quality["issues"]))

    st.text_area("Contenido generado", value=tutorial.get("content", ""), height=380)

    suggestions = suggest_improvements(
        {
            "word_count": tutorial.get("word_count", 0),
            "tags": tutorial.get("tags", []),
            "platforms": tutorial.get("platforms_published", []),
        }
    )
    if suggestions:
        st.subheader("Sugerencias de mejora")
        for item in suggestions:
            st.write(f"- [{item['priority']}] {item['message']}")

    st.markdown("---")
    st.subheader("Publicacion")
    platforms = st.multiselect(
        "Selecciona plataformas",
        options=["devto", "hashnode", "telegram", "blogger"],
        default=["devto", "hashnode"],
    )

    publish_now_col, schedule_col = st.columns(2)
    with publish_now_col:
        if st.button("Publicar ahora", disabled=not platforms):
            results = publish_to_platforms(tutorial_data=tutorial, platforms=platforms)
            _render_publish_results(results)

            urls = {platform: result.get("url") for platform, result in results.items() if result.get("url")}
            successful = [platform for platform, result in results.items() if result.get("success")]
            updates = {
                "platforms_published": list(sorted(set((tutorial.get("platforms_published") or []) + successful))),
                "urls": {**(tutorial.get("urls") or {}), **urls},
            }
            updated = update_item(tutorial["id"], updates)
            st.session_state["last_tutorial"] = updated or {**tutorial, **updates}
            update_analytics(st.session_state["last_tutorial"], results)

    with schedule_col:
        schedule_date = st.date_input("Fecha programada", value=datetime.now().date())
        schedule_time = st.time_input("Hora programada", value=datetime.now().time())
        if st.button("Programar", disabled=not platforms):
            queue = PublicationQueue()
            scheduled_for = datetime.combine(schedule_date, schedule_time)
            job_id = queue.schedule(tutorial_data=tutorial, platforms=platforms, publish_datetime=scheduled_for)
            st.success(f"Publicacion programada. Job ID: {job_id}")
