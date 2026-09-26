"""AI analyst via OmniRoute. DeepSeek-style prompt -> natural language report."""
import json
import os

import requests

OMNI_URL = "http://127.0.0.1:20128/v1/chat/completions"
DEFAULT_MODEL = "gemini/gemini-3.1-flash-lite-preview"

SYSTEM_PROMPT = (
    "You are a professional analyst of the Russian bookmaker market. "
    "You read market consensus, interpret EV and Kelly, warn about risks. "
    "Advice must be calm, no hype. Never guarantee wins."
)


class ValueBetAnalyst:
    def __init__(self, api_key=None, model=DEFAULT_MODEL, timeout=90):
        self.api_key = api_key or os.environ.get("OMNI_KEY") or "sk-84454d30f22bfcb1-5d2256-72fbd6b3"
        self.model = model
        self.timeout = timeout

    def build_user_prompt(self, event, consensus, value_bets):
        lines = []
        lines.append("Match: " + str(event.get("home")) + " vs " + str(event.get("away")) + " (" + str(event.get("league", "?")) + ")")
        lines.append("")
        lines.append("Market consensus (true probability, margin removed):")
        for out, c in consensus.items():
            prob = c.get("consensus_prob", 0) * 100
            lines.append("  " + out.ljust(6) + " prob=" + str(round(prob,1)) + "% fair_odds=" + str(c.get("consensus_odds")) + " conf=" + str(c.get("confidence",0)) + " sources=" + str(c.get("sources",0)))
        lines.append("")
        if value_bets:
            lines.append("Value-bets found (odds > fair):")
            for vb in value_bets:
                lines.append("  - " + vb["outcome"] + " @ " + vb["bookmaker"] + " odds=" + str(vb["odds"]) + " EV=" + str(round(vb["ev"]*100,1)) + "% Kelly=" + str(round(vb["kelly"]*100,2)) + "% score=" + str(vb["deal_score"]))
        else:
            lines.append("No value-bets found. Market is efficient.")
        lines.append("")
        lines.append("Answer in Russian, analyst tone, no markdown tables.")
        lines.append("Structure: 1) Should you bet? 2-3 sentences. 2) Stake size (Kelly %). 3) Risks.")
        lines.append("Max 4 paragraphs. No guarantees.")
        return "\n".join(lines)

    def analyze(self, event, consensus, value_bets):
        prompt = self.build_user_prompt(event, consensus, value_bets)
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = "Bearer " + self.api_key
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 800,
        }
        r = requests.post(OMNI_URL, headers=headers, json=payload, timeout=self.timeout)
        if r.status_code != 200:
            raise RuntimeError("OmniRoute HTTP " + str(r.status_code) + ": " + r.text[:300])
        data = r.json()
        return data["choices"][0]["message"].get("content", "").strip()
