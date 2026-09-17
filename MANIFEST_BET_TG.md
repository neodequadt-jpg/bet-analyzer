# BET-ANALYZER — ENGINEERING MANIFEST
# Version: BET-TG-0003
# Status: ACTIVE
# Methodology: ARTEM
# Workspace: ~/BET-ANALYZER
# Previous: BET-TG-0002 (see backup)

## RESTORE MODE
mode: engineering_execution
redesign: forbidden
roadmap: forbidden
source_of_truth: this_manifest

## METHODOLOGY — ARTEM
workflow:
  - One Engineering Goal
  - One Commit
  - Verification
  - Report
rules:
  - Repository Reality Rule
  - No Invented Dependencies
  - Evidence Before Authority
  - Reality Before Assumptions

## WORKSPACE
project: BET-ANALYZER
repository: ~/BET-ANALYZER
branch: main
status: ACTIVE DEVELOPMENT
architecture: FROZEN

## AI BACKEND (CURRENT)
provider: OmniRoute v3.8.50 (http://127.0.0.1:20128/v1)
upstream: Gemini (Google AI Studio)
model: gemini/gemini-3.1-flash-lite-preview  # non-reasoning, fast
auth: "Bearer sk-84454d30f22bfcb1-5d2256-72fbd6b3" (pipeline key)
proxy: http://127.0.0.1:18080 (opera-proxy, TR exit) — required for Google API
fallback_env: OMNI_KEY in ~/.bet_env
dead_providers:
  - oc/big-pickle (OpenCode free, 403 since 2026-09-17)
  - cfp/* (Chrome can't reach Cloudflare via proxy)
  - tllm/* (Vercel blocks RU IP)
  - aug/*, dva/*, zc/*, ddgw/*, felo/*, pepper/*

## BOT RUNTIME
bot: @bet_analyzer_anrhytm_bot (id 8165315037)
BOT_TOKEN: stored in ~/.bet_env (chmod 600), rotated on compromise
TG_ADMIN_ID: 3 users in whitelist (see ~/.bet_env)
proxy_env for bot: http_proxy=http://127.0.0.1:18080 (NOT 8118, NOT socks 9050)
tg_bot.py: stdlib + requests, NO aiogram

## VERIFIED COMPONENTS
verified:
  - AI chat (Gemini): WORKING — reply ~150-300 chars, RU+EN
  - RAG live-data injection: WORKING — fetches Fonbet events on "express + sport"
  - /live <sport> <hours>: WORKING — 10 events, MSK time, odds
  - /value pipeline: WORKING — RONBET+manual → consensus → EV
  - /express, /report: WORKING (via Gemini)
  - inline keyboard (3x2 + lang): WORKING
  - i18n RU/EN: WORKING (menus, welcome, AI directive at END of prompt)
  - rate limit: WORKING — 20 req/min per chat, token bucket
  - whitelist: WORKING — 3 users, friendly rejection
  - tests: 66 passed (48 in test_tg_chat.py + 18 in test_tg_resilience.py)
  - sanitize error: WORKING — redacts BOT_TOKEN in logs

## CONSTRAINTS
constraints:
  - No aiogram (requests + stdlib only)
  - OmniRoute must run with proxy 18080 (env -u all_proxy first)
  - Gemini free tier: 15 req/min → cooldown on burst, use lite-preview
  - DSH uses gemini/gemini-3.1-flash-lite-preview (updated in ~/.dsh/settings.yaml)
  - Test runner: ./run_tests.sh (uses AVITO venv pytest)
  - BOT_TOKEN never in chat/git/logs

## FILE STRUCTURE
structure:
  - tg_bot.py                    # bot + AI chat + commands
  - MANIFEST_BET_TG.md           # this file
  - prompts/sports_betting_ru.txt # 7445-char universal prompt
  - ai/client.py, analyst.py, express_builder.py
  - bookmakers/fonbet_api.py, fonbet_extended.py, manual_source.py, normalizer.py
  - market/consensus.py
  - scoring/ev.py
  - tests/{test_tg_chat.py, test_tg_resilience.py, conftest.py}
  - run_tests.sh
  - data/{manual/, cache/, runs/}

## CURRENT GOAL
goal_id: G-BET-0005
title: APScheduler-style daily report at 09:00 MSK
status: active
definition_of_done:
  - Send value-bets report to all whitelist users at 09:00 MSK
  - stdlib-only (no apscheduler package)
  - time check in main() loop
  - 2 new tests
  - one commit, verified

## NEXT STEPS (roadmap)
priority_1: daily report at 09:00 MSK (in progress)
priority_2: .venv for BET-ANALYZER (isolate from AVITO)
priority_3: inline keyboard inside /value (per-match detail)
priority_4: more sports in /live (basketball, volleyball)

## EXECUTION RULES
communication:
  mode: maximum_engineering_density
  water: forbidden
output_format: commands, patches, code, verification
missing_info_rule: ask ONE precise question, else continue

## SESSION START
procedure:
  1. Load this manifest
  2. Verify reality (git log, grep, ./run_tests.sh)
  3. Report restored state in ≤15 bullets
  4. Execute priority_1
  5. Report result + commit hash
response_must_end_with:
  - ENGINEERING STATE RESTORED
  - PRIORITY_N EXECUTED
