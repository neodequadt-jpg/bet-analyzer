#!/usr/bin/env bash
# dsh-auto v4.2 — ARTEM-strict
# Exit: 0 PASS / 1 PRE_FLIGHT / 2 SPEC_INVALID / 3 EXEC_FAIL / 4 TESTS_FAIL / 5 NO_COMMIT / 6 VERIFY_FAIL
set -uo pipefail

SPEC="${1:-}"
MAX_ATTEMPTS="${2:-8}"
RUN_ID="run-$(date +%Y%m%d-%H%M%S)"
RUN_DIR="$HOME/.dsh/runs/$RUN_ID"
LOG="$RUN_DIR/dsh.log"
mkdir -p "$RUN_DIR"

# Всё что ниже — пишет EVR перед exit
PRE_HEAD=""
STATUS="FAIL"
REASON=""

_write_evr() {
    local st="$1"
    local rs="$2"
    python3 "$HOME/.dsh/lib/write_evr.py" "$RUN_DIR" "$st" "$rs" 2>/dev/null || true
}

die() {
    local code="$1"; shift
    local msg="$*"
    echo "[dsh-auto] ❌ EXIT $code: $msg" >&2
    _write_evr "FAIL" "exit_$code: $msg"
    exit "$code"
}

[ -n "$SPEC" ] || die 1 "usage: dsh-auto.sh <spec-file> [max-attempts]"
[ -f "$SPEC" ] || die 1 "spec not found: $SPEC"

cd ~/BET-ANALYZER

# ============ PHASE 1: PRE-FLIGHT ============
echo "[dsh-auto] === Phase 1: Pre-flight ===" | tee "$LOG"

RUNTIME_WHITELIST="data/state.json data/cache/ data/backtest/"

MODIFIED=$(git status --short | grep -v '^??' | awk '{print $2}')
DIRTY=""
for f in $MODIFIED; do
    W=0
    for w in $RUNTIME_WHITELIST; do
        case "$f" in "$w"|"$w"*) W=1; break ;; esac
    done
    [ "$W" -eq 0 ] && DIRTY="$DIRTY $f"
done

if [ -n "$DIRTY" ]; then
    echo "[dsh-auto] dirty files:$DIRTY" | tee -a "$LOG"
    git status --short | tee -a "$LOG"
    die 1 "working tree has modified files — commit/stash first"
fi
[ -n "$MODIFIED" ] && echo "[dsh-auto] ignored runtime: $MODIFIED" | tee -a "$LOG"

PRE_HEAD=$(git rev-parse HEAD)
echo "[dsh-auto] pre-state: $PRE_HEAD" | tee -a "$LOG"

if ! ss -lntp 2>/dev/null | grep -q ':20128'; then
    die 1 "OmniRoute down (port 20128)"
fi

source ~/.bet_env 2>/dev/null || true
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
nvm use 22 >/dev/null 2>&1 || die 1 "nvm not available"

BASELINE=$(./run_tests.sh 2>&1 | tail -3)
echo "$BASELINE" | tee -a "$LOG"
echo "$BASELINE" | grep -q "passed" || die 1 "baseline tests fail: $BASELINE"

# ============ PHASE 2: SPEC CONTRACT ============
echo "[dsh-auto] === Phase 2: Spec contract ===" | tee -a "$LOG"

for sec in "Reality" "Goal" "Deliverable" "Verification" "Constraints"; do
    if ! grep -qE "^## $sec" "$SPEC"; then
        die 2 "spec missing section: ## $sec"
    fi
done
echo "[dsh-auto] spec OK: $SPEC" | tee -a "$LOG"

# ============ PHASE 3: EXECUTE ============
echo "[dsh-auto] === Phase 3: Execute ===" | tee -a "$LOG"

# Модели: сильные первыми. 120B > 20B для агентных задач.
MODELS=(
    "groq/openai/gpt-oss-120b"
    "groq/qwen/qwen3.8-27b"
    "groq/openai/gpt-oss-20b"
    "gemini/gemini-3.1-flash-lite-preview"
    "groq/groq/compound"
    "gemini/gemini-3.6-flash"
)

set_model() {
    python3 - "$1" <<'PYEOF'
import re, sys
from pathlib import Path
model = sys.argv[1]
p = Path.home() / ".dsh" / "settings.yaml"
s = p.read_text()
s = re.sub(r"(agent-default-model:\n provider: omniroute\n model: )[^\n]+",
           r"\g<1>" + model, s)
p.write_text(s)
PYEOF
}

# Промпт v4.2: spec — единственный источник. Никакой MANIFEST.
DSH_PROMPT="Your spec is at ABSOLUTE PATH: $(realpath $SPEC). This file EXISTS. Read it. Implement strictly the spec at $SPEC. The spec is the ONLY source of truth. Do NOT read other files (no MANIFEST, no README). Implement literally: create/edit only files listed in the ## Deliverable section. Run only the ## Verification commands. Then commit with a message referencing the spec ID. Report the final commit hash."

