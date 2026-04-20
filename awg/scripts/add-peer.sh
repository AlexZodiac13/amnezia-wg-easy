#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 3 ]]; then
  echo "Usage: $0 <interface> <client_public_key> <client_ip_cidr> [preshared_key]"
  exit 1
fi

IFACE="$1"
CLIENT_PUBLIC_KEY="$2"
CLIENT_IP_CIDR="$3"
PRESHARED_KEY="${4:-}"

if [[ -n "$PRESHARED_KEY" ]]; then
  wg set "$IFACE" peer "$CLIENT_PUBLIC_KEY" preshared-key <(echo "$PRESHARED_KEY") allowed-ips "$CLIENT_IP_CIDR"
else
  wg set "$IFACE" peer "$CLIENT_PUBLIC_KEY" allowed-ips "$CLIENT_IP_CIDR"
fi

echo "Peer added: $CLIENT_PUBLIC_KEY -> $CLIENT_IP_CIDR"