# DEMO-0003: Telegram bot via DSH

Status: VERIFIED
Date: 2026-09-14

## Goal
DSH написал tg_bot.py по спеке ~/.dsh/tasks/tg_bot.md, следуя ARTEM.

## Constraints satisfied
- No new dependencies: only os, sys, json, time, html, requests + project modules
- No aiogram/telebot/asyncio/threading (verified by grep — no real imports)
- Existing files not modified

## Commands implemented
- /start, /help — welcome
- /value    — value-bets summary (fonbet+manual+consensus+EV)
- /express  — ExpressBuilder on all value-bets
- /report   — ValueBetAnalyst natural-language
- /status   — uptime + pipeline availability

## Verified
- py_compile: exit 0
- Missing BOT_TOKEN: exit 1 + stderr message
- Offline import: OK, all 5 attributes present (cmd_value/express/report/status, build_pipeline)

## Run
export BOT_TOKEN='<token from @BotFather>'
export TG_ADMIN_ID='<your chat_id>'   # optional whitelist
export no_proxy=127.0.0.1,localhost
~/AVITO-PRINTER-V2/.venv/bin/python tg_bot.py
