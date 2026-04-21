#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'EOF'
Usage:
  add-peer.sh <interface> <client_public_key> <client_ip_cidr> [preshared_key]
  add-peer.sh <interface> [client_name] [endpoint] [client_ip_cidr] [preshared_key]
EOF
  exit 1
}

IFACE="$1"
shift || usage

CLIENTS_DIR="/etc/amnezia/amneziawg/clients"
SERVER_CONFIG="/etc/amnezia/amneziawg/${IFACE}.conf"
SERVER_PUBLIC_KEY_FILE="/etc/amnezia/amneziawg/server_public.key"
DEFAULT_CLIENT_IP_CIDR="10.80.0.2/32"
PUBKEY_PATTERN='^[A-Za-z0-9+/]{43}=$'

server_value() {
  local key="$1"
  awk -F'=' -v wanted_key="$key" '
    BEGIN { ignorecase = 1 }
    {
      current_key = $1
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", current_key)
      if (tolower(current_key) == tolower(wanted_key)) {
        value = substr($0, index($0, "=") + 1)
        gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
        print value
        exit
      }
    }
  ' "$SERVER_CONFIG"
}

if [[ $# -ge 2 && ${1:-} =~ $PUBKEY_PATTERN ]]; then
  CLIENT_PUBLIC_KEY="$1"
  CLIENT_IP_CIDR="$2"
  PRESHARED_KEY="${3:-}"

  if [[ -n "$PRESHARED_KEY" ]]; then
    awg set "$IFACE" peer "$CLIENT_PUBLIC_KEY" preshared-key <(printf '%s' "$PRESHARED_KEY") allowed-ips "$CLIENT_IP_CIDR"
  else
    awg set "$IFACE" peer "$CLIENT_PUBLIC_KEY" allowed-ips "$CLIENT_IP_CIDR"
  fi

  echo "Peer added: $CLIENT_PUBLIC_KEY -> $CLIENT_IP_CIDR"
  exit 0
fi

if [[ $# -gt 4 ]]; then
  usage
fi

CLIENT_NAME="${1:-client-$(date +%Y%m%d%H%M%S)}"
ENDPOINT="${2:-${AWG_ENDPOINT:-change-me:5066}}"
CLIENT_IP_CIDR="${3:-$DEFAULT_CLIENT_IP_CIDR}"
PRESHARED_KEY="${4:-}"
CLIENT_PERSISTENT_KEEPALIVE="${AWG_CLIENT_PERSISTENT_KEEPALIVE:-0}"

if [[ ! -f "$SERVER_CONFIG" ]]; then
  echo "Server config not found: $SERVER_CONFIG" >&2
  exit 1
fi

mkdir -p "$CLIENTS_DIR"

CLIENT_PRIVATE_KEY_FILE="$CLIENTS_DIR/${CLIENT_NAME}.privatekey"
CLIENT_PUBLIC_KEY_FILE="$CLIENTS_DIR/${CLIENT_NAME}.publickey"
CLIENT_CONFIG_FILE="$CLIENTS_DIR/${CLIENT_NAME}.conf"
CLIENT_QR_FILE="$CLIENTS_DIR/${CLIENT_NAME}.png"
CLIENT_QR_TXT_FILE="$CLIENTS_DIR/${CLIENT_NAME}_qr.txt"

awg genkey | tee "$CLIENT_PRIVATE_KEY_FILE" | awg pubkey > "$CLIENT_PUBLIC_KEY_FILE"
chmod 600 "$CLIENT_PRIVATE_KEY_FILE"
chmod 644 "$CLIENT_PUBLIC_KEY_FILE"

CLIENT_PRIVATE_KEY="$(cat "$CLIENT_PRIVATE_KEY_FILE")"
CLIENT_PUBLIC_KEY="$(cat "$CLIENT_PUBLIC_KEY_FILE")"
SERVER_PUBLIC_KEY="$(cat "$SERVER_PUBLIC_KEY_FILE")"

SERVER_DNS="${AWG_DNS:-$(server_value DNS || true)}"
SERVER_JC="$(server_value Jc || true)"
SERVER_JMIN="$(server_value Jmin || true)"
SERVER_JMAX="$(server_value Jmax || true)"
SERVER_S1="$(server_value S1 || true)"
SERVER_S2="$(server_value S2 || true)"
SERVER_S3="$(server_value S3 || true)"
SERVER_S4="$(server_value S4 || true)"
SERVER_H1="$(server_value H1 || true)"
SERVER_H2="$(server_value H2 || true)"
SERVER_H3="$(server_value H3 || true)"
SERVER_H4="$(server_value H4 || true)"
SERVER_I1="$(server_value I1 || true)"
SERVER_I2="$(server_value I2 || true)"
SERVER_I3="$(server_value I3 || true)"
SERVER_I4="$(server_value I4 || true)"
SERVER_I5="$(server_value I5 || true)"
SERVER_MTU="$(server_value MTU || true)"

if [[ -z "$PRESHARED_KEY" ]]; then
  PRESHARED_KEY="$(awg genpsk)"
fi

awg set "$IFACE" peer "$CLIENT_PUBLIC_KEY" preshared-key <(printf '%s' "$PRESHARED_KEY") allowed-ips "$CLIENT_IP_CIDR"

{
  printf '%s\n' '[Interface]'
  printf 'PrivateKey = %s\n' "$CLIENT_PRIVATE_KEY"
  printf 'Address = %s\n' "$CLIENT_IP_CIDR"
  if [[ -n "$SERVER_MTU" ]]; then
    printf 'MTU = %s\n' "$SERVER_MTU"
  fi
  if [[ -n "$SERVER_DNS" ]]; then
    printf 'DNS = %s\n' "$SERVER_DNS"
  fi
  [[ -n "$SERVER_JC" ]] && printf 'Jc = %s\n' "$SERVER_JC"
  [[ -n "$SERVER_JMIN" ]] && printf 'Jmin = %s\n' "$SERVER_JMIN"
  [[ -n "$SERVER_JMAX" ]] && printf 'Jmax = %s\n' "$SERVER_JMAX"
  [[ -n "$SERVER_S1" ]] && printf 'S1 = %s\n' "$SERVER_S1"
  [[ -n "$SERVER_S2" ]] && printf 'S2 = %s\n' "$SERVER_S2"
  [[ -n "$SERVER_S3" ]] && printf 'S3 = %s\n' "$SERVER_S3"
  [[ -n "$SERVER_S4" ]] && printf 'S4 = %s\n' "$SERVER_S4"
  [[ -n "$SERVER_H1" ]] && printf 'H1 = %s\n' "$SERVER_H1"
  [[ -n "$SERVER_H2" ]] && printf 'H2 = %s\n' "$SERVER_H2"
  [[ -n "$SERVER_H3" ]] && printf 'H3 = %s\n' "$SERVER_H3"
  [[ -n "$SERVER_H4" ]] && printf 'H4 = %s\n' "$SERVER_H4"
  [[ -n "$SERVER_I1" ]] && printf 'I1 = %s\n' "$SERVER_I1"
  [[ -n "$SERVER_I2" ]] && printf 'I2 = %s\n' "$SERVER_I2"
  [[ -n "$SERVER_I3" ]] && printf 'I3 = %s\n' "$SERVER_I3"
  [[ -n "$SERVER_I4" ]] && printf 'I4 = %s\n' "$SERVER_I4"
  [[ -n "$SERVER_I5" ]] && printf 'I5 = %s\n' "$SERVER_I5"
  printf '\n[Peer]\n'
  printf 'PublicKey = %s\n' "$SERVER_PUBLIC_KEY"
  printf 'PresharedKey = %s\n' "$PRESHARED_KEY"
  printf 'Endpoint = %s\n' "$ENDPOINT"
  printf 'AllowedIPs = 0.0.0.0/0, ::/0\n'
  printf 'PersistentKeepalive = %s\n' "$CLIENT_PERSISTENT_KEEPALIVE"
} > "$CLIENT_CONFIG_FILE"

# Make config readable (755 dir, 644 files)
chmod 644 "$CLIENT_CONFIG_FILE"

# Generate QR codes with Python
if command -v python3 &>/dev/null; then
  # PNG QR code
  python3 -c "
import qrcode
try:
    with open('$CLIENT_CONFIG_FILE', 'r') as f:
        data = f.read()
    qr = qrcode.QRCode()
    qr.add_data(data)
    qr.make()
    qr.make_image().save('$CLIENT_QR_FILE')
except:
    pass
" && chmod 644 "$CLIENT_QR_FILE" 2>/dev/null || true
  
  # ASCII QR code
  python3 -c "
import qrcode
try:
    with open('$CLIENT_CONFIG_FILE', 'r') as f:
        data = f.read()
    qr = qrcode.QRCode()
    qr.add_data(data)
    qr.make()
    qr.print_ascii()
except:
    pass
" > "$CLIENT_QR_TXT_FILE" 2>&1 && chmod 644 "$CLIENT_QR_TXT_FILE" || true
fi

echo "Client created: $CLIENT_NAME"
echo "Client config: $CLIENT_CONFIG_FILE"
echo "Client private key: $CLIENT_PRIVATE_KEY_FILE"
echo "Client public key: $CLIENT_PUBLIC_KEY_FILE"
[[ -f "$CLIENT_QR_FILE" ]] && echo "Client QR (PNG): $CLIENT_QR_FILE"
[[ -f "$CLIENT_QR_TXT_FILE" ]] && echo "Client QR (text): $CLIENT_QR_TXT_FILE"
echo "Peer added: $CLIENT_PUBLIC_KEY -> $CLIENT_IP_CIDR"