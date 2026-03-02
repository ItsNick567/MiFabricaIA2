import os
import warnings
import requests
import streamlit as st

warnings.filterwarnings(
    "ignore",
    message=r".*google\.generativeai.*",
    category=FutureWarning,
)
import google.generativeai as genai


def generar_texto_gemini(prompt, model_name="models/gemini-1.5-flash"):
    try:
        model = genai.GenerativeModel(model_name)
        r = model.generate_content(prompt)
        return getattr(r, "text", None)
    except Exception as e:
        if "429" in str(e) or "quota" in str(e).lower():
            st.error("❌ Cuota Gemini agotada")
        return None


def generar_texto_groq(prompt, api_key):
    if not api_key:
        return None
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        data = {
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.55,
            "max_tokens": 2200,
        }
        r = requests.post(url, headers=headers, json=data, timeout=60)
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"]
        return None
    except Exception:
        return None


def _norm_base_url(url: str | None) -> str:
    v = (url or "").strip() or "http://127.0.0.1:11434"
    return v.rstrip("/")


def listar_modelos_locales(base_url: str | None = None) -> list:
    base = _norm_base_url(base_url or os.getenv("LOCAL_LLM_BASE_URL", "http://127.0.0.1:11434"))
    try:
        r = requests.get(f"{base}/api/tags", timeout=6)
        if r.status_code != 200:
            return []
        data = r.json() if r.text else {}
        models = data.get("models", []) if isinstance(data, dict) else []
        out = []
        for m in models:
            if isinstance(m, dict):
                name = str(m.get("name") or m.get("model") or "").strip()
                if name:
                    out.append(name)
            elif isinstance(m, str):
                ms = m.strip()
                if ms:
                    out.append(ms)
        return sorted(list(dict.fromkeys(out)))
    except Exception:
        return []


def generar_texto_local(
    prompt,
    model_name: str | None = None,
    base_url: str | None = None,
    temperature: float = 0.45,
    max_tokens: int = 2400,
    timeout_s: int = 240,
):
    """
    Motor local principal vía Ollama.
    Soporta:
    - POST /api/generate (nativo Ollama)
    - POST /v1/chat/completions (compat OpenAI local: LM Studio/Open WebUI/Ollama v1)
    """
    model = (model_name or os.getenv("LOCAL_LLM_MODEL", "qwen2.5:14b")).strip()
    base = _norm_base_url(base_url or os.getenv("LOCAL_LLM_BASE_URL", "http://127.0.0.1:11434"))
    if not model:
        return None

    # 1) Ollama nativo
    try:
        payload = {
            "model": model,
            "prompt": str(prompt or ""),
            "stream": False,
            "options": {
                "temperature": float(temperature),
                "top_p": 0.9,
                "repeat_penalty": 1.05,
                "num_ctx": 8192,
                "num_predict": int(max_tokens),
            },
        }
        r = requests.post(f"{base}/api/generate", json=payload, timeout=timeout_s)
        if r.status_code == 200 and r.text:
            data = r.json()
            out = str(data.get("response") or "").strip()
            if out:
                return out
    except Exception:
        pass

    # 2) Compat OpenAI local (fallback)
    try:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": str(prompt or "")}],
            "temperature": float(temperature),
            "max_tokens": int(max_tokens),
        }
        r = requests.post(f"{base}/v1/chat/completions", json=payload, timeout=timeout_s)
        if r.status_code == 200 and r.text:
            data = r.json()
            choices = data.get("choices", []) if isinstance(data, dict) else []
            if choices and isinstance(choices[0], dict):
                msg = choices[0].get("message", {}) or {}
                out = str(msg.get("content") or "").strip()
                if out:
                    return out
    except Exception:
        pass

    return None


def generar_texto_motor(
    prompt,
    motor_texto: str = "Gemini (GRATIS)",
    groq_key: str | None = None,
    local_model: str | None = None,
    local_base_url: str | None = None,
    allow_cloud_fallback: bool = True,
):
    """
    Router único de texto:
    - `Local (Ollama)` usa solo local por defecto si allow_cloud_fallback=False.
    - `Groq` y `Gemini` mantienen comportamiento actual con fallback configurable.
    """
    motor = str(motor_texto or "").lower()
    is_local = ("local" in motor) or ("ollama" in motor) or ("lm studio" in motor)
    is_groq = "groq" in motor
    is_gemini = "gemini" in motor

    if is_local:
        out = generar_texto_local(prompt, model_name=local_model, base_url=local_base_url)
        if out:
            return out
        if not allow_cloud_fallback:
            return None

    if is_groq:
        out = generar_texto_groq(prompt, groq_key)
        if out:
            return out
        if not allow_cloud_fallback:
            return None
        out = generar_texto_gemini(prompt)
        if out:
            return out
        return generar_texto_local(prompt, model_name=local_model, base_url=local_base_url)

    if is_gemini:
        out = generar_texto_gemini(prompt)
        if out:
            return out
        if not allow_cloud_fallback:
            return None
        out = generar_texto_groq(prompt, groq_key)
        if out:
            return out
        return generar_texto_local(prompt, model_name=local_model, base_url=local_base_url)

    # Motor no reconocido: prioriza local
    out = generar_texto_local(prompt, model_name=local_model, base_url=local_base_url)
    if out:
        return out
    out = generar_texto_groq(prompt, groq_key)
    if out:
        return out
    return generar_texto_gemini(prompt)
