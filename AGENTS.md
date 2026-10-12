# ARTEM context

Methodology: ~/NEE/ARTEM-CORE.md
Bootstrap:   ~/NEE/BOOTSTRAP/
EVR log:     ~/NEE/logs/

## Правила
- Reality Before Assumptions — верифицируй grep/sed/curl
- py_compile после каждого Python-патча
- One engineering step = one commit
- DSH halucinates — проверяй на исходнике

## DSH WRITE ACCESS — критично
DSH (headless) ПИШЕТ в файлы. Не давать "прочитай и предложи" без явного запрета.
- В prompt: "НЕ применяй. Выведи diff."
- Перед dshh: cp <file> <file>.before-dsh
- После dshh: git status --porcelain
- Откат: git checkout -- <file>

## Тесты
- Unit:        ./run_tests.sh
- Integration: ./run_tests.sh -m integration

## Состояние
- Smarkets: timeout=15, retries=3
- Telegram: HTTP_TIMEOUT=25, WG split-tunnel
- market/consensus.py — 19 тестов
- scoring/resolver.py — 6/7 покрыто
- tg_bot.py: /stats added (EVR-0012)
- results/ empty — resolver не запускался

## Backlog
- запустить resolve_all() → populate results/
- tests cmd_stats (tmp_path)
