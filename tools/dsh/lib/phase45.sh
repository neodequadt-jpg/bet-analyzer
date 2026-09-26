# ============ PHASE 4.5: SPEC VERIFICATION (Evidence Before Authority) ============
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
    if [ "$VEXIT" -ne 0 ]; then
        VERIF_FAILED=1
        echo "[dsh-auto] verify[$((i+1))] FAILED (exit $VEXIT)" | tee -a "$LOG"
    fi
    OK=$([ "$VEXIT" -eq 0 ] && echo 1 || echo 0)
    printf '%d\t%d\t%d\t%s\n' "$((i+1))" "$VEXIT" "$OK" "$CMD" >> "$VERIF_TSV"
    i=$((i + 1))
done

python3 - "$VERIF_TSV" "$RUN_DIR/verifications.json" <<'PYEOF'
import json, sys
from pathlib import Path
tsv = Path(sys.argv[1])
out = Path(sys.argv[2])
arr = []
if tsv.exists():
    for line in tsv.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t", 3)
        if len(parts) < 4:
            continue
        arr.append({
            "idx": int(parts[0]),
            "exit": int(parts[1]),
            "ok": parts[2] == "1",
            "cmd": parts[3],
        })
out.write_text(json.dumps(arr, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"[dsh-auto] verifications recorded: {len(arr)}")
PYEOF

if [ "$VERIF_FAILED" -eq 1 ]; then
    echo "[dsh-auto] spec verification FAILED — rollback" | tee -a "$LOG"
    git reset --hard "$PRE_HEAD"
    echo "[dsh-auto] ❌ EXIT 6: spec verification failed" >&2
    exit 6
fi

