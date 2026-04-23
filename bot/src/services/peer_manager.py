import subprocess
import json
import os
import socket
from pathlib import Path
from src.config import Config
import logging

logger = logging.getLogger(__name__)

class PeerManager:
    """Управление WireGuard пирами через скрипты"""

    @staticmethod
    def _docker_request(method: str, path: str, body: dict | None = None) -> dict:
        payload = json.dumps(body).encode() if body is not None else b""
        request = [
            f"{method} {path} HTTP/1.1",
            "Host: docker",
            f"Content-Length: {len(payload)}",
            "Content-Type: application/json",
            "",
            "",
        ]
        request_bytes = "\r\n".join(request).encode() + payload

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect("/var/run/docker.sock")
        sock.sendall(request_bytes)

        response = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
        sock.close()

        header_blob, _, response_body = response.partition(b"\r\n\r\n")
        header_lines = header_blob.decode(errors="replace").splitlines()
        status_line = header_lines[0] if header_lines else "HTTP/1.1 500"
        status_code = int(status_line.split()[1])

        return {
            "status_code": status_code,
            "body": response_body,
        }

    @staticmethod
    def _run_script_in_awg(script_name: str, args: list[str]) -> subprocess.CompletedProcess:
        """Выполняет скрипт внутри контейнера awg-core через Docker Engine API."""
        container_name = Config.AWG_CONTAINER_NAME
        script_path = f"/opt/awg/scripts/{script_name}"
        create_response = PeerManager._docker_request(
            "POST",
            f"/containers/{container_name}/exec",
            {
                "AttachStdout": True,
                "AttachStderr": True,
                "Tty": False,
                "Cmd": ["bash", script_path, *args],
            },
        )

        if create_response["status_code"] >= 400:
            return subprocess.CompletedProcess(
                args=["docker-api", container_name, script_path, *args],
                returncode=create_response["status_code"],
                stdout="",
                stderr=create_response["body"].decode(errors="replace"),
            )

        exec_id = json.loads(create_response["body"].decode())["Id"]
        start_response = PeerManager._docker_request(
            "POST",
            f"/exec/{exec_id}/start",
            {"Detach": False, "Tty": False},
        )

        if start_response["status_code"] >= 400:
            return subprocess.CompletedProcess(
                args=["docker-api", container_name, script_path, *args],
                returncode=start_response["status_code"],
                stdout="",
                stderr=start_response["body"].decode(errors="replace"),
            )

        inspect_response = PeerManager._docker_request("GET", f"/exec/{exec_id}/json")
        exit_code = 0
        if inspect_response["status_code"] < 400:
            exit_code = json.loads(inspect_response["body"].decode()).get("ExitCode", 0)

        return subprocess.CompletedProcess(
            args=["docker-api", container_name, script_path, *args],
            returncode=exit_code,
            stdout=start_response["body"].decode(errors="replace"),
            stderr="",
        )
    
    @staticmethod
    async def add_peer(
        client_name: str,
        client_ip: str,
        rate_limit: int = 15,
        endpoint: str = None
    ) -> dict:
        """Добавить нового пира"""
        try:
            # Скрипт выполняется в awg контейнере
            result = PeerManager._run_script_in_awg(
                "add-peer.sh",
                [
                Config.AWG_INTERFACE,
                client_name,
                endpoint or f"{os.environ.get('SERVER_ENDPOINT', 'example.com')}:{Config.AWG_LISTEN_PORT}",
                client_ip + "/32",
                "",  # preshared_key (пусто, будет сгенерирован)
                str(rate_limit)
                ],
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to add peer: {result.stderr}")
                return {"success": False, "error": result.stderr}
            
            logger.info(f"Peer {client_name} added successfully")
            
            # Считать конфиг файл
            config_path = os.path.join(Config.CONFIGS_DIR, f"{client_name}.conf")
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config_content = f.read()
            else:
                config_content = result.stdout
            
            return {
                "success": True,
                "message": "Peer added",
                "config": config_content
            }
        
        except Exception as e:
            logger.error(f"Exception in add_peer: {str(e)}")
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
                                cmd = ["bash", "-c", f"echo {private_key} | wg pubkey"]
                                result = subprocess.run(cmd, capture_output=True, text=True)
                                client_public_key = result.stdout.strip()
                                break
            
            if not client_public_key:
                return {"success": False, "error": "Public key not found"}

            result = PeerManager._run_script_in_awg(
                "remove-peer.sh",
                [Config.AWG_INTERFACE, client_public_key],
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to remove peer: {result.stderr}")
                return {"success": False, "error": result.stderr}
            
            logger.info(f"Peer {client_name} removed successfully")
            return {"success": True, "message": "Peer removed"}
        
        except Exception as e:
            logger.error(f"Exception in remove_peer: {str(e)}")
            return {"success": False, "error": str(e)}
