#!/usr/bin/env python3
"""llm.py — duenne Ollama-Anbindung fuer die Agenten (chat + structured JSON)."""

from __future__ import annotations

import json
import re
from typing import Any

import requests

OLLAMA = "http://localhost:11434"


def chat(model: str, system: str, user: str, *, temperature: float = 0.85,
         num_ctx: int = 16384, num_predict: int = 220,
         extra: dict[str, Any] | None = None, timeout: int = 600) -> str:
    """Ein Chat-Call. Gibt den bereinigten Antworttext zurueck."""
    opts: dict[str, Any] = {"temperature": temperature, "num_ctx": num_ctx,
                            "num_predict": num_predict}
    if extra:
        opts.update(extra)
    payload: dict[str, Any] = {
        "model": model, "stream": False, "options": opts,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
    }
    if model.startswith("qwen3"):
        payload["think"] = False
    r = requests.post(f"{OLLAMA}/api/chat", json=payload, timeout=timeout)
    r.raise_for_status()
    text = r.json().get("message", {}).get("content", "").strip()
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    return text


def chat_json(model: str, system: str, user: str, schema: dict[str, Any], *,
              temperature: float = 0.4, timeout: int = 600) -> dict[str, Any]:
    """Strukturierter Call: erzwingt JSON nach Schema (Ollama format=)."""
    payload: dict[str, Any] = {
        "model": model, "stream": False, "format": schema,
        "options": {"temperature": temperature, "num_ctx": 16384,
                    "num_predict": 500},
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
    }
    if model.startswith("qwen3"):
        payload["think"] = False
    r = requests.post(f"{OLLAMA}/api/chat", json=payload, timeout=timeout)
    r.raise_for_status()
    raw = r.json().get("message", {}).get("content", "").strip()
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    m = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    return json.loads(m.group(0)) if m else {}
