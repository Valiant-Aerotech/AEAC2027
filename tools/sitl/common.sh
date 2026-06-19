#!/usr/bin/env bash
# Shared diagnostics for Valiant WSL bash scripts (source, do not execute).
# Usage: source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

valiant_script_dir() {
  local src="${1:-${BASH_SOURCE[1]:-${BASH_SOURCE[0]:-}}}"
  if [[ -n "$src" ]]; then
    cd "$(dirname "$src")" && pwd
  else
    echo "${VALIANT_SITL_SCRIPT_DIR:-}"
  fi
}

VALIANT_LOG="${VALIANT_LOG:-$HOME/.valiant_wsl_last.log}"
VALIANT_DOC="${VALIANT_DOC:-docs/runbooks/sitl-wsl.md}"

_valiant_ts() {
  date -Iseconds 2>/dev/null || date '+%Y-%m-%dT%H:%M:%S'
}

valiant_log() {
  local line="[$(_valiant_ts)] $*"
  echo "$*"
  echo "$line" >>"$VALIANT_LOG"
}

valiant_hint() {
  echo "  -> $*" >&2
}

valiant_die() {
  local msg="$1"
  shift || true
  echo "" >&2
  echo "ERROR: $msg" >&2
  while (($# > 0)); do
    valiant_hint "$1"
    shift
  done
  valiant_hint "Docs: $VALIANT_DOC"
  valiant_hint "Windows: python tools/valiant.py diagnose"
  exit "${VALIANT_DIE_CODE:-1}"
}

valiant_require_cmd() {
  local cmd="$1"
  shift || true
  if ! command -v "$cmd" &>/dev/null; then
    valiant_die "Required command not found: $cmd" "$@"
  fi
}

valiant_require_file() {
  local path="$1"
  local purpose="${2:-required file}"
  shift 2 || shift 1 || true
  if [[ ! -f "$path" ]]; then
    valiant_die "Missing $purpose: $path" "$@"
  fi
}

valiant_require_dir() {
  local path="$1"
  local purpose="${2:-required directory}"
  shift 2 || shift 1 || true
  if [[ ! -d "$path" ]]; then
    valiant_die "Missing $purpose: $path" "$@"
  fi
}

valiant_on_err() {
  local rc=$?
  echo "" >&2
  echo "ERROR: command failed at line ${BASH_LINENO[0]} (exit $rc)" >&2
  valiant_hint "Session log: $VALIANT_LOG"
  valiant_hint "Docs: $VALIANT_DOC"
  exit "$rc"
}
