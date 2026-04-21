#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 <interface> <client_public_key>"
  exit 1
fi

IFACE="$1"
CLIENT_PUBLIC_KEY="$2"

awg set "$IFACE" peer "$CLIENT_PUBLIC_KEY" remove
echo "Peer removed: $CLIENT_PUBLIC_KEY"