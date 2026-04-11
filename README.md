# AmneziaWG Easy

## 1. Подготовка хоста (модуль ядра)
Для работы контейнера на сервере должен быть установлен модуль ядра `amneziawg`.

Для Debian/Ubuntu:
```bash
sudo apt install -y software-properties-common python3-launchpadlib gnupg2 linux-headers-$(uname -r)
sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 57290828
echo "deb https://ppa.launchpadcontent.net/amnezia/ppa/ubuntu focal main" | sudo tee -a /etc/apt/sources.list
echo "deb-src https://ppa.launchpadcontent.net/amnezia/ppa/ubuntu focal main" | sudo tee -a /etc/apt/sources.list
sudo apt-get update
sudo apt-get install -y amneziawg
```
Подробности [amnezia-vpn](https://github.com/amnezia-vpn/amneziawg-linux-kernel-module)

## 2. Запуск VPN
Убедитесь, что настроен файл `docker-compose.yml` (пароли, порты). Настройки сохраняются в папке `amnezia-data`.

Запуск:
```bash
docker compose up -d
```

## 3. Ограничение скорости
Для установки лимитов скорости (шейпинга) для конкретных клиентов используйте интерактивный скрипт. Он автоматически подключается к неймспейсу контейнера и применяет правила `tc`.

Запуск меню:
```bash
sudo ./scripts/wg-menu.sh
```

В меню доступно:
- Просмотр списка клиентов и их IP-адресов.
- Установка симметричного лимита (например, `15mbit` или `2000kbit`).
- Снятие лимита с клиента.

*Примечание: скрипты требуют выполнения от пользователя root (sudo).*
