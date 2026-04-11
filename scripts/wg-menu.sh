#!/bin/bash

# Путь к нашему основному скрипту лимитирования (находится в этой же папке)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
LIMIT_SCRIPT="$SCRIPT_DIR/wg-limit.sh"
CONTAINER_NAME="amnezia-wg-easy"

# Проверка запуска от root
if [ "$EUID" -ne 0 ]; then
  echo "Пожалуйста, запустите скрипт с правами root (sudo)."
  exit 1
fi

# Проверка, существует ли скрипт wg-limit.sh
if [ ! -f "$LIMIT_SCRIPT" ]; then
    echo "Ошибка: Не найден скрипт $LIMIT_SCRIPT"
    exit 1
fi

# Проверяем, запущен ли контейнер
if ! docker ps --format '{{.Names}}' | grep -Eq "^${CONTAINER_NAME}\$"; then
    echo "Ошибка: Контейнер ${CONTAINER_NAME} не запущен в Docker."
    exit 1
fi

# Получаем PID контейнера для nsenter
PID=$(docker inspect -f '{{.State.Pid}}' "$CONTAINER_NAME")

echo "Сбор данных о клиентах из wg-easy..."
# Читаем конфигурацию из контейнера, чтобы вытащить имена и IP
CONFIG=$(docker exec "$CONTAINER_NAME" cat /etc/wireguard/wg0.conf 2>/dev/null)

# Парсим конфигурацию (ищем строки '# Client: Имя' и 'AllowedIPs = IP')
CLIENTS=$(echo "$CONFIG" | awk '
    /^# Client: / { name=$0; sub(/^# Client: /, "", name); sub(/ \(.*$/, "", name); }
    /^# Name: / { name=$0; sub(/^# Name: /, "", name); sub(/ \(.*$/, "", name); }
    /^AllowedIPs/ {
        ip=$3; 
        sub(/\/.*$/, "", ip);
        if(name=="") name="Без имени";
        print ip "|" name;
        name="";
    }
')

if [ -z "$CLIENTS" ]; then
    echo "Клиенты не найдены. Создайте их сначала через веб-интерфейс."
    exit 1
fi

IFS=$'\n' read -r -d '' -a client_array <<< "$CLIENTS"

while true; do
    echo "============================================="
    echo "   МЕНЮ УПРАВЛЕНИЯ СКОРОСТЬЮ (AmneziaWG)    "
    echo "============================================="
    echo "0) Выход"
    
    # Выводим список клиентов
    for i in "${!client_array[@]}"; do
        ip="${client_array[$i]%%|*}"
        name="${client_array[$i]#*|}"
        echo "$((i+1))) $name ($ip)"
    done
    echo "---------------------------------------------"
    
    read -p "Выберите номер клиента (0-${#client_array[@]}): " choice
    
    if [[ "$choice" == "0" ]]; then
        echo "Выход."
        break
    fi
    
    index=$((choice-1))
    if [[ -n "${client_array[$index]}" ]]; then
        selected_ip="${client_array[$index]%%|*}"
        selected_name="${client_array[$index]#*|}"
        
        echo ""
        echo "=> Выбран клиент: $selected_name ($selected_ip)"
        echo "   1) Установить лимит"
        echo "   2) Снять лимит"
        echo "   3) Назад"
        read -p "Действие: " action
        
        case $action in
            1)
                read -p "Скорость скачивания (например, 15mbit): " dl
                read -p "Скорость отдачи (например, 15mbit): " ul
                echo "=> Применяем лимиты в контейнере..."
                # Запускаем целевой скрипт в нужном неймспейсе
                nsenter -t "$PID" -n "$LIMIT_SCRIPT" start "$selected_ip" "$dl" "$ul"
                echo "Готово!"
                echo ""
                ;;
            2)
                echo "=> Снимаем лимиты..."
                nsenter -t "$PID" -n "$LIMIT_SCRIPT" stop "$selected_ip"
                echo "Готово!"
                echo ""
                ;;
            *)
                echo "Действие отменено."
                echo ""
                ;;
        esac
    else
        echo "Неверный выбор. Пожалуйста, введите цифру из списка."
        echo ""
    fi
done
