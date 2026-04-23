import qrcode
from io import BytesIO
import json
import base64
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class ConfigManager:
    """Управление конфигами клиентов"""
    
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
