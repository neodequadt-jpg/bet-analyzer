# DEMO-0002: ExpressBuilder via DSH + OmniRoute

Status: VERIFIED
Date: 2026-09-14

## Goal
DSH (DeepSeek Harness) как coding agent написал ai/express_builder.py
по спеке .dsh/tasks/express_builder.md, следуя ARTEM.
Full path: ExpressBuilder -> OmniRoute -> oc/big-pickle -> JSON.

## Setup
- DSH 0.1.5-rc.1 (npm, Node 22.23.2 via nvm)
- Provider: omniroute (openai-completions, baseURL http://127.0.0.1:20128/v1)
- apiKeyEnv: OMNIROUTE_API_KEY (placeholder, OmniRoute auth не требует)
- no_proxy=127.0.0.1,localhost (OmniRoute через loopback)

## ARTEM flow
1. Spec-First: .dsh/tasks/express_builder.md (deliverable + constraints + acceptance)
2. DSH прочитал существующие файлы (analyst.py, ev.py, parser.py)
3. Написал ai/express_prompt.py + ai/express_builder.py
4. py_compile -> exit 0
5. Independent verification: imports только os/json/requests/ai.express_prompt

## Evidence (synthetic test)
Input: 3 synthetic value-bets (EV 0.055/0.042/0.038)

Output from oc/big-pickle:
  legs = 3 (Зенит-Ростов, ЦСКА-Локомотив, Краснодар-Ахмат)
  total_odds = 7.3815  (2.10 * 1.90 * 1.85 - verно)
  total_ev   = 0.1411  ((1.055 * 1.042 * 1.038) - 1 - верно)
  stake_pct  = 1.0
  rationale  = человеко-читаемое обоснование

## Real data result (current RPL)
value-bets >= 2: NO (only 1: Спартак-Факел away @ Лига Ставок 9.5, EV+3.3%)
Correct behavior: {"legs": [], "reason": "insufficient value-bets"}

## Files
- ai/express_prompt.py         (EXPRESS_SYSTEM_PROMPT)
- ai/express_builder.py        (ExpressBuilder.build)
- .dsh/tasks/express_builder.md (spec)
- ~/.dsh/settings.yaml          (provider config)

## Notes
- DSH требует apiKeyEnv даже если backend без auth — placeholder решает.
- no_proxy=127.0.0.1 обязателен, иначе Node подхватывает system proxy 8118.
- AI корректно посчитал total_odds и total_ev по входным данным.
