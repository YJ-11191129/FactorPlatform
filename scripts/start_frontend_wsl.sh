#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${1:-/mnt/d/FactorPlatform}"
PORT="${2:-3000}"

cd "${ROOT_DIR}/web"
exec npm run dev -- --hostname 0.0.0.0 --port "${PORT}"
