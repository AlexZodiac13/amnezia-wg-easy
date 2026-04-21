#!/usr/bin/env bash
set -euo pipefail

AWG_INTERFACE="${AWG_INTERFACE:-awg0}"
AWG_LISTEN_PORT="${AWG_LISTEN_PORT:-5060}"
AWG_ADDRESS="${AWG_ADDRESS:-10.80.0.1/24}"
AWG_MTU="${AWG_MTU:-1280}"
AWG_DNS="${AWG_DNS:-1.1.1.1}"
AWG_TABLE="${AWG_TABLE:-off}"

AWG_JC="${AWG_JC:-7}"
AWG_JMIN="${AWG_JMIN:-50}"
AWG_JMAX="${AWG_JMAX:-1000}"
AWG_S1="${AWG_S1:-68}"
AWG_S2="${AWG_S2:-149}"
AWG_S3="${AWG_S3:-32}"
AWG_S4="${AWG_S4:-16}"
AWG_H1="${AWG_H1:-471800590-471800690}"
AWG_H2="${AWG_H2:-1246894907-1246895000}"
AWG_H3="${AWG_H3:-923637689-923637690}"
AWG_H4="${AWG_H4:-1769581055-1869581055}"
AWG_I1="${AWG_I1:-}"
AWG_I2="${AWG_I2:-}"
AWG_I3="${AWG_I3:-}"
AWG_I4="${AWG_I4:-}"
AWG_I5="${AWG_I5:-}"

CONFIG_DIR=/etc/amnezia/amneziawg
CONFIG_FILE="${CONFIG_DIR}/${AWG_INTERFACE}.conf"

mkdir -p "$CONFIG_DIR"
chmod 700 /etc/amnezia "$CONFIG_DIR"

if [[ ! -f "$CONFIG_DIR/server_private.key" ]]; then
  awg genkey | tee "$CONFIG_DIR/server_private.key" | awg pubkey > "$CONFIG_DIR/server_public.key"
  chmod 600 "$CONFIG_DIR/server_private.key"
  chmod 644 "$CONFIG_DIR/server_public.key"
fi

SERVER_PRIVATE_KEY="$(cat "$CONFIG_DIR/server_private.key")"

{
  printf '%s\n' '[Interface]'
  printf 'PrivateKey = %s\n' "$SERVER_PRIVATE_KEY"
  printf 'Address = %s\n' "$AWG_ADDRESS"
  printf 'ListenPort = %s\n' "$AWG_LISTEN_PORT"
  printf 'MTU = %s\n' "$AWG_MTU"
  printf 'Table = %s\n' "$AWG_TABLE"
  printf 'DNS = %s\n' "$AWG_DNS"
  printf 'Jc = %s\n' "$AWG_JC"
  printf 'Jmin = %s\n' "$AWG_JMIN"
  printf 'Jmax = %s\n' "$AWG_JMAX"
  printf 'S1 = %s\n' "$AWG_S1"
  printf 'S2 = %s\n' "$AWG_S2"
  printf 'S3 = %s\n' "$AWG_S3"
  printf 'S4 = %s\n' "$AWG_S4"
  printf 'H1 = %s\n' "$AWG_H1"
  printf 'H2 = %s\n' "$AWG_H2"
  printf 'H3 = %s\n' "$AWG_H3"
  printf 'H4 = %s\n' "$AWG_H4"
  [[ -n "$AWG_I1" ]] && printf 'I1 = %s\n' "$AWG_I1"
  [[ -n "$AWG_I2" ]] && printf 'I2 = %s\n' "$AWG_I2"
  [[ -n "$AWG_I3" ]] && printf 'I3 = %s\n' "$AWG_I3"
  [[ -n "$AWG_I4" ]] && printf 'I4 = %s\n' "$AWG_I4"
  [[ -n "$AWG_I5" ]] && printf 'I5 = %s\n' "$AWG_I5"
} > "$CONFIG_FILE"

if ip link show "${AWG_INTERFACE}" >/dev/null 2>&1; then
  awg-quick down "${AWG_INTERFACE}" || true
  awg-quick up "${AWG_INTERFACE}"
else
  awg-quick up "${AWG_INTERFACE}"
fi

# Ensure VPN clients can reach the internet when host FORWARD policy is DROP.
EXT_IF="$(ip route show default 0.0.0.0/0 | awk 'NR==1{print $5}')"
AWG_SUBNET="$(ip -4 route show dev "${AWG_INTERFACE}" proto kernel scope link | awk 'NR==1{print $1}')"

if [[ -n "${EXT_IF}" && -n "${AWG_SUBNET}" ]]; then
  iptables -C FORWARD -i "${AWG_INTERFACE}" -j ACCEPT 2>/dev/null || \
    iptables -I FORWARD 1 -i "${AWG_INTERFACE}" -j ACCEPT

  iptables -C FORWARD -o "${AWG_INTERFACE}" -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || \
    iptables -I FORWARD 1 -o "${AWG_INTERFACE}" -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT

  iptables -t nat -C POSTROUTING -s "${AWG_SUBNET}" -o "${EXT_IF}" -j MASQUERADE 2>/dev/null || \
    iptables -t nat -I POSTROUTING 1 -s "${AWG_SUBNET}" -o "${EXT_IF}" -j MASQUERADE
fi

echo "AWG is up on ${AWG_INTERFACE}:${AWG_LISTEN_PORT}"
echo "Server public key: $(cat "$CONFIG_DIR/server_public.key")"
echo "Client DNS suggestion: ${AWG_DNS}"

exec tail -f /dev/null