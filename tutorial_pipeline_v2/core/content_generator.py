"""Tutorial generation pipeline with hard English enforcement and LLM fallback."""

from __future__ import annotations

import re
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List

from config import settings
from utils.cache_manager import CacheManager
from utils.llm_text import generar_texto_motor, listar_modelos_locales
from utils.logger import get_logger
from utils.paths import ensure_dirs, p

logger = get_logger(__name__)

PRIMARY_ENGINE = "Groq"
SECONDARY_ENGINE = "Local (Ollama)"
FALLBACK_ENGINE = "Gemini (GRATIS)"

WORD_COUNT_BY_LENGTH = {
    "short": 800,
    "medium": 1100,
    "long": 1400,
}

TUTORIAL_TEMPLATES = {
    "technical": """You are a technical writer creating tutorials for developers.

CRITICAL RULES:
- Write ONLY in ENGLISH.
- Do not translate to Spanish or any other language.
- Keep technical terms and commands exactly as they should be typed.

Create a comprehensive tutorial about: {topic}

Requirements:
- Language: ENGLISH ONLY
- Audience: Beginner to intermediate developers
- Length target: {word_count} words
- Tone: Educational, clear, practical
- Include: Code examples and step-by-step instructions

Structure:
1. Introduction (2-3 short paragraphs)
2. Prerequisites
3. Main content (3-5 sections with examples)
4. Troubleshooting
5. Conclusion

Return valid Markdown only.
""",
    "conceptual": """You are an expert educator.

CRITICAL RULES:
- Write ONLY in ENGLISH.
- Keep explanations simple and practical.

Explain this topic clearly: {topic}

Requirements:
- Language: ENGLISH ONLY
- Target length: {word_count} words
- Include one analogy and one practical example
- Use Markdown headings for each section

Structure:
1. Introduction
2. Core concepts
3. Practical example
4. Common mistakes
5. Conclusion
""",
    "quickstart": """You are a developer advocate writing fast-start guides.

CRITICAL RULES:
- Write ONLY in ENGLISH.
- Focus on executable steps.

Create a quickstart tutorial for: {topic}

Requirements:
- Language: ENGLISH ONLY
- Target length: {word_count} words
- 5-8 numbered steps
- Include commands/code snippets
- Include expected output checks

Structure:
1. What you will build
2. Prerequisites
3. Steps
4. Troubleshooting
5. Next steps
""",
}

SPANISH_HINTS = {
    " el ",
    " la ",
    " los ",
    " las ",
    " un ",
    " una ",
    " de ",
    " en ",
    " que ",
    " con ",
    " para ",
    " como ",
    " por ",
}
ENGLISH_HINTS = {
    " the ",
    " a ",
    " an ",
    " is ",
    " are ",
    " in ",
    " to ",
    " of ",
    " and ",
    " for ",
    " with ",
    " from ",
}


def build_tutorial_prompt(topic: str, length: str = "medium", tutorial_type: str = "technical") -> str:
    """Build LLM prompt from topic and tutorial style."""
    word_count = WORD_COUNT_BY_LENGTH.get(length, WORD_COUNT_BY_LENGTH["medium"])
    template = TUTORIAL_TEMPLATES.get(tutorial_type, TUTORIAL_TEMPLATES["technical"])
    return template.format(topic=topic, word_count=word_count)


def detect_language(text: str) -> str:
    """Heuristic language detection focused on English-vs-Spanish output."""
    normalized = f" {(text or '').lower()} "
    spanish_count = sum(1 for token in SPANISH_HINTS if token in normalized)
    english_count = sum(1 for token in ENGLISH_HINTS if token in normalized)

    if any(marker in normalized for marker in [" cion ", " ciones ", " para ", " sobre "]):
        spanish_count += 1

    if english_count >= spanish_count:
        return "en"
    return "es"


def _normalize_engine_name(engine_label: str) -> str:
    raw = str(engine_label).lower()
    if "groq" in raw:
        return "groq"
    if "ollama" in raw or "local" in raw:
        return "ollama"
    if "gemini" in raw:
        return "gemini"
    return "unknown"


