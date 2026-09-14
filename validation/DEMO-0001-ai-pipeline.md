# DEMO-0001: AI pipeline (Python + OmniRoute + DeepSeek-style prompt)

Status: VERIFIED
Date: 2026-09-14

## Goal

Show end-to-end: Python collects real RPL odds, computes value-bets,
then OmniRoute + big-pickle generates a human-readable analyst report.

## Pipeline

    Fonbet API  ->  merge  ->  consensus  ->  EV/Kelly  ->  AI-аналитик
    (Python)        (Python)  (Python)      (Python)      (OmniRoute)

## Evidence

Command:

    PYTHONPATH=. ~/AVITO-PRINTER-V2/.venv/bin/python demo_ai_pipeline.py

Output:

    [1/4] Fetch Fonbet RPL odds...
          fonbet raw: 8
    [2/4] Load manual multi-BK data...
          manual raw: 16
    [3/4] Merge + consensus + EV...
          grouped: 8
          target: Спартак vs Факел (4 BK)
          value-bets: 1
    [4/4] AI analyst via OmniRoute...
          model: oc/big-pickle | auth: False

    AI REPORT: Спартак vs Факел
    ---
    1) Should you bet? Formal EV +3.3%, in range of typical noise.
    2) Stake size: full Kelly 0.38%, recommend 1/4 Kelly (~0.1%).
    3) Risks: low prob (10.8%), high variance, conf=0.76 moderate.
    4) Итог: лотерейный билет с небольшим перевесом, no guarantees.

## Key points

- AI **не галлюцинирует** — все числа (9.5, 9.3, 10.8%, 0.38%, 0.76)
  взяты из prompt, сформированного Python-кодом.
- Разделение: математика — Python, язык — LLM.
- OmniRoute работает без auth на /v1/chat/completions.
- Model `oc/big-pickle` — рабочий, отвечает за 1-2 сек.

## Files

- `ai/analyst.py` — ValueBetAnalyst (prompt + OmniRoute client)
- `demo_ai_pipeline.py` — end-to-end demo
- `runner.py` — режимы: mock / manual / fonbet / hybrid / hybrid_ai
- `data/runs/demo_ai_report.json` — сохранённый отчёт

## Notes

- /v1/models требует auth (401), но /v1/chat/completions — нет.
- api_key = "" трактуется как «no-auth» — это правильно.
- Промпт: SYSTEM (роль) + user (structured данные + инструкция формата).
