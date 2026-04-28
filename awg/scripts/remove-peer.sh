#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 <interface> <client_public_key>"
  exit 1
fi

IFACE="$1"
CLIENT_PUBLIC_KEY="$2"
SERVER_CONFIG="/etc/amnezia/amneziawg/${IFACE}.conf"
CLIENT_IP=""

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
        if ($0 ~ /^[[:space:]]*AllowedIPs[[:space:]]*=/) {
          line = $0
          sub(/^[^=]*=[[:space:]]*/, "", line)
          line = trim(line)
          if (drop_block == 1) {
            client_ip = line
          }
        }
        next
      }

      print
    }
    END {
      flush_block()
      if (client_ip != "") {
        print client_ip > "/tmp/remove_peer_ip"
      }
    }
  ' "$SERVER_CONFIG" > "$tmp_file"
  mv "$tmp_file" "$SERVER_CONFIG"

  if [[ -f /tmp/remove_peer_ip ]]; then
    CLIENT_IP="$(cat /tmp/remove_peer_ip)"
    rm -f /tmp/remove_peer_ip
  fi
fi

if [[ -n "$CLIENT_IP" ]]; then
  default_ext_if() {
    ip route show default 0.0.0.0/0 | awk 'NR==1{print $5}'
  }

  EXT_IF="$(default_ext_if)"
  CLIENT_IP_ADDR="${CLIENT_IP%/*}"
  iptables -t mangle -D PREROUTING -i "$IFACE" -s "$CLIENT_IP_ADDR" -j MARK --set-mark "$DEFAULT_RATE_MBIT" 2>/dev/null || true
  iptables -t mangle -D PREROUTING -i "$IFACE" -s "$CLIENT_IP_ADDR" -j MARK --set-mark "$WHITELIST_RATE_MBIT" 2>/dev/null || true
  iptables -t mangle -D PREROUTING -i "$IFACE" -s "$CLIENT_IP_ADDR" -j MARK --set-mark "$UNLIMITED_RATE_MBIT" 2>/dev/null || true
  iptables -t mangle -D PREROUTING -i "$IFACE" -s "$CLIENT_IP_ADDR" -j CONNMARK --save-mark 2>/dev/null || true
fi

awg set "$IFACE" peer "$CLIENT_PUBLIC_KEY" remove
echo "Peer removed: $CLIENT_PUBLIC_KEY"