#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <interface>"
  exit 1
fi

IFACE="$1"
awg show "$IFACE" dump