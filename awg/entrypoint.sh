#!/usr/bin/env bash
set -euo pipefail

AWG_INTERFACE="${AWG_INTERFACE:-awg0}"
AWG_LISTEN_PORT="${AWG_LISTEN_PORT:-5060}"
AWG_ADDRESS="${AWG_ADDRESS:-10.80.0.1/24}"
AWG_MTU="${AWG_MTU:-1280}"
AWG_DNS="${AWG_DNS:-1.1.1.1}"
AWG_TABLE="${AWG_TABLE:-off}"

AWG_JC="${AWG_JC:-4}"
AWG_JMIN="${AWG_JMIN:-40}"
AWG_JMAX="${AWG_JMAX:-70}"
AWG_S1="${AWG_S1:-0}"
AWG_S2="${AWG_S2:-0}"
AWG_H1="${AWG_H1:-1}"
AWG_H2="${AWG_H2:-2}"
AWG_H3="${AWG_H3:-3}"
AWG_H4="${AWG_H4:-4}"

mkdir -p /etc/amnezia
chmod 700 /etc/amnezia

if [[ ! -f /etc/amnezia/server_private.key ]]; then
  wg genkey | tee /etc/amnezia/server_private.key | wg pubkey > /etc/amnezia/server_public.key
  chmod 600 /etc/amnezia/server_private.key
  chmod 644 /etc/amnezia/server_public.key
fi

SERVER_PRIVATE_KEY="$(cat /etc/amnezia/server_private.key)"

cat > /etc/amnezia/${AWG_INTERFACE}.conf <<EOF
[Interface]
PrivateKey = ${SERVER_PRIVATE_KEY}
Address = ${AWG_ADDRESS}
ListenPort = ${AWG_LISTEN_PORT}
MTU = ${AWG_MTU}
SaveConfig = true
Table = ${AWG_TABLE}
Jc = ${AWG_JC}
Jmin = ${AWG_JMIN}
Jmax = ${AWG_JMAX}
S1 = ${AWG_S1}
S2 = ${AWG_S2}
H1 = ${AWG_H1}
H2 = ${AWG_H2}
H3 = ${AWG_H3}
H4 = ${AWG_H4}
EOF

amneziawg-go "${AWG_INTERFACE}"
ip link set dev "${AWG_INTERFACE}" up
ip address replace "${AWG_ADDRESS}" dev "${AWG_INTERFACE}"
wg setconf "${AWG_INTERFACE}" "/etc/amnezia/${AWG_INTERFACE}.conf"

echo "AWG is up on ${AWG_INTERFACE}:${AWG_LISTEN_PORT}"
echo "Server public key: $(cat /etc/amnezia/server_public.key)"
echo "Client DNS suggestion: ${AWG_DNS}"

exec tail -f /dev/null