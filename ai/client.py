"""
AI-клиент через OmniRoute.
Тот же endpoint, что в AVITO-PRINTER-V2.
"""

import json
import os
import re
from typing import Any

import requests


OMNI_URL = "http://127.0.0.1:20128/v1/chat/completions"
MODEL = "oc/big-pickle"


class BettingAI:
    def __init__(self, api_key: str | None = None, timeout: int = 120):
        # OmniRoute может работать без auth. Пустой ключ = no auth.
        self.api_key = api_key or os.environ.get("OMNI_KEY") or ""
        self.timeout = timeout

    @staticmethod
    def _extract_json(content: str) -> dict[str, Any]:
        if not content:
            raise ValueError("empty content")
        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.IGNORECASE)
            content = re.sub(r"\s*```$", "", content)
        return json.loads(content.strip())

    def analyze_event_context(
        self,
        home: str,
        away: str,
        league: str,
        news_text: str = "",
    ) -> dict[str, Any]:
        prompt = f"""
Ты аналитик спортивных событий. Матч: {home} — {away} ({league}).

Известный контекст:
{news_text or "(нет дополнительных данных)"}

Оцени риск ставки. Верни строго JSON:
{{
  "form_home": "сильная" | "средняя" | "слабая" | "unknown",
  "form_away": "сильная" | "средняя" | "слабая" | "unknown",
  "injuries_home": ["список травм или пусто"],
  "injuries_away": ["список травм или пусто"],
  "motivation_home": "высокая" | "обычная" | "низкая" | "unknown",
  "motivation_away": "высокая" | "обычная" | "низкая" | "unknown",
  "risk_flags": ["список подозрительных сигналов"],
  "risk_score": 0
}}
risk_score: 0 = нет рисков, 100 = максимальный риск.
Не выдумывай данные. Если не знаешь — ставь "unknown".
"""
        r = requests.post(
            OMNI_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
                "max_tokens": 500,
                "response_format": {"type": "json_object"},
            },
            timeout=self.timeout,
        )
        if r.status_code != 200:
            raise RuntimeError(f"OmniRoute HTTP {r.status_code}: {r.text[:300]}")
        data = r.json()
        choice = data["choices"][0]
        if choice.get("finish_reason") != "stop":
            raise RuntimeError(f"finish_reason={choice.get('finish_reason')}")
        return self._extract_json(choice["message"].get("content"))
