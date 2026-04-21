#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 <interface> <client_public_key>"
  exit 1
fi

IFACE="$1"
CLIENT_PUBLIC_KEY="$2"
SERVER_CONFIG="/etc/amnezia/amneziawg/${IFACE}.conf"

if [[ -f "$SERVER_CONFIG" ]]; then
  tmp_file="$(mktemp)"
  awk -v target_key="$CLIENT_PUBLIC_KEY" '
    function trim(s) {
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", s)
      return s
    }
    function flush_block() {
      if (in_peer == 1) {
        if (!drop_block) {
          printf "%s", block
        }
      }
      block = ""
      in_peer = 0
      drop_block = 0
    }
    {
      if ($0 ~ /^\[Peer\][[:space:]]*$/) {
        flush_block()
        in_peer = 1
        block = $0 ORS
        next
      }

      if (in_peer == 1) {
        block = block $0 ORS
        if ($0 ~ /^[[:space:]]*PublicKey[[:space:]]*=/) {
          line = $0
          sub(/^[^=]*=[[:space:]]*/, "", line)
          line = trim(line)
          if (line == target_key) {
            drop_block = 1
          }
        }
        next
      }

      print
    }
    END {
      flush_block()
    }
  ' "$SERVER_CONFIG" > "$tmp_file"
  mv "$tmp_file" "$SERVER_CONFIG"
fi

awg set "$IFACE" peer "$CLIENT_PUBLIC_KEY" remove
echo "Peer removed: $CLIENT_PUBLIC_KEY"