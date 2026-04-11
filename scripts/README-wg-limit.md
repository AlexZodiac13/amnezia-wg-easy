# wg-limit.sh

Скрипт для ограничения скорости клиентов WireGuard/AmneziaWG через `tc` + `ifb`.

Поддерживаемые команды:

- `add <client_ipv4> <rate>` — установить лимит клиенту
- `del <client_ipv4>` — удалить лимит клиента
- `show` — показать активные правила и счетчики
- `reset` — удалить все правила shaping

## Требования

- Linux с `tc` (`iproute2`)
- root-права
- интерфейс WireGuard/AmneziaWG (`wg0` по умолчанию)
- для сценария с Docker: запуск в network namespace контейнера (`nsenter`)

## Быстрый старт (Docker + wg-easy)

Ниже универсальный сценарий, когда интерфейс `wg0` существует внутри контейнера `amnezia-wg-easy`.

```bash
cd /home/docker/amnezia-wg
chmod +x ./wg-limit.sh

CONTAINER=amnezia-wg-easy
SCRIPT=/home/docker/amnezia-wg/wg-limit.sh
PID=$(sudo docker inspect -f '{{.State.Pid}}' "$CONTAINER")

# Проверка интерфейса внутри namespace контейнера
sudo nsenter -t "$PID" -n ip -br link | grep -E 'wg|awg'

# Сброс старых правил
sudo nsenter -t "$PID" -n "$SCRIPT" reset

# Применить лимит: 20mbit для клиента 10.10.0.3
sudo nsenter -t "$PID" -n env ROOT_RATE=300mbit "$SCRIPT" add 10.10.0.3 20mbit

# Проверка счетчиков
sudo nsenter -t "$PID" -n "$SCRIPT" show
```

## Локальный запуск (без Docker)

Если интерфейс существует на хосте:

```bash
sudo WG_IFACE=wg0 ./scripts/wg-limit.sh add 10.10.0.3 20mbit
sudo WG_IFACE=wg0 ./scripts/wg-limit.sh show
```

## Удаление лимита

```bash
sudo nsenter -t "$PID" -n "$SCRIPT" del 10.10.0.3
```

## Полный сброс

```bash
sudo nsenter -t "$PID" -n "$SCRIPT" reset
```

## Параметры окружения

- `WG_IFACE` — интерфейс VPN (по умолчанию `wg0`)
- `IFB_IFACE` — служебный ifb интерфейс (по умолчанию `ifb0`)
- `ROOT_RATE` — базовая скорость корневого класса (по умолчанию `10gbit`)
- `DEFAULT_CLASS_ID` — class id по умолчанию (по умолчанию `999`)

Рекомендуется выставлять `ROOT_RATE` ближе к реальной пропускной способности сервера, например `300mbit`, чтобы уменьшить предупреждения HTB про quantum.

## Частые проблемы

1. `Ошибка: интерфейс wg0 не найден.`

Скрипт запущен в namespace хоста, а интерфейс находится в контейнере.
Используйте запуск через `nsenter`.

2. `Change operation not supported by specified qdisc.`

Обычно это следы старых правил/несовместимости.
Сначала выполните `reset`, потом `add`.

3. Лимит не ощущается

Проверьте IP клиента, подсеть (например `10.10.0.x`) и рост счетчиков через `show`.
