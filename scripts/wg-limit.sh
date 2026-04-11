#!/usr/bin/env bash
set -euo pipefail

# Ограничение скорости для клиентов WireGuard/AmneziaWG через tc + ifb.
#
# Возможности:
# - add: установить симметричный лимит (download+upload) для IP клиента
# - del: удалить лимит для IP клиента
# - show: показать активные классы/фильтры
# - reset: полностью сбросить qdisc/filter для пары интерфейсов
#
# Примечания:
# - Работает с IPv4-адресами клиентов.
# - Требуются права root.
# - По умолчанию используется интерфейс wg0 (можно переопределить WG_IFACE).

WG_IFACE="${WG_IFACE:-wg0}"
IFB_IFACE="${IFB_IFACE:-ifb0}"
ROOT_RATE="${ROOT_RATE:-10gbit}"
DEFAULT_CLASS_ID="${DEFAULT_CLASS_ID:-999}"

usage() {
  cat <<'EOF'
Использование:
  sudo ./scripts/wg-limit.sh add <client_ipv4> <скорость>
  sudo ./scripts/wg-limit.sh del <client_ipv4>
  sudo ./scripts/wg-limit.sh show
  sudo ./scripts/wg-limit.sh reset

Примеры:
  sudo ./wg-limit.sh add 10.10.0.3 20mbit
  sudo ./scripts/wg-limit.sh del 10.10.0.2
  sudo ./scripts/wg-limit.sh show
  sudo ./scripts/wg-limit.sh reset

Переопределение через переменные окружения:
  WG_IFACE=wg0
  IFB_IFACE=ifb0
  ROOT_RATE=10gbit
EOF
}

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    echo "Ошибка: запустите от root (используйте sudo)." >&2
    exit 1
  fi
}

require_cmds() {
  local missing=0
  for cmd in tc ip modprobe awk grep; do
    if ! command -v "${cmd}" >/dev/null 2>&1; then
      echo "Ошибка: не найдена обязательная команда: ${cmd}" >&2
      missing=1
    fi
  done
  if [[ "${missing}" -ne 0 ]]; then
    exit 1
  fi
}

