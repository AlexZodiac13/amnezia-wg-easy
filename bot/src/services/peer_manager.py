import asyncio
import json
import os
import logging
from datetime import datetime
from src.config import Config
from src.services.config_manager import ConfigManager

logger = logging.getLogger(__name__)

class PeerManager:
    """Управление AmneziaWG через Docker Engine API (Async Mode)"""
    @staticmethod
    async def _docker_request(method: str, path: str, body: dict | None = None) -> dict:
        """Асинхронный HTTP запрос к Docker Unix Socket"""
        try:
            # Асинхронное подключение к сокету исключает зависание бота
            reader, writer = await asyncio.open_unix_connection("/var/run/docker.sock")

            payload = json.dumps(body).encode() if body is not None else b""
            request = (
                f"{method} {path} HTTP/1.1\r\n"
                f"Host: docker\r\n"
                f"Content-Length: {len(payload)}\r\n"
                f"Content-Type: application/json\r\n"
                f"Connection: close\r\n\r\n"
            ).encode() + payload

            writer.write(request)
            await writer.drain()

            response = b""
            while True:
                chunk = await reader.read(4096)
                if not chunk:
                    break
                response += chunk
            
            writer.close()
            await writer.wait_closed()

            header_blob, _, response_body = response.partition(b"\r\n\r\n")
            lines = header_blob.decode(errors="replace").splitlines()
            status_code = int(lines[0].split()[1]) if lines else 500

            return {"status_code": status_code, "body": response_body}
        except Exception as e:
            logger.error(f"Docker Socket Error: {e}")
            return {"status_code": 500, "body": str(e).encode()}

    @staticmethod
    async def _run_script_in_awg(script_name: str, args: list[str]):
        """Запуск скрипта внутри контейнера awg-core через API"""
        container = Config.AWG_CONTAINER_NAME
        script_path = f"/opt/awg/scripts/{script_name}"

        # 1. Создание exec-инстанса
        create_res = await PeerManager._docker_request(
            "POST", f"/containers/{container}/exec",
            {"AttachStdout": True, "AttachStderr": True, "Cmd": ["bash", script_path, *args]}
        )

        if create_res["status_code"] != 201:
            return 1, "", f"Docker Exec Create Failed: {create_res['status_code']}"

        exec_id = json.loads(create_res["body"])["Id"]

        # 2. Старт exec-инстанса
        start_res = await PeerManager._docker_request("POST", f"/exec/{exec_id}/start", {"Detach": False})

        # Docker возвращает поток в формате: [8 байт заголовка][данные]
        output = start_res["body"]
        clean_output = ""
        if len(output) > 8:
            # Убираем технические заголовки Docker, чтобы получить чистый текст конфига
            clean_output = output[8:].decode(errors="ignore").strip()

        return 0, clean_output, ""

    @staticmethod
    async def add_peer(client_name: str, client_ip: str, rate_limit: int = 15, endpoint: str = None) -> dict:
        """Добавить нового пира асинхронно"""
        try:
            server_url = os.environ.get('SERVER_ENDPOINT', 'wg.owgrant.com')
            args = [
                Config.AWG_INTERFACE,
                client_name,
                endpoint or f"{server_url}:{Config.AWG_LISTEN_PORT}",
                f"{client_ip}/32",
                "", # PSK (генерируется скриптом)
                str(rate_limit)
            ]

            exit_code, stdout, stderr = await PeerManager._run_script_in_awg("add-peer.sh", args)

            if exit_code != 0:
                return {"success": False, "error": stderr or "Script execution error"}

            # Пытаемся прочитать файл, если скрипт его создал, иначе берем из stdout
            config_path = os.path.join(Config.CONFIGS_DIR, f"{client_name}.conf")
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config_content = f.read()
            else:
                config_content = stdout

            if not config_content:
                return {"success": False, "error": "Empty config generated"}

            return {"success": True, "config": config_content}
        except Exception as e:
            logger.error(f"Critical error in add_peer: {e}")
            return {"success": False, "error": str(e)}
    
    @staticmethod
    async def remove_peer(client_name: str, client_public_key: str = None) -> dict:
        """Удалить пира"""
        try:
            # Если нет публичного ключа, получить его из файла конфига
            if not client_public_key:
                config_path = os.path.join(Config.CONFIGS_DIR, f"{client_name}.conf")
                if os.path.exists(config_path):
                    with open(config_path, 'r') as f:
                        for line in f:
                            if line.strip().startswith("PrivateKey"):
                                # Вычислить публичный ключ из приватного
                                private_key = line.split("=")[1].strip()
                                # Оставляем синхронный вызов для локальной утилиты wg,
                                # так как она обычно отрабатывает мгновенно
                                import subprocess
                                cmd = ["bash", "-c", f"echo {private_key} | wg pubkey"]
                                result = subprocess.run(cmd, capture_output=True, text=True)
                                client_public_key = result.stdout.strip()
                                break
            
            if not client_public_key:
                return {"success": False, "error": "Public key not found"}

            exit_code, stdout, stderr = await PeerManager._run_script_in_awg(
                "remove-peer.sh",
                [Config.AWG_INTERFACE, client_public_key],
            )
            
            if exit_code != 0:
                logger.error(f"Failed to remove peer: {stderr}")
                return {"success": False, "error": stderr}

            logger.info(f"Peer {client_name} removed successfully")
            return {"success": True, "message": "Peer removed"}
        
        except Exception as e:
            logger.error(f"Exception in remove_peer: {str(e)}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def generate_amnezia_backup(config_content: str, client_name: str) -> dict:
        """Генерировать JSON бекап с поддержкой параметров AmneziaWG v2"""
        parsed = ConfigManager.parse_wg_config(config_content)
        if "interface" not in parsed:
            return {}

        # Извлекаем специфические параметры AmneziaWG (Junk, Magic numbers)
        # Если их нет в конфиге, приложение будет использовать дефолтные
        backup = {
            "name": client_name,
            "interface": {
                "privateKey": parsed["interface"].get("PrivateKey", ""),
                "address": parsed["interface"].get("Address", ""),
                "mtu": int(parsed["interface"].get("MTU", "1280")),
                "dns": parsed["interface"].get("DNS", "1.1.1.1").split(", "),
                # Параметры AmneziaWG v2
                "junkPacketCount": int(parsed["interface"].get("JunkPacketCount", "3")),
                "junkPacketMinSize": int(parsed["interface"].get("JunkPacketMinSize", "50")),
                "junkPacketMaxSize": int(parsed["interface"].get("JunkPacketMaxSize", "1000")),
                "initPacketJunkSize": int(parsed["interface"].get("InitPacketJunkSize", "0")),
                "responsePacketJunkSize": int(parsed["interface"].get("ResponsePacketJunkSize", "0")),
                "initPacketMagicNumber": int(parsed["interface"].get("InitPacketMagicNumber", "1")),
                "responsePacketMagicNumber": int(parsed["interface"].get("ResponsePacketMagicNumber", "2")),
                "underloadPacketMagicNumber": int(parsed["interface"].get("UnderloadPacketMagicNumber", "3")),
                "transportPacketMagicNumber": int(parsed["interface"].get("TransportPacketMagicNumber", "4")),
            },
            "peer": {
                "publicKey": parsed.get("peer", {}).get("PublicKey", ""),
                "endpoint": parsed.get("peer", {}).get("Endpoint", ""),
                "allowedIPs": parsed.get("peer", {}).get("AllowedIPs", "0.0.0.0/0").split(", "),
                "persistentKeepalive": int(parsed.get("peer", {}).get("PersistentKeepalive", "25")),
            },
            "createdAt": datetime.utcnow().isoformat(),
        }
        return backup

