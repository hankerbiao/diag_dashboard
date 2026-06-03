#!/usr/bin/env bash
# WeaveEye 数据同步 — 一键入口（供 crontab / 运维脚本调用）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

CONFIG="${WEAVEEYE_SYNC_CONFIG:-$ROOT/scripts/sync_config.yaml}"
PYTHON="${WEAVEEYE_PYTHON:-python3}"

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

exec "$PYTHON" "$ROOT/scripts/weaveeye_sync.py" run -c "$CONFIG" "$@"
