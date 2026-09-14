"""Сборщик экспрессов (пари) через OmniRoute.

Берёт value-bets, фильтрует кандидатов, отдаёт их AI-модели
и возвращает JSON-схему экспресса как есть.
"""

import json
import os

import requests
from ai.express_prompt import EXPRESS_SYSTEM_PROMPT

OMNI_URL = "http://127.0.0.1:20128/v1/chat/completions"
MODEL = "oc/big-pickle"
MIN_EV = 0.03
MIN_CONFIDENCE = 0.6
MIN_TRUST_SCORE = 0.7


class ExpressBuilder:
    def __init__(self, api_key=None, model=MODEL, timeout=90):
        self.api_key = api_key or os.environ.get("OMNI_KEY") or ""
        self.model = model
        self.timeout = timeout

    @staticmethod
    def _filter_candidates(value_bets):
        """Pre-filter: только кандидаты с EV >= 0.03, confidence >= 0.6, trust_score >= 0.7."""
        candidates = []
        for vb in value_bets:
            if float(vb.get("ev") or 0) < MIN_EV:
                continue
            if float(vb.get("confidence") or 0) < MIN_CONFIDENCE:
                continue
            if float(vb.get("trust_score") or 0) < MIN_TRUST_SCORE:
                continue
            candidates.append(vb)
        return candidates

    @staticmethod
    def _build_user_prompt(candidates, events_meta):
        lines = []
        lines.append("Value-bets (уже отфильтрованы: EV >= 0.03, confidence >= 0.6, trust_score >= 0.7):")
        for vb in candidates:
            event = vb.get("event") or vb.get("event_id") or "?"
            lines.append(
                "  - " + str(event) + " | " + str(vb.get("outcome")) + " @ "
                + str(vb.get("bookmaker")) + " odds=" + str(vb.get("odds"))
                + " EV=" + str(vb.get("ev")) + " deal_score=" + str(vb.get("deal_score"))
            )
        lines.append("")
        lines.append("Метаданные матчей (запрет корреляции: максимум 1 исход на матч):")
        lines.append(json.dumps(events_meta, ensure_ascii=False, indent=2))
        lines.append("")
        lines.append("Собери экспресс из 2-4 исходов, total_odds <= 50.0.")
        lines.append("Ответь строго по JSON-схеме из системного промпта. Без гарантий, без хайпа.")
        return "\n".join(lines)

    def build(self, value_bets, events_meta):
        candidates = self._filter_candidates(value_bets)
        if len(candidates) < 2:
            return {"legs": [], "reason": "insufficient value-bets"}

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = "Bearer " + self.api_key
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": EXPRESS_SYSTEM_PROMPT},
                {"role": "user", "content": self._build_user_prompt(candidates, events_meta)},
            ],
            "temperature": 0.2,
            "max_tokens": 800,
            "response_format": {"type": "json_object"},
        }
        r = requests.post(OMNI_URL, headers=headers, json=payload, timeout=self.timeout)
        if r.status_code != 200:
            raise RuntimeError("OmniRoute HTTP " + str(r.status_code) + ": " + r.text[:300])
        data = r.json()
        content = data["choices"][0]["message"].get("content", "").strip()
        return json.loads(content)