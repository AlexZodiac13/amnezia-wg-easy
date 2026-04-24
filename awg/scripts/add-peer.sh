#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'EOF'
Usage:
  add-peer.sh <interface> <client_public_key> <client_ip_cidr> [preshared_key] [rate_mbit]
  add-peer.sh <interface> [client_name] [endpoint] [client_ip_cidr] [preshared_key] [rate_mbit]
EOF
  exit 1
}

IFACE="$1"
shift || usage

CLIENTS_DIR="/etc/amnezia/amneziawg/clients"
SERVER_CONFIG="/etc/amnezia/amneziawg/${IFACE}.conf"
SERVER_PUBLIC_KEY_FILE="/etc/amnezia/amneziawg/server_public.key"
DEFAULT_CLIENT_IP_CIDR="10.80.0.2/32"
DEFAULT_RATE_MBIT="${AWG_RATE_LIMIT_MBIT:-15}"
WHITELIST_RATE_MBIT="${AWG_WHITELIST_RATE_MBIT:-200}"
UNLIMITED_RATE_MBIT="${AWG_UNLIMITED_RATE_MBIT:-1000}"
ROOT_DEFAULT_CLASS_ID="9999"
PUBKEY_PATTERN='^[A-Za-z0-9+/]{43}=$'

next_available_ip() {
  local subnet="10.80.0.0/16"
  local start_ip="10.80.0.2"
  local used_ips
  
  # Extract used IPs from server config
  used_ips=$(awk '
    /^[[:space:]]*AllowedIPs[[:space:]]*=/ {
      split($0, parts, "=")
      ip = parts[2]
      gsub(/[[:space:]]+/, "", ip)
      # Extract IP part before /
      split(ip, ip_parts, "/")
      print ip_parts[1]
    }
  ' "$SERVER_CONFIG" | sort -u)
  
  # Find next available IP starting from 10.80.0.2
  local ip_num=$(echo "$start_ip" | awk -F. '{print ($1*256*256*256) + ($2*256*256) + ($3*256) + $4}')
  local max_ip=$(echo "10.80.255.254" | awk -F. '{print ($1*256*256*256) + ($2*256*256) + ($3*256) + $4}')
  
  while [ $ip_num -le $max_ip ]; do
    local candidate_ip=$(awk -v num=$ip_num 'BEGIN {
      printf "%d.%d.%d.%d", (num/(256*256*256))%256, (num/(256*256))%256, (num/256)%256, num%256
    }')
    
    if ! echo "$used_ips" | grep -q "^$candidate_ip$"; then
      echo "$candidate_ip/32"
      return 0
    fi
    
    ip_num=$((ip_num + 1))
  done
  
  echo "No available IP addresses in subnet $subnet" >&2
  return 1
}

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

remove_peer_from_server_config() {
  local peer_public_key="$1"
  local tmp_file
  tmp_file="$(mktemp)"

  awk -v target_key="$peer_public_key" '
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
}

persist_peer_in_server_config() {
  local peer_public_key="$1"
  local peer_ip_cidr="$2"
  local peer_psk="${3:-}"

  remove_peer_from_server_config "$peer_public_key"

  {
    printf '\n[Peer]\n'
    printf 'PublicKey = %s\n' "$peer_public_key"
    [[ -n "$peer_psk" ]] && printf 'PresharedKey = %s\n' "$peer_psk"
    printf 'AllowedIPs = %s\n' "$peer_ip_cidr"
  } >> "$SERVER_CONFIG"
}

default_ext_if() {
  ip route show default 0.0.0.0/0 | awk 'NR==1{print $5}'
}

normalize_rate() {
  local requested_rate="${1:-$DEFAULT_RATE_MBIT}"

  if [[ "$requested_rate" == "0" ]]; then
    printf '%s\n' "$UNLIMITED_RATE_MBIT"
    return
  fi

  if [[ "$requested_rate" =~ ^[0-9]+$ ]]; then
    if [[ "$requested_rate" -eq "$WHITELIST_RATE_MBIT" ]]; then
      printf '%s\n' "$WHITELIST_RATE_MBIT"
      return
    fi

    if [[ "$requested_rate" -eq "$UNLIMITED_RATE_MBIT" ]]; then
      printf '%s\n' "$UNLIMITED_RATE_MBIT"
      return
    fi

    printf '%s\n' "$requested_rate"
    return
  fi

  printf '%s\n' "$DEFAULT_RATE_MBIT"
}

ensure_htb_root() {
  local device="$1"

  tc qdisc del dev "$device" root 2>/dev/null || true
  tc qdisc add dev "$device" root handle 1: htb default "$ROOT_DEFAULT_CLASS_ID" 2>/dev/null || true

  # Keep non-matching traffic out of limited classes.
  tc class add dev "$device" parent 1: classid "1:${ROOT_DEFAULT_CLASS_ID}" htb rate "${UNLIMITED_RATE_MBIT}mbit" ceil "${UNLIMITED_RATE_MBIT}mbit" 2>/dev/null || true

  tc class add dev "$device" parent 1: classid "1:${DEFAULT_RATE_MBIT}" htb rate "${DEFAULT_RATE_MBIT}mbit" ceil "${DEFAULT_RATE_MBIT}mbit" 2>/dev/null || true
  tc class add dev "$device" parent 1: classid "1:${WHITELIST_RATE_MBIT}" htb rate "${WHITELIST_RATE_MBIT}mbit" ceil "${WHITELIST_RATE_MBIT}mbit" 2>/dev/null || true
  tc class add dev "$device" parent 1: classid "1:${UNLIMITED_RATE_MBIT}" htb rate "${UNLIMITED_RATE_MBIT}mbit" ceil "${UNLIMITED_RATE_MBIT}mbit" 2>/dev/null || true

  tc filter add dev "$device" parent 1: protocol ip prio 1 handle "$DEFAULT_RATE_MBIT" fw flowid "1:${DEFAULT_RATE_MBIT}" 2>/dev/null || true
  tc filter add dev "$device" parent 1: protocol ip prio 1 handle "$WHITELIST_RATE_MBIT" fw flowid "1:${WHITELIST_RATE_MBIT}" 2>/dev/null || true
  tc filter add dev "$device" parent 1: protocol ip prio 1 handle "$UNLIMITED_RATE_MBIT" fw flowid "1:${UNLIMITED_RATE_MBIT}" 2>/dev/null || true
}

apply_peer_rate_limit() {
  local client_ip_cidr="$1"
  local rate_mbit="$2"
  local client_ip="${client_ip_cidr%/*}"
  local ext_if

  ext_if="$(default_ext_if)"
  [[ -n "$ext_if" ]] || return 0

  ensure_htb_root "$IFACE"
  ensure_htb_root "$ext_if"

  iptables -t mangle -C PREROUTING -i "$IFACE" -s "$client_ip" -j MARK --set-mark "$rate_mbit" 2>/dev/null || \
    iptables -t mangle -I PREROUTING 1 -i "$IFACE" -s "$client_ip" -j MARK --set-mark "$rate_mbit"

  iptables -t mangle -C PREROUTING -i "$IFACE" -s "$client_ip" -j CONNMARK --save-mark 2>/dev/null || \
    iptables -t mangle -I PREROUTING 2 -i "$IFACE" -s "$client_ip" -j CONNMARK --save-mark

  iptables -t mangle -C PREROUTING -i "$ext_if" -m conntrack --ctstate ESTABLISHED,RELATED -j CONNMARK --restore-mark 2>/dev/null || \
    iptables -t mangle -I PREROUTING 1 -i "$ext_if" -m conntrack --ctstate ESTABLISHED,RELATED -j CONNMARK --restore-mark
}

if [[ $# -ge 2 && ${1:-} =~ $PUBKEY_PATTERN ]]; then
  CLIENT_PUBLIC_KEY="$1"
  CLIENT_IP_CIDR="$2"
  PRESHARED_KEY="${3:-}"
  CLIENT_RATE_MBIT="$(normalize_rate "${4:-}")"

  if [[ -n "$PRESHARED_KEY" ]]; then
    awg set "$IFACE" peer "$CLIENT_PUBLIC_KEY" preshared-key <(printf '%s' "$PRESHARED_KEY") allowed-ips "$CLIENT_IP_CIDR"
  else
    awg set "$IFACE" peer "$CLIENT_PUBLIC_KEY" allowed-ips "$CLIENT_IP_CIDR"
  fi

  persist_peer_in_server_config "$CLIENT_PUBLIC_KEY" "$CLIENT_IP_CIDR" "$PRESHARED_KEY"

  apply_peer_rate_limit "$CLIENT_IP_CIDR" "$CLIENT_RATE_MBIT"

  echo "Peer added: $CLIENT_PUBLIC_KEY -> $CLIENT_IP_CIDR (rate ${CLIENT_RATE_MBIT}mbit)"
  exit 0
fi

if [[ $# -gt 5 ]]; then
  usage
fi

CLIENT_NAME="${1:-client-$(date +%Y%m%d%H%M%S)}"
ENDPOINT="${2:-${AWG_ENDPOINT:-change-me:5066}}"
CLIENT_IP_CIDR="${3:-$(next_available_ip)}"
PRESHARED_KEY="${4:-}"
CLIENT_RATE_MBIT="$(normalize_rate "${5:-}")"
CLIENT_PERSISTENT_KEEPALIVE="${AWG_CLIENT_PERSISTENT_KEEPALIVE:-0}"

if [[ ! -f "$SERVER_CONFIG" ]]; then
  echo "Server config not found: $SERVER_CONFIG" >&2
  exit 1
fi

mkdir -p "$CLIENTS_DIR"

CLIENT_PRIVATE_KEY_FILE="$CLIENTS_DIR/${CLIENT_NAME}.privatekey"
CLIENT_PUBLIC_KEY_FILE="$CLIENTS_DIR/${CLIENT_NAME}.publickey"
CLIENT_CONFIG_FILE="$CLIENTS_DIR/${CLIENT_NAME}.conf"

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
persist_peer_in_server_config "$CLIENT_PUBLIC_KEY" "$CLIENT_IP_CIDR" "$PRESHARED_KEY"
apply_peer_rate_limit "$CLIENT_IP_CIDR" "$CLIENT_RATE_MBIT"

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
  printf '\n# Rate limit (in Mbit/s) - do not edit\n'
  printf '# Rate = %s\n' "$CLIENT_RATE_MBIT"
} > "$CLIENT_CONFIG_FILE"

# Make config readable (755 dir, 644 files)
chmod 644 "$CLIENT_CONFIG_FILE"

echo "Client created: $CLIENT_NAME"
echo "Client config: $CLIENT_CONFIG_FILE"
echo "Client private key: $CLIENT_PRIVATE_KEY_FILE"
echo "Client public key: $CLIENT_PUBLIC_KEY_FILE"
echo "Peer added: $CLIENT_PUBLIC_KEY -> $CLIENT_IP_CIDR (rate ${CLIENT_RATE_MBIT}mbit)"