def force_translate_to_english(text: str, engines: List[str] | None = None) -> str:
    """Force translation to English via configured LLM engines."""
    prompt = (
        "Translate the following content to ENGLISH only. "
        "Preserve code blocks, commands, and technical terms exactly.\n\n"
        f"Text:\n{text}\n\n"
        "English translation (Markdown):"
    )

    engine_order = engines or [
        settings.LLM_ENGINE_PRIMARY,
        settings.LLM_ENGINE_SECONDARY,
        settings.LLM_ENGINE_FALLBACK,
    ]

    for engine in engine_order:
        try:
            translated = generar_texto_motor(
                prompt=prompt,
                motor_texto=engine,
                groq_key=settings.GROQ_API_KEY if "groq" in str(engine).lower() else None,
                local_model=settings.LOCAL_LLM_MODEL,
                local_base_url=settings.LOCAL_LLM_BASE_URL,
                allow_cloud_fallback=not settings.LOCAL_LLM_STRICT,
            )
            if translated and detect_language(translated) == "en":
                return translated
        except Exception as exc:  # pragma: no cover
            logger.warning("Translation attempt failed engine=%s error=%s", engine, exc)

    return text


def _extract_title(text: str, fallback_topic: str) -> str:
    generic_titles = {
        "introduction",
        "tutorial",
        "guide",
        "overview",
        "getting started",
    }
    topic_lower = str(fallback_topic or "").strip().lower()

    for line in (text or "").splitlines():
        cleaned = line.strip().lstrip("#").strip()
        if not cleaned:
            continue
        cleaned_lower = cleaned.lower()

        if cleaned_lower in generic_titles:
            continue

        # If the title is too generic and does not reference the topic, force a descriptive fallback.
        if len(cleaned.split()) <= 2 and topic_lower and topic_lower not in cleaned_lower:
            continue

        return cleaned[:140]

    if fallback_topic:
        return f"Introduction to {fallback_topic}"[:140]
    return "Practical Developer Tutorial"


def _extract_sections(text: str) -> List[Dict[str, str]]:
    sections: List[Dict[str, str]] = []
    current_title = "Introduction"
    current_lines: List[str] = []

    for line in (text or "").splitlines():
        if line.strip().startswith("##"):
            if current_lines:
                sections.append({"title": current_title, "content": "\n".join(current_lines).strip()})
                current_lines = []
            current_title = line.strip().lstrip("#").strip() or "Section"
        else:
            current_lines.append(line)

    if current_lines:
        sections.append({"title": current_title, "content": "\n".join(current_lines).strip()})

    return [section for section in sections if section.get("content")]


def analyze_tutorial_quality(tutorial_text: str) -> Dict[str, Any]:
    """Analyze generated tutorial quality and return score + issues."""
    score = 100
    issues: List[str] = []

    word_count = len((tutorial_text or "").split())
    if word_count < 700:
        score -= 20
        issues.append("Content is too short (<700 words)")
    elif word_count > 2500:
        score -= 10
        issues.append("Content is too long (>2500 words)")

    if "##" not in (tutorial_text or ""):
        score -= 15
        issues.append("Missing markdown sections")

    lower_text = (tutorial_text or "").lower()
    has_code_hint = any(keyword in lower_text for keyword in ["python", "javascript", "code", "command"])
    if "```" not in (tutorial_text or "") and has_code_hint:
        score -= 10
        issues.append("Missing code blocks")

    if detect_language(tutorial_text) != "en":
        score -= 30
        issues.append("Language validation failed (non-English output)")

    return {
        "score": max(0, score),
        "word_count": word_count,
        "issues": issues,
        "has_code": "```" in (tutorial_text or ""),
        "has_sections": "##" in (tutorial_text or ""),
        "language": detect_language(tutorial_text),
    }


