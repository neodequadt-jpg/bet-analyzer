# BET-ANALYZER — Codex Agent Instructions

## Workflow (ARTEM-Lite)

Каждый патч проходит этот цикл. Не пропускать.

1. **Verify reality** — `rg`/`cat`/`curl` перед изменением. Не предполагать.
2. **Apply patch** — один атомарный шаг, одна область.
3. **Compile check** — `python3 -m py_compile <file>` после каждого Python-патча.
4. **Test** — `./run_tests.sh` (unit); `./run_tests.sh -m integration` (integration).
5. **EVR** — если патч меняет поведение: написать EVR-NNNN.md в validation/.
   Non-behavioral изменения (typo, .gitignore, docs) — EVR не нужен.
6. **Commit** — один шаг = один коммит. Без «заодно».

## DSH — только batch/cron

DSH — headless-агент для scheduled-задач (bonus-cron, nightly sync).
Для интерактивной работы — **только Codex**.

Если нужно вызвать DSH из Codex:
- Перед: `cp <file> <file>.before-dsh`
- В prompt: `"НЕ применяй. Выведи diff."`
- После: `git status --porcelain` — проверить что изменилось
- Откат: `git checkout -- <file>`

## OmniRoute

- Proxy: `127.0.0.1:20128`
- Combo primary: `bet-edge-primary` → deepseek-v4-flash ($0.09/$0.18) → glm-5.3-flash ($0.04/$0.90)
- Combo free: `bet-edge-free` → cfp/deepseek-v4-flash → cfp/glm-5.2 → oc/deepseek-v4-flash-free → cfp/qwen2.5-coder
- **Groq/Gemini модели не работают через responses API** — только chat/completions
- **OmniRoute down → задача блокируется.** Не молча падать.

## Data Sources

| Source | Type | Key needed | What it gives |
|--------|------|-----------|---------------|
| Fonbet API | ЦУПИС БК | No | RPL/KHL/MMA odds |
| Smarkets | Exchange | No | Low-margin calibration odds |
| TheOddsAPI | International | ODDS_API_KEY (free) | Pinnacle (sharp book) EPL/Nations League/+ |
| footbolno.ru | Results | No (CC BY 4.0) | Match results for resolver |
| metaratings.ru | Bonuses | No | 33+ bonus offers |

## Monetization

- Free: /bonuses, /stats, /live, /backtest, /subscribe
- Premium (200⭐/month): /value, /signals, /plan, /express, /report
- Gating: `_premium_gate()` in tg_bot.py
- Payment: Telegram Stars via `cmd_subscribe()`

## Constraints

- git = source of truth. BOOTSTRAP/STATE.md — summary, не истина.
- Не редизайнить ядро. Не переименовывать концепты.
- Не пропускать Research. Не пропускать Validation.
- requests.Session(trust_env=False) — всегда.
- .env / ключи / токены — в .gitignore. Только .env.example.

## Тесты

- Unit:        ./run_tests.sh
- Integration: ./run_tests.sh -m integration
- Baseline:    319 passed, 7 skipped, 2 deselected

## Состояние проекта

- resolve_all(): 90/90 resolved, ROI +68% flat, +55% Kelly
- Active bonuses: 12 (167,600₽ total) — auto-synced from metaratings
- Pinnacle: wired via TheOddsAPI (EPL + Nations League)
- Premium gating: implemented
- Smarkets: timeout issues (proxy-related)

## Backlog

- G-0015: plan_builder ✅ (implemented)
- ~~Fix Smarkets proxy~~ ✅ (trust_env=False, deadline 40s, jitter)
- ~~Add TheOddsAPI sports~~ ✅ (Bundesliga, La Liga, Serie A wired)
- ~~Nations League C/D filter~~ ✅ (excluded in fonbet_api + theoddsapi_provider)
