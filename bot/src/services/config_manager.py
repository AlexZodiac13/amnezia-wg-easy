import qrcode
from io import BytesIO
import json
import base64
from datetime import datetime, timedelta
import logging
import os

logger = logging.getLogger(__name__)

class ConfigManager:
    """Управление конфигами клиентов"""
    
    BACKUP_TEMPLATE_PATH = os.getenv("AMNEZIA_BACKUP_TEMPLATE_PATH", "/app/AmneziaVPN.backup")

    
    @staticmethod
    def parse_wg_config(config_content: str) -> dict:
        """Парсить WireGuard конфиг"""
        data = {}
        current_section = None
        
        for line in config_content.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            if line.startswith('['):
                current_section = line.strip('[]').lower()
                if current_section not in data:
                    data[current_section] = {}
            elif '=' in line and current_section:
                key, value = line.split('=', 1)
                data[current_section][key.strip()] = value.strip()
        
        return data
    
    @staticmethod
    def generate_qr_code(config_content: str) -> bytes:
        """Сгенерировать QR-код для конфига"""
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(config_content)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            buf = BytesIO()
            img.save(buf, format='PNG')
            buf.seek(0)
            return buf.getvalue()
        except Exception as e:
            logger.error(f"Failed to generate QR code: {str(e)}")
            return None
    
    @staticmethod
    def generate_amnezia_backup(config_content: str, client_name: str) -> dict:
        """Генерировать JSON бекап для приложения Amnezia"""
        parsed = ConfigManager.parse_wg_config(config_content)
        
        backup = {
            "name": client_name,
            "interface": {
                "privateKey": parsed.get("interface", {}).get("PrivateKey", ""),
                "address": parsed.get("interface", {}).get("Address", ""),
                "mtu": int(parsed.get("interface", {}).get("MTU", "1280")),
                "dns": parsed.get("interface", {}).get("DNS", "").split(", "),
            },
            "peer": {
                "publicKey": parsed.get("peer", {}).get("PublicKey", ""),
                "presharedKey": parsed.get("peer", {}).get("PresharedKey", ""),
                "endpoint": parsed.get("peer", {}).get("Endpoint", ""),
                "allowedIPs": parsed.get("peer", {}).get("AllowedIPs", "").split(", "),
                "persistentKeepalive": int(parsed.get("peer", {}).get("PersistentKeepalive", "0")),
            },
            "createdAt": datetime.utcnow().isoformat(),
        }
        
        return backup
    
    @staticmethod
    def generate_amnezia_backup_full(config_content: str, client_name: str, server_endpoint: str = "wg.owgrant.com") -> dict:
        """Генерировать полный JSON бекап Amnezia с применением пользовательского конфига к шаблону.
        
        Загружает базовый backup с параметрами приложения (язык, приложения, режимы обхода)
        и подставляет пользовательский конфиг WireGuard.
        """
        try:
            parsed = ConfigManager.parse_wg_config(config_content)
            
            # Загружаем шаблонный backup файл
            backup_data = {}
            if os.path.exists(ConfigManager.BACKUP_TEMPLATE_PATH):
                try:
                    with open(ConfigManager.BACKUP_TEMPLATE_PATH, 'r', encoding='utf-8') as f:
                        backup_data = json.load(f)
                except Exception as e:
                    logger.warning(f"Failed to load backup template: {e}")
                    backup_data = {}
            
            # Если шаблон не загружен или пуст, используем минимальную структуру
            if not backup_data:
                backup_data = {
                    "AppPlatform": "Android",
                    "Conf/appLanguage": "ru_RU",
                    "Conf/autoStart": False,
                    "Conf/killSwitchEnabled": True,
                    "Conf/useAmneziaDns": True,
                    "Conf/appsSplitTunnelingEnabled": True,
                    "Conf/appsRouteMode": 1,
                    "Conf/routeMode": 1,
                    "Conf/ForwardApps": [],
                    "Conf/ExceptApps": [],
                }
            
            # Извлекаем пользовательский конфиг
            client_private_key = parsed.get("interface", {}).get("PrivateKey", "")
            client_ip = parsed.get("interface", {}).get("Address", "")
            mtu = parsed.get("interface", {}).get("MTU", "1280")
            dns = parsed.get("interface", {}).get("DNS", "10.80.0.1")
            
            # Параметры сервера
            server_pub_key = parsed.get("peer", {}).get("PublicKey", "")
            psk_key = parsed.get("peer", {}).get("PresharedKey", "")
            endpoint = parsed.get("peer", {}).get("Endpoint", f"{server_endpoint}:5066")
            allowed_ips = parsed.get("peer", {}).get("AllowedIPs", "0.0.0.0/0, ::/0").split(", ")
            persistent_keep_alive = parsed.get("peer", {}).get("PersistentKeepalive", "25")
            
            # Параметры AmneziaWG v2
            jc = parsed.get("interface", {}).get("Jc", "6")
            jmin = parsed.get("interface", {}).get("Jmin", "50")
            jmax = parsed.get("interface", {}).get("Jmax", "1000")
            s1 = parsed.get("interface", {}).get("S1", "68")
            s2 = parsed.get("interface", {}).get("S2", "149")
            s3 = parsed.get("interface", {}).get("S3", "64")
            s4 = parsed.get("interface", {}).get("S4", "16")
            h1 = parsed.get("interface", {}).get("H1", "471800590-471800690")
            h2 = parsed.get("interface", {}).get("H2", "1246894907-1246895000")
            h3 = parsed.get("interface", {}).get("H3", "923637689-923637780")
            h4 = parsed.get("interface", {}).get("H4", "1769581055-1869581055")
            i1 = parsed.get("interface", {}).get("I1", "")
            i2 = parsed.get("interface", {}).get("I2", "")
            
            # Парсим Servers/serversList если он есть
            servers_list = []
            servers_list_was_string = False
            if "Servers/serversList" in backup_data:
                try:
                    servers_list_value = backup_data["Servers/serversList"]
                    if isinstance(servers_list_value, str):
                        servers_list_was_string = True
                        servers_list = json.loads(servers_list_value)
                    else:
                        servers_list = servers_list_value
                except (json.JSONDecodeError, TypeError):
                    servers_list = []
            
            # Если нет серверов, создаём структуру
            if not servers_list:
                servers_list = [{
                    "containers": [],
                    "defaultContainer": "amnezia-awg",
                    "description": "Пользовательский сервер",
                    "hostName": endpoint.split(':')[0] if ':' in endpoint else endpoint
                }]
            
            # Обновляем первый сервер (основной) с пользовательским конфигом
            primary_server = servers_list[0]
            if "containers" not in primary_server or not primary_server["containers"]:
                primary_server["containers"] = [{"awg": {}, "container": "amnezia-awg"}]
            
            existing_container = primary_server["containers"][0]
            existing_awg = existing_container.get("awg", {})
            
            # Создаём объект конфигурации для Amnezia, сохраняя шаблонные поля
            awg_config = {
                "H1": h1,
                "H2": h2,
                "H3": h3,
                "H4": h4,
                "I1": i1,
                "I2": i2,
                "Jc": jc,
                "Jmax": jmax,
                "Jmin": jmin,
                "S1": s1,
                "S2": s2,
                "S3": s3,
                "S4": s4,
                "allowed_ips": [ip.strip() for ip in allowed_ips],
                "client_ip": client_ip,
                "client_priv_key": client_private_key,
                "config": config_content,
                "hostName": endpoint.split(':')[0] if ':' in endpoint else endpoint,
                "mtu": mtu,
                "persistent_keep_alive": persistent_keep_alive,
                "port": int(endpoint.split(':')[1]) if ':' in endpoint else 5066,
                "psk_key": psk_key,
                "server_pub_key": server_pub_key
            }
            
            # Обновляем last_config если он есть
            if "last_config" in existing_awg:
                try:
                    last_config_obj = json.loads(existing_awg["last_config"])
                    last_config_obj.update(awg_config)
                    existing_awg["last_config"] = json.dumps(last_config_obj, indent=4)
                except (json.JSONDecodeError, TypeError):
                    existing_awg["last_config"] = json.dumps(awg_config, indent=4)
            else:
                existing_awg["last_config"] = json.dumps(awg_config, indent=4)
            
            # Не добавляем поля AWG на верхний уровень, чтобы избежать дублирования
            # existing_awg.update(awg_config)
            existing_container["awg"] = existing_awg
            existing_container["container"] = existing_container.get("container", "amnezia-awg")
            primary_server["containers"] = [existing_container]
            primary_server["hostName"] = endpoint.split(':')[0] if ':' in endpoint else endpoint
            
            # Обновляем список серверов в backup
            backup_data["Servers/serversList"] = json.dumps(servers_list, indent=4) if servers_list_was_string else servers_list
            backup_data["Servers/defaultServerIndex"] = 0
            
            return backup_data
            
        except Exception as e:
            logger.error(f"Failed to generate full amnezia backup: {e}")
            return {}
    
    @staticmethod
    def create_setup_instruction(config_format: str = "android") -> str:

        """Создать инструкцию по настройке"""
        instruction_ru = """
📱 **Инструкция по настройке Amnezia VPN**

**Для Android:**
1. Загрузите приложение Amnezia VPN из Google Play
2. Нажмите кнопку "+" для добавления нового сервера
3. Выберите опцию "Импорт из QR-кода" или загрузите файл конфига
4. Скопируйте текст конфига в буфер обмена и нажмите "Вставить"
5. Убедитесь, что выборочный обход включен
6. Нажмите "Подключиться"

**Для iOS:**
1. Загрузите приложение Amnezia VPN из App Store
2. Нажмите кнопку "+" для добавления конфига
3. Отсканируйте QR-код или импортируйте файл
4. Проверьте настройки и подключитесь

**Для Windows/macOS:**
1. Скачайте приложение Amnezia
2. Откройте приложение и импортируйте конфиг через QR-код или файл
3. Выберите правильную конфигурацию и подключитесь

❗ **Важно:** Ваш конфиг действителен 30 дней с момента создания.
Вы получите уведомление за 3 дня до истечения срока действия.
        """
        return instruction_ru