def _suggest_tags(topic: str, content: str, max_tags: int = 8) -> List[str]:
    candidates = re.findall(r"[a-zA-Z0-9+#.-]{3,}", f"{topic} {content[:600]}")
    stop = {"the", "and", "for", "with", "tutorial", "guide"}
    ranked: List[str] = []
    for token in candidates:
        low = token.lower()
        if low in stop or low.isdigit() or low in ranked:
            continue
        ranked.append(low)
        if len(ranked) >= max_tags:
            break
    return ranked


class TutorialGenerator:
    """High-level tutorial generation service."""

    def __init__(self) -> None:
        ensure_dirs()
        self.cache = CacheManager()
        self.engines = [
            settings.LLM_ENGINE_PRIMARY or PRIMARY_ENGINE,
            settings.LLM_ENGINE_SECONDARY or SECONDARY_ENGINE,
            settings.LLM_ENGINE_FALLBACK or FALLBACK_ENGINE,
        ]

        if settings.GOOGLE_API_KEY:
            try:
                import google.generativeai as genai

                genai.configure(api_key=settings.GOOGLE_API_KEY)
            except Exception as exc:  # pragma: no cover
                logger.warning("Could not configure Gemini SDK: %s", exc)

    def list_local_models(self) -> List[str]:
        """Expose local model discovery for UI."""
        return listar_modelos_locales(base_url=settings.LOCAL_LLM_BASE_URL)

    def get_engine_status(self) -> Dict[str, Dict[str, str]]:
        """Return readiness hints for each engine."""
        local_models = self.list_local_models()
        return {
            "groq": {
                "configured": "yes" if bool(settings.GROQ_API_KEY) else "no",
                "detail": "GROQ_API_KEY configured" if settings.GROQ_API_KEY else "Missing GROQ_API_KEY in .env",
            },
            "ollama": {
                "configured": "yes" if bool(local_models) else "no",
                "detail": (
                    f"Detected models: {', '.join(local_models[:5])}"
                    if local_models
                    else f"No local models found at {settings.LOCAL_LLM_BASE_URL}"
                ),
            },
            "gemini": {
                "configured": "yes" if bool(settings.GOOGLE_API_KEY) else "no",
                "detail": "GOOGLE_API_KEY configured" if settings.GOOGLE_API_KEY else "Missing GOOGLE_API_KEY in .env",
            },
        }

    def _force_english_if_needed(self, raw_text: str, force_english: bool) -> str:
        if not force_english:
            return raw_text

        if detect_language(raw_text) == "en":
            return raw_text

        translated = force_translate_to_english(raw_text, engines=self.engines)
        if detect_language(translated) == "en":
            return translated

        logger.warning("Language enforcement failed after translation fallback")
        return translated

    def generate_tutorial_with_fallback(
        self,
        topic: str,
        length: str = "medium",
        tutorial_type: str = "technical",
        tags: List[str] | None = None,
        use_cache: bool = True,
        force_english: bool | None = None,
    ) -> Dict[str, Any]:
        """Generate tutorial using configured engine priority."""
        if not topic.strip():
            raise ValueError("topic cannot be empty")

        enforce_english = settings.FORCE_ENGLISH if force_english is None else bool(force_english)

        cache_key = f"tutorial_{topic}_{length}_{tutorial_type}_en_{int(enforce_english)}"
        if use_cache:
            cached = self.cache.get(cache_key)
            if cached and (not enforce_english or detect_language(str(cached.get("content", ""))) == "en"):
                logger.info("Tutorial cache hit for topic=%s", topic)
                return cached

        prompt = build_tutorial_prompt(topic=topic, length=length, tutorial_type=tutorial_type)
        start_global = time.perf_counter()
        last_exception: Exception | None = None
        attempt_details: List[str] = []
        local_models_snapshot = self.list_local_models()

        for engine in self.engines:
            try:
                logger.info("Generating tutorial topic=%s engine=%s", topic, engine)
                start_engine = time.perf_counter()
                prechecks: List[str] = []
                engine_low = str(engine).lower()
                if "groq" in engine_low and not settings.GROQ_API_KEY:
                    prechecks.append("GROQ_API_KEY missing")
                if "gemini" in engine_low and not settings.GOOGLE_API_KEY:
                    prechecks.append("GOOGLE_API_KEY missing")
                if "local" in engine_low or "ollama" in engine_low:
                    if not local_models_snapshot:
                        prechecks.append("No local models detected")

                result = generar_texto_motor(
                    prompt=prompt,
                    motor_texto=engine,
                    groq_key=settings.GROQ_API_KEY if "groq" in engine_low else None,
                    local_model=settings.LOCAL_LLM_MODEL,
                    local_base_url=settings.LOCAL_LLM_BASE_URL,
                    allow_cloud_fallback=not settings.LOCAL_LLM_STRICT,
                )
                engine_time = time.perf_counter() - start_engine
                if not result:
                    reason = "empty response"
                    if prechecks:
                        reason = f"{reason} ({'; '.join(prechecks)})"
                    attempt_details.append(f"{engine}: {reason}")
                    logger.warning("Engine returned no content: %s", engine)
                    continue

                enforced_result = self._force_english_if_needed(result, force_english=enforce_english)
                quality = analyze_tutorial_quality(enforced_result)
                tutorial_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

                tutorial_payload = {
                    "id": tutorial_id,
                    "timestamp": datetime.now().isoformat(),
                    "topic": topic,
                    "title": _extract_title(enforced_result, topic),
                    "content": enforced_result,
                    "sections": _extract_sections(enforced_result),
                    "platforms_published": [],
                    "urls": {},
                    "llm_used": _normalize_engine_name(engine),
                    "generation_time": round(time.perf_counter() - start_global, 2),
                    "engine_response_time": round(engine_time, 2),
                    "word_count": quality["word_count"],
                    "estimated_reads": 0,
                    "estimated_revenue": 0.0,
                    "performance_score": quality["score"],
                    "tags": tags or _suggest_tags(topic, enforced_result),
                    "quality": quality,
                    "tutorial_type": tutorial_type,
                    "length": length,
                }

                output_file = p("tutorials_generated", f"{tutorial_id}.md")
                with open(output_file, "w", encoding="utf-8") as handle:
                    handle.write(enforced_result)

                self.cache.set(cache_key, tutorial_payload)
                logger.info(
                    "Tutorial generated topic=%s engine=%s language=%s",
                    topic,
                    engine,
                    quality.get("language"),
                )
                return tutorial_payload
            except Exception as exc:
                last_exception = exc
                attempt_details.append(f"{engine}: exception {exc}")
                logger.warning("Generation failed on engine=%s: %s", engine, exc)
                continue

        details_text = " | ".join(attempt_details) if attempt_details else "no fallback details"
        if last_exception is not None:
            raise RuntimeError(f"All LLM engines failed. Last error: {last_exception}. Detail: {details_text}")
        raise RuntimeError(f"All LLM engines failed. Detail: {details_text}")

    def generate_tutorial(
        self,
        topic: str,
        engine: str | None = None,
        length: str = "medium",
        tutorial_type: str = "technical",
        force_english: bool | None = None,
    ) -> Dict[str, Any]:
        """Generate tutorial forcing one engine or full fallback chain."""
        if engine:
            previous_order = list(self.engines)
            self.engines = [engine] + [item for item in previous_order if item != engine]
            try:
                return self.generate_tutorial_with_fallback(
                    topic=topic,
                    length=length,
                    tutorial_type=tutorial_type,
                    use_cache=False,
                    force_english=force_english,
                )
            finally:
                self.engines = previous_order

        return self.generate_tutorial_with_fallback(
            topic=topic,
            length=length,
            tutorial_type=tutorial_type,
            force_english=force_english,
        )


def generate_tutorial(topic: str, **kwargs: Any) -> Dict[str, Any]:
    """Module-level wrapper for autonomous pipeline usage."""
    generator = TutorialGenerator()
    return generator.generate_tutorial_with_fallback(topic=topic, **kwargs)