validate_ipv4() {
  local ip="$1"
  if [[ ! "${ip}" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
    echo "Ошибка: некорректный IPv4-адрес: ${ip}" >&2
    exit 1
  fi
  IFS='.' read -r o1 o2 o3 o4 <<<"${ip}"
  for o in "$o1" "$o2" "$o3" "$o4"; do
    if (( o < 0 || o > 255 )); then
      echo "Ошибка: некорректный октет IPv4 в адресе ${ip}" >&2
      exit 1
    fi
  done
}

class_id_for_ip() {
  local ip="$1"
  local o1 o2 o3 o4
  IFS='.' read -r o1 o2 o3 o4 <<<"${ip}"
  local value=$(( (o3 * 256 + o4) % 65000 + 100 ))
  echo "${value}"
}

ensure_interfaces() {
  ip link show "${WG_IFACE}" >/dev/null 2>&1 || {
    echo "Ошибка: интерфейс ${WG_IFACE} не найден." >&2
    exit 1
  }

  modprobe ifb >/dev/null 2>&1 || true
  if ! ip link show "${IFB_IFACE}" >/dev/null 2>&1; then
    ip link add "${IFB_IFACE}" type ifb
  fi
  ip link set "${IFB_IFACE}" up
}

ensure_base_qdisc() {
  tc qdisc add dev "${WG_IFACE}" root handle 1: htb default "${DEFAULT_CLASS_ID}" 2>/dev/null \
    || tc qdisc change dev "${WG_IFACE}" root handle 1: htb default "${DEFAULT_CLASS_ID}"
  tc class add dev "${WG_IFACE}" parent 1: classid 1:1 htb rate "${ROOT_RATE}" ceil "${ROOT_RATE}" 2>/dev/null \
    || tc class change dev "${WG_IFACE}" parent 1: classid 1:1 htb rate "${ROOT_RATE}" ceil "${ROOT_RATE}"
  tc class add dev "${WG_IFACE}" parent 1:1 classid 1:${DEFAULT_CLASS_ID} htb rate "${ROOT_RATE}" ceil "${ROOT_RATE}" 2>/dev/null \
    || tc class change dev "${WG_IFACE}" parent 1:1 classid 1:${DEFAULT_CLASS_ID} htb rate "${ROOT_RATE}" ceil "${ROOT_RATE}"

  if ! tc qdisc show dev "${WG_IFACE}" | grep -q "ingress ffff:"; then
    tc qdisc add dev "${WG_IFACE}" handle ffff: ingress
  fi
  if ! tc filter show dev "${WG_IFACE}" parent ffff: | grep -q "mirred.*${IFB_IFACE}"; then
    tc filter add dev "${WG_IFACE}" parent ffff: protocol ip u32 \
      match u32 0 0 action mirred egress redirect dev "${IFB_IFACE}"
  fi

  tc qdisc add dev "${IFB_IFACE}" root handle 2: htb default "${DEFAULT_CLASS_ID}" 2>/dev/null \
    || tc qdisc change dev "${IFB_IFACE}" root handle 2: htb default "${DEFAULT_CLASS_ID}"
  tc class add dev "${IFB_IFACE}" parent 2: classid 2:1 htb rate "${ROOT_RATE}" ceil "${ROOT_RATE}" 2>/dev/null \
    || tc class change dev "${IFB_IFACE}" parent 2: classid 2:1 htb rate "${ROOT_RATE}" ceil "${ROOT_RATE}"
  tc class add dev "${IFB_IFACE}" parent 2:1 classid 2:${DEFAULT_CLASS_ID} htb rate "${ROOT_RATE}" ceil "${ROOT_RATE}" 2>/dev/null \
    || tc class change dev "${IFB_IFACE}" parent 2:1 classid 2:${DEFAULT_CLASS_ID} htb rate "${ROOT_RATE}" ceil "${ROOT_RATE}"
}

add_limit() {
  local ip="$1"
  local rate="$2"
  validate_ipv4 "${ip}"

  local cid
  cid="$(class_id_for_ip "${ip}")"

  ensure_interfaces
  ensure_base_qdisc

  # Ограничение download: трафик сервер -> клиент (dst client_ip) на WG интерфейсе.
  tc class add dev "${WG_IFACE}" parent 1:1 classid 1:${cid} htb rate "${rate}" ceil "${rate}" 2>/dev/null \
    || tc class change dev "${WG_IFACE}" parent 1:1 classid 1:${cid} htb rate "${rate}" ceil "${rate}"

  # Удаляем старый фильтр для class id перед добавлением нового.
  tc filter show dev "${WG_IFACE}" parent 1: \
    | awk '/flowid 1:'"${cid}"'/{print $0}' \
    | while read -r _; do
        tc filter del dev "${WG_IFACE}" parent 1: protocol ip prio 10 u32 \
          match ip dst "${ip}"/32 flowid 1:${cid} 2>/dev/null || true
      done

  tc filter del dev "${WG_IFACE}" parent 1: protocol ip prio 10 u32 \
    match ip dst "${ip}"/32 flowid 1:${cid} 2>/dev/null || true
  tc filter add dev "${WG_IFACE}" protocol ip parent 1: prio 10 u32 \
    match ip dst "${ip}"/32 flowid 1:${cid}

  # Ограничение upload: трафик клиент -> сервер (src client_ip), перенаправленный в ifb.
  tc class add dev "${IFB_IFACE}" parent 2:1 classid 2:${cid} htb rate "${rate}" ceil "${rate}" 2>/dev/null \
    || tc class change dev "${IFB_IFACE}" parent 2:1 classid 2:${cid} htb rate "${rate}" ceil "${rate}"

  tc filter show dev "${IFB_IFACE}" parent 2: \
    | awk '/flowid 2:'"${cid}"'/{print $0}' \
    | while read -r _; do
        tc filter del dev "${IFB_IFACE}" parent 2: protocol ip prio 10 u32 \
          match ip src "${ip}"/32 flowid 2:${cid} 2>/dev/null || true
      done

  tc filter del dev "${IFB_IFACE}" parent 2: protocol ip prio 10 u32 \
    match ip src "${ip}"/32 flowid 2:${cid} 2>/dev/null || true
  tc filter add dev "${IFB_IFACE}" protocol ip parent 2: prio 10 u32 \
    match ip src "${ip}"/32 flowid 2:${cid}

  echo "Применен лимит ${rate} для ${ip} на ${WG_IFACE} (class id ${cid})."
}

del_limit() {
  local ip="$1"
  validate_ipv4 "${ip}"

  local cid
  cid="$(class_id_for_ip "${ip}")"

  tc filter del dev "${WG_IFACE}" parent 1: protocol ip prio 10 u32 \
    match ip dst "${ip}"/32 flowid 1:${cid} 2>/dev/null || true
  tc class del dev "${WG_IFACE}" classid 1:${cid} 2>/dev/null || true

  tc filter del dev "${IFB_IFACE}" parent 2: protocol ip prio 10 u32 \
    match ip src "${ip}"/32 flowid 2:${cid} 2>/dev/null || true
  tc class del dev "${IFB_IFACE}" classid 2:${cid} 2>/dev/null || true

  echo "Лимит для ${ip} удален (class id ${cid})."
}

show_state() {
  echo "=== qdisc: ${WG_IFACE} ==="
  tc -s qdisc show dev "${WG_IFACE}" || true
  echo
  echo "=== class: ${WG_IFACE} ==="
  tc -s class show dev "${WG_IFACE}" || true
  echo
  echo "=== filter: ${WG_IFACE} ==="
  tc filter show dev "${WG_IFACE}" parent 1: || true
  echo
  echo "=== ingress filter: ${WG_IFACE} ==="
  tc filter show dev "${WG_IFACE}" parent ffff: || true
  echo
  echo "=== qdisc: ${IFB_IFACE} ==="
  tc -s qdisc show dev "${IFB_IFACE}" || true
  echo
  echo "=== class: ${IFB_IFACE} ==="
  tc -s class show dev "${IFB_IFACE}" || true
  echo
  echo "=== filter: ${IFB_IFACE} ==="
  tc filter show dev "${IFB_IFACE}" parent 2: || true
}

reset_all() {
  tc qdisc del dev "${WG_IFACE}" root 2>/dev/null || true
  tc qdisc del dev "${WG_IFACE}" ingress 2>/dev/null || true
  tc qdisc del dev "${IFB_IFACE}" root 2>/dev/null || true

  if ip link show "${IFB_IFACE}" >/dev/null 2>&1; then
    ip link set "${IFB_IFACE}" down || true
    ip link del "${IFB_IFACE}" type ifb || true
  fi

  echo "Сброс выполнен для ${WG_IFACE}/${IFB_IFACE}."
}

main() {
  require_root
  require_cmds

  if [[ $# -lt 1 ]]; then
    usage
    exit 1
  fi

  case "$1" in
    add)
      [[ $# -eq 3 ]] || { usage; exit 1; }
      add_limit "$2" "$3"
      ;;
    del)
      [[ $# -eq 2 ]] || { usage; exit 1; }
      del_limit "$2"
      ;;
    show)
      [[ $# -eq 1 ]] || { usage; exit 1; }
      show_state
      ;;
    reset)
      [[ $# -eq 1 ]] || { usage; exit 1; }
      reset_all
      ;;
    *)
      usage
      exit 1
      ;;
  esac
}

main "$@"
