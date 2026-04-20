# AmneziaWG v2: AWG core

Этот этап включает только VPN-ядро на `amneziawg-go`.

## Что уже сделано

- Контейнер `awg-core` на базе `amneziawg-go`.
- Режим сети: `host`.
- Порт сервера: `5060/udp` (настраивается через env).
- Интерфейс: `awg0`.
- Скрипты управления peer через `wg`:
  - `/opt/awg/scripts/add-peer.sh`
  - `/opt/awg/scripts/remove-peer.sh`
  - `/opt/awg/scripts/list-peers.sh`

## Запуск

```bash
docker compose up -d --build
docker compose logs -f awg
```

## Проверка интерфейса

```bash
docker exec -it awg-core ip a show awg0
docker exec -it awg-core wg show awg0
```

## Управление peer

Добавить peer:

```bash
docker exec -it awg-core /opt/awg/scripts/add-peer.sh awg0 <CLIENT_PUBLIC_KEY> 10.80.0.2/32
```

Удалить peer:

```bash
docker exec -it awg-core /opt/awg/scripts/remove-peer.sh awg0 <CLIENT_PUBLIC_KEY>
```

Список peer:

```bash
docker exec -it awg-core /opt/awg/scripts/list-peers.sh awg0
```