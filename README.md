# AmneziaWG v2: AWG core

Этот этап поднимает AWG-сервер через `awg-quick` с userspace fallback на `amneziawg-go`.

## Что уже сделано

- Контейнер `awg-core` на базе `awg-quick` и `amneziawg-go`.
- Режим сети: `host`.
- Порт сервера: `5060/udp` (настраивается через env).
- Интерфейс: `awg0`.
- Скрипты управления peer через `awg`:
  - `/opt/awg/scripts/add-peer.sh`
  - `/opt/awg/scripts/remove-peer.sh`
  - `/opt/awg/scripts/list-peers.sh`

Конфиг хранится в `/etc/amnezia/amneziawg/awg0.conf`.
Опционально можно задать `AWG_I1`-`AWG_I5` для signature packets AmneziaWG 2.0; по умолчанию они пустые.

## Запуск

```bash
docker compose up -d --build
docker compose logs -f awg
```

## Проверка интерфейса

```bash
docker exec -it awg-core ip a show awg0
docker exec -it awg-core awg show awg0
```

## Управление peer

Создать клиента и добавить peer:

```bash
docker exec -it awg-core /opt/awg/scripts/add-peer.sh awg0 <CLIENT_NAME> <SERVER_IP_OR_DOMAIN>:5066 10.80.0.2/32
```

Если нужен только ручной режим без генерации клиента, скрипт по-прежнему принимает старый формат:

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

## Как создать клиента для проверки

1. Сгенерируйте ключи клиента:

```bash
awg genkey | tee client_private.key | awg pubkey > client_public.key
```

2. Возьмите `Server public key` из лога контейнера или из файла `./awg/data/server_public.key`.

3. Создайте клиентский конфиг, например `client.conf`:

```ini
[Interface]
PrivateKey = <CLIENT_PRIVATE_KEY>
Address = 10.80.0.2/32
DNS = 1.1.1.1

Jc = 7
Jmin = 50
Jmax = 1000
S1 = 68
S2 = 149
S3 = 32
S4 = 16
H1 = 471800590-471800690
H2 = 1246894907-1246895000
H3 = 923637689-923637690
H4 = 1769581055-1869581055

# i1-i5 опциональны. Если хотите проверить signature packets, задайте их и на клиенте.
I1 = QUIC:50:0a0b0c0d0e0f1011121314
I2 = DNS:50:000100000001000000000000

[Peer]
PublicKey = <SERVER_PUBLIC_KEY>
Endpoint = <SERVER_IP_OR_DOMAIN>:5066
AllowedIPs = 0.0.0.0/0, ::/0
PersistentKeepalive = 25
```

4. Скрипт уже создаст peer на сервере и сохранит клиентские файлы:

- `./awg/data/clients/<CLIENT_NAME>.privatekey`
- `./awg/data/clients/<CLIENT_NAME>.publickey`
- `./awg/data/clients/<CLIENT_NAME>.conf`

5. Импортируйте `client.conf` в AmneziaVPN или используйте его в любом AWG/WireGuard-клиенте, который поддерживает AmneziaWG 2.0.