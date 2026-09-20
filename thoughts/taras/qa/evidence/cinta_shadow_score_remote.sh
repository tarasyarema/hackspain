#!/bin/sh
# Run only after the coordinator approves the remote slot and reviewed inputs.
set -eu

AUDIT_INPUT=/srv/hackspain-coffee/diagnostics/c95a10a-shadow16s-attempt1/input
AUDIT_OUTPUT=/srv/hackspain-coffee/diagnostics/c95a10a-shadow16s-attempt1/output
AUDIT_LOCK=/srv/hackspain-coffee/diagnostics/c95a10a-shadow16s-attempt1/runtime.lock

test -f "$AUDIT_INPUT/cinta_shadow_score.py"
test -f "$AUDIT_INPUT/cinta_shadow_score_summary.py"
test -f "$AUDIT_INPUT/cinta_shadow_score_expected.json"
test ! -e "$AUDIT_OUTPUT/run.json"

exec docker run --rm \
  --name cinta-shadow-score-c95a10a-attempt1 \
  --cpus=2 --memory=2g --pids-limit=128 \
  --network=none --read-only \
  --env LP_NUM_THREADS=2 \
  --tmpfs /tmp:rw,nosuid,nodev,size=256m,uid=10001,gid=10001 \
  --mount "type=bind,source=$AUDIT_INPUT,target=/audit-input,readonly" \
  --mount "type=bind,source=$AUDIT_OUTPUT,target=/audit-output" \
  --mount "type=bind,source=$AUDIT_LOCK,target=/private/tmp/hackspain-coffee-runtime.lock" \
  --entrypoint python \
  sha256:4bf6d623015cc92655d880a3563e8904a5467a082034fb8e3f14d19dccea120a \
  /audit-input/cinta_shadow_score.py \
  --repo /app \
  --expected /audit-input/cinta_shadow_score_expected.json \
  --output /audit-output/run.json