MODEL_USED=""
DSH_OK=0
for attempt in $(seq 1 "$MAX_ATTEMPTS"); do
    idx=$(( (attempt - 1) % ${#MODELS[@]} ))
    M="${MODELS[$idx]}"
    echo "[dsh-auto] attempt $attempt/$MAX_ATTEMPTS — model: $M" | tee -a "$LOG"
    set_model "$M"
    set +e
    OUT=$(env -u all_proxy -u ALL_PROXY \
          http_proxy="http://127.0.0.1:18080" \
          https_proxy="http://127.0.0.1:18080" \
          HTTP_PROXY="http://127.0.0.1:18080" \
          HTTPS_PROXY="http://127.0.0.1:18080" \
          no_proxy="127.0.0.1,localhost" \
          dsh --profile headless "$DSH_PROMPT" 2>&1)
    DSH_EXIT=$?
    set -e
    echo "$OUT" | tail -30 | tee -a "$LOG"

    if echo "$OUT" | grep -qiE "cooling down|rate.limit|429|too many|PI_AI_ERROR"; then
        BACK=$(( 30 * (2 ** (attempt - 1)) ))
        [ "$BACK" -gt 240 ] && BACK=240
        echo "[dsh-auto] cooldown → ${BACK}s" | tee -a "$LOG"
        sleep "$BACK"
        continue
    fi
    if [ "$DSH_EXIT" -eq 0 ]; then
        MODEL_USED="$M"
        DSH_OK=1
        break
    fi
    sleep 30
done
[ "$DSH_OK" -eq 1 ] || die 3 "DSH failed after $MAX_ATTEMPTS attempts (model chain exhausted)"

# ============ PHASE 4: VERIFY ============
echo "[dsh-auto] === Phase 4: Verify ===" | tee -a "$LOG"

TESTS_AFTER=$(./run_tests.sh 2>&1 | tail -3)
echo "$TESTS_AFTER" | tee -a "$LOG"
POST_HEAD=$(git rev-parse HEAD)
DIFF_STAT=$(git diff --stat "$PRE_HEAD" "$POST_HEAD" | tail -1)

if ! echo "$TESTS_AFTER" | grep -q "passed"; then
    echo "[dsh-auto] tests failed — rollback" | tee -a "$LOG"
    git reset --hard "$PRE_HEAD"
    die 4 "tests failed after DSH"
fi

if [ "$POST_HEAD" = "$PRE_HEAD" ]; then
    echo "[dsh-auto] no commit created — DSH did nothing" | tee -a "$LOG"
    die 5 "DSH created no commit (spec may be too trivial or model hallucinated)"
fi

# ============ PHASE 4.5: SPEC VERIFICATION ============
echo "[dsh-auto] === Phase 4.5: Spec verification ===" | tee -a "$LOG"

VERIFS_JSON=$(python3 "$HOME/.dsh/lib/extract_verifications.py" "$SPEC" 2>/dev/null || echo "[]")
NUM_VERIFS=$(echo "$VERIFS_JSON" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo 0)
echo "[dsh-auto] spec verification commands: $NUM_VERIFS" | tee -a "$LOG"

VERIF_TSV="$RUN_DIR/verifications.tsv"
: > "$VERIF_TSV"
VERIF_FAILED=0

i=0
while [ "$i" -lt "$NUM_VERIFS" ]; do
    CMD=$(echo "$VERIFS_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin)[$i]['cmd'])")
    echo "[dsh-auto] verify[$((i+1))/$NUM_VERIFS]: $CMD" | tee -a "$LOG"
    set +e
    VOUT=$(cd ~/BET-ANALYZER && bash -c "$CMD" 2>&1)
    VEXIT=$?
    set -e
    echo "$VOUT" | tail -5 | tee -a "$LOG"
    [ "$VEXIT" -ne 0 ] && VERIF_FAILED=1 && echo "[dsh-auto] verify[$((i+1))] FAILED" | tee -a "$LOG"
    OK=$([ "$VEXIT" -eq 0 ] && echo 1 || echo 0)
    printf '%d\t%d\t%d\t%s\n' "$((i+1))" "$VEXIT" "$OK" "$CMD" >> "$VERIF_TSV"
    i=$((i + 1))
done

python3 - "$VERIF_TSV" "$RUN_DIR/verifications.json" <<'PYEOF'
import json, sys
from pathlib import Path
tsv = Path(sys.argv[1]); out = Path(sys.argv[2])
arr = []
if tsv.exists():
    for line in tsv.read_text(encoding="utf-8").splitlines():
        p = line.split("\t", 3)
        if len(p) < 4: continue
        arr.append({"idx": int(p[0]), "exit": int(p[1]), "ok": p[2] == "1", "cmd": p[3]})
out.write_text(json.dumps(arr, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"[dsh-auto] verifications recorded: {len(arr)}")
PYEOF

if [ "$VERIF_FAILED" -eq 1 ]; then
    echo "[dsh-auto] spec verification FAILED — rollback" | tee -a "$LOG"
    git reset --hard "$PRE_HEAD"
    die 6 "spec verification failed (see verifications.json)"
fi

# ============ PHASE 5: EVIDENCE ============
echo "[dsh-auto] === Phase 5: Evidence ===" | tee -a "$LOG"

cat > "$RUN_DIR/EVR.md" <<EOF
# EVR-$RUN_ID

- Status: **PASS**
- pre-state: $PRE_HEAD
- post-state: $POST_HEAD
- model_used: $MODEL_USED
- diff: $DIFF_STAT
- baseline: $(echo "$BASELINE" | tail -1)
- final: $(echo "$TESTS_AFTER" | tail -1)
- verifications: $NUM_VERIFS (all passed)
EOF

cat > "$RUN_DIR/run.json" <<EOF
{
  "run_id": "$RUN_ID",
  "status": "PASS",
  "spec": "$SPEC",
  "pre_hash": "$PRE_HEAD",
  "post_hash": "$POST_HEAD",
  "model_used": "$MODEL_USED",
  "diff_stat": "$DIFF_STAT",
  "baseline_tests": "$(echo "$BASELINE" | tail -1)",
  "final_tests": "$(echo "$TESTS_AFTER" | tail -1)",
  "verifications_count": $NUM_VERIFS
}
EOF

echo "[dsh-auto] ✅ SUCCESS" | tee -a "$LOG"
echo "  before: $PRE_HEAD"
echo "  after:  $POST_HEAD"
echo "  model:  $MODEL_USED"
echo "  EVR:    $RUN_DIR/EVR.md"
exit 0
