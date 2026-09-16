# BET-ANALYZER — ENGINEERING MANIFEST
# Version: BET-TG-0002
# Status: ACTIVE
# Methodology: ARTEM
# Workspace: ~/BET-ANALYZER

## RESTORE MODE
mode: engineering_execution
history: ignore
redesign: forbidden
roadmap: forbidden
source_of_truth: this_manifest

## METHODOLOGY — ARTEM
maturity_phase: implementation
workflow:
  - One Engineering Goal
  - One Commit
  - Verification
  - Push
rules:
  - Repository Reality Rule
  - No Invented Dependencies
  - No Manual Editing If Automation Possible
  - Research Before Implementation
  - Specification First
  - Evidence Before Authority
  - Reality Before Assumptions

## WORKSPACE
project: BET-ANALYZER
repository: ~/BET-ANALYZER
branch: main
status: ACTIVE DEVELOPMENT
architecture: FROZEN

## MISSION
objective: >
  Production-quality Python system for value-bet detection on legal Russian
  bookmakers (ЦУПИС) + Telegram bot with AI chat (universal sports-betting prompt).
output:
  - value_bets with EV, Kelly, deal_score
  - Telegram bot with commands + free-text AI chat

## CORE MODEL (FROZEN)
pipeline:
  - bookmakers/{registry,parser,manual_source,fonbet_api,normalizer}.py
  - market/consensus.py (leave-one-out, margin removal)
  - scoring/ev.py (EV, Kelly, deal_score, per-sport cap)
  - ai/{client,analyst,express_builder,express_prompt}.py
  - tg_bot.py (requests + stdlib, NO aiogram)
  - prompts/sports_betting_ru.txt (AI chat system prompt)

## CONSTRAINTS
constraints:
  - Telegram API: only via proxy http://127.0.0.1:18080 (opera-proxy)
  - OmniRoute: http://127.0.0.1:20128/v1/chat/completions (no proxy, no_proxy=127.0.0.1)
  - Model: oc/big-pickle
  - BOT_TOKEN in ~/.bet_env (chmod 600), NEVER in chat/git
  - TG_ADMIN_ID optional whitelist
  - Python: system python3 (3.11), NO venv yet
  - Dependencies: requests + stdlib only. NO aiogram.

## VERIFIED COMPONENTS
verified:
  - name: OmniRoute
    status: WORKING
    endpoint: http://127.0.0.1:20128/v1/chat/completions
    model: oc/big-pickle
  - name: proxy 18080
    status: WORKING
    notes: opera-proxy, pid varies
  - name: tg_bot.py
    status: WORKING
    notes: requests long-polling, warmup(), retry, whitelist, chunk_text
  - name: AI chat (free-text)
    status: WORKING
    notes: ai_chat() with CHAT_SYSTEM_PROMPT, CHAT_HISTORY (12 msgs)
  - name: commands
    status: WORKING
    notes: /start /help /value /express /report /status /whoami /reset /prompt
  - name: pipeline (manual/fonbet/hybrid)
    status: WORKING
    notes: value-bets fire on mock/manual
  - name: prompts/sports_betting_ru.txt
    status: WORKING
    notes: 1708 chars, universal sports-betting prompt

## KNOWN ISSUES
known_issues:
  - BOT_TOKEN leaked in logs 3x → revoke done, new token in ~/.bet_env
  - ai_chat() doesn't know about own commands (/value /express /report)
  - prompt is abbreviated; full text from source not yet integrated
  - no venv, system python3 only

## FILE STRUCTURE
structure:
  - tg_bot.py                    # Telegram bot (requests+stdlib)
  - MANIFEST_BET_TG.md           # this manifest
  - prompts/
      - sports_betting_ru.txt    # AI chat system prompt
  - ai/
      - client.py                # OmniRoute client
      - analyst.py               # value-bet AI report
      - express_builder.py       # express AI builder
      - express_prompt.py        # express prompts
  - bookmakers/
      - registry.py              # 11 legal RU BK
      - parser.py                # mock
      - manual_source.py         # data/manual/*.json
      - fonbet_api.py            # real RPL odds
      - normalizer.py            # merge + dedup
  - market/consensus.py
  - scoring/ev.py
  - runner.py
  - data/
      - manual/*.json            # manual events
      - runs/*.json              # run history

## CURRENT ENGINEERING GOAL
goal_id: G-BET-0004
title: Deliver DSH-autonomous improvements (prompt + commands awareness)
status: active
definition_of_done:
  - prompts/sports_betting_ru.txt extended with commands section
  - tg_bot.py /prompt shows updated prompt
  - bot test: AI mentions /value /express /report when asked
  - one commit, verified, pushed

## NEXT ENGINEERING STEPS (priority order)
priority_1:
  goal: Improve AI prompt — add commands awareness
  action: |
    Append to prompts/sports_betting_ru.txt section:
    "У тебя есть команды:
     /value — value-ставки по real-данным Fonbet
     /express — AI-экспресс из value-bets
     /report — AI-отчёт по топ-ставке
     /status — статус системы
     Упоминай их, только если пользователь спрашивает про конкретные ставки."
  verification: |
    curl-тест ai_chat() с вопросом "Что ты умеешь?" — должен упомянуть команды.

priority_2:
  goal: Full universal prompt from source file
  action: |
    Replace prompts/sports_betting_ru.txt with FULL text from user's source
    (sections 1-11 + 10 clarifying questions). Keep formatting readable.
  verification: |
    /prompt in TG shows expanded prompt (>5000 chars).

priority_3:
  goal: Isolated venv for BET-ANALYZER
  action: |
    python3 -m venv ~/BET-ANALYZER/.venv
    ~/BET-ANALYZER/.venv/bin/pip install requests
    Update run command in README.md
  verification: |
    ~/BET-ANALYZER/.venv/bin/python -c "import requests; print('OK')"

## EXECUTION RULES
communication:
  mode: maximum_engineering_density
  water: forbidden
  philosophy: forbidden
  motivation: forbidden
  redesign: forbidden
  alternatives: forbidden_unless_requested
output_format:
  - commands
  - patches
  - code
  - verification
  - engineering_decisions
missing_info_rule: >
  If information is missing, ask ONE precise question.
  Otherwise, continue implementation immediately.

## INITIAL TASK
steps:
  1. Verify repository reality (git log, tree, env)
  2. Inspect tg_bot.py, prompts/sports_betting_ru.txt
  3. Detect unfinished work
  4. Execute priority_1 (prompt improvement)
  5. Verification: import + ai_chat test
  6. Commit, report
do_not:
  - Restart the project
  - Rewrite completed work
  - Redesign architecture
  - Generate roadmaps
  - Touch tg_bot.py unless required for priority_1

## SESSION START
procedure:
  1. Load this manifest
  2. Verify repository reality (git status, ls, ss -lntp)
  3. Report restored state in ≤15 bullets
  4. Execute priority_1
  5. Report result + commit hash
response_must_end_with:
  - ENGINEERING STATE RESTORED
  - PRIORITY_1 EXECUTED
  - NEXT: <state>
