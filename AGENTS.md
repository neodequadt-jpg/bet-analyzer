# ARTEM context

Methodology: ~/NEE/ARTEM-CORE.md
Bootstrap:   ~/NEE/BOOTSTRAP/
EVR log:     ~/NEE/logs/

## Правила
- Reality Before Assumptions — верифицируй grep/sed/curl
- py_compile после каждого Python-патча
- One engineering step = one commit
- DSH halucinates — любое предложение проверяй на исходнике

## Тесты
- Unit:        ./run_tests.sh                    (pytest.ini: -m "not integration")
- Integration: ./run_tests.sh -m integration     (live Fonbet/Smarkets/Telegram)

## Текущее состояние (verified)
- Smarkets: timeout=15, retries=3 (bookmakers/smarkets_provider.py:84-85)
- Telegram: HTTP_TIMEOUT=25 (tg_bot.py), трафик через WG split-tunnel
- market/consensus.py — полностью покрыт (19 тестов)
- scoring/resolver.py — 4/7 функций покрыто edge-кейсами

## Backlog
- scoring/resolver.py: mock network для _get_session, _fetch_events_for_date
- docs: docstrings для ключевых модулей
- периодический DSH review (1×/неделя)
