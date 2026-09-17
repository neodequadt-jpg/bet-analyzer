"""Express builder with value-bets + fallback to market consensus."""

import json
import os

import requests
from ai.express_prompt import EXPRESS_SYSTEM_PROMPT, EXPRESS_CONSENSUS_PROMPT

OMNI_URL = "http://127.0.0.1:20128/v1/chat/completions"
MODEL = "gemini/gemini-3.1-flash-lite-preview"
MIN_EV = 0.03
MIN_CONFIDENCE = 0.6
MIN_TRUST_SCORE = 0.7


class ExpressBuilder:
    def __init__(self, api_key=None, model=MODEL, timeout=45):
        self.api_key = api_key or os.environ.get("OMNI_KEY") or "sk-84454d30f22bfcb1-5d2256-72fbd6b3"
        self.model = model
        self.timeout = timeout

    @staticmethod
    def _filter_candidates(value_bets):
        out = []
        for vb in value_bets:
            if float(vb.get("ev") or 0) < MIN_EV:
                continue
            if float(vb.get("confidence") or 0) < MIN_CONFIDENCE:
                continue
            if float(vb.get("trust_score") or 0) < MIN_TRUST_SCORE:
                continue
            out.append(vb)
        return out

    @staticmethod
    def _build_user_prompt(candidates, events_meta, mode):
        lines = []
        if mode == "value":
            lines.append("Value-bets (EV>=0.03, conf>=0.6, trust>=0.7):")
        else:
            lines.append("Market-consensus candidates (no strict EV filter):")
        for vb in candidates:
            eid = vb.get("event_id") or vb.get("event") or "?"
            meta = events_meta.get(eid, {})
            label = f"{meta.get('home', vb.get('event', '?'))} vs {meta.get('away', '')}".strip()
            lines.append(
                "  - " + label + " | " + str(vb.get("outcome")) + " @ "
                + str(vb.get("bookmaker")) + " odds=" + str(vb.get("odds"))
                + " EV=" + str(vb.get("ev", 0)) + " deal_score=" + str(vb.get("deal_score", 0))
            )
        lines.append("")
        lines.append("Match metadata (no correlation: max 1 outcome per match):")
        lines.append(json.dumps(events_meta, ensure_ascii=False, indent=2))
        lines.append("")
        lines.append("Build parlay of 2-4 legs, total_odds <= 50.0.")
        lines.append("Reply strictly with JSON schema from system prompt.")
        return "\n".join(lines)

    def build(self, value_bets, events_meta, fallback_candidates=None):
        """
        value_bets: candidates from scoring.ev (may be empty)
        events_meta: {event_id: {home, away, league}}
        fallback_candidates: if value-bets < 2, use these (best-odds from consensus)
        """
        value_candidates = self._filter_candidates(value_bets)
        value_event_ids = {vb.get("event_id") for vb in value_candidates if vb.get("event_id")}

        if len(value_candidates) >= 2 and len(value_event_ids) >= 2:
            candidates = value_candidates
            mode = "value"
        elif fallback_candidates and len(fallback_candidates) >= 2:
            candidates = fallback_candidates[:8]
            mode = "consensus"
            print("[express_builder] fallback: consensus picks (" + str(len(candidates)) + ")", flush=True)
        else:
            return {"legs": [], "reason": "insufficient value-bets"}

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = "Bearer " + self.api_key
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": EXPRESS_CONSENSUS_PROMPT if mode == "consensus" else EXPRESS_SYSTEM_PROMPT},
                {"role": "user", "content": self._build_user_prompt(candidates, events_meta, mode)},
            ],
            "temperature": 0.2,
            "max_tokens": 800,
            "response_format": {"type": "json_object"},
        }
        r = requests.post(OMNI_URL, headers=headers, json=payload, timeout=self.timeout)
        if r.status_code != 200:
            raise RuntimeError("OmniRoute HTTP " + str(r.status_code) + ": " + r.text[:300])
        data = r.json()
        choice = (data.get("choices") or [{}])[0] if data.get("choices") else {}
        message = choice.get("message") or {}
        raw = message.get("content")

        # Content may be None (provider flake), string, or already a dict
        if raw is None:
            # Some providers return content in reasoning_content, or empty
            raw = message.get("reasoning_content") or ""

        if isinstance(raw, dict):
            # Already parsed JSON object
            return raw

        content = str(raw).strip()
        if not content:
            return {"legs": [], "reason": "empty AI response"}

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Try to find a JSON object inside the text
            import re as _re
            m = _re.search(r"\{.*\}", content, _re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(0))
                except json.JSONDecodeError:
                    pass
            return {"legs": [], "reason": "AI returned non-JSON: " + content[:120]}
