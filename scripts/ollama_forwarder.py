"""
VERA - Encaminhador TCP de Loopback para Ollama Local
Permite que os containers Docker acessem o daemon Ollama local (que escuta em 127.0.0.1:11434)
através da porta 11435 em todas as interfaces de rede (0.0.0.0).
"""
import sys
import socket
import select
import signal
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [OllamaForwarder]: %(message)s"
)
logger = logging.getLogger("ollama_forwarder")

LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = 11435
TARGET_HOST = "127.0.0.1"
TARGET_PORT = 11434
BUFFER_SIZE = 65536


def run_forwarder():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server.bind((LISTEN_HOST, LISTEN_PORT))
    except Exception as e:
        logger.error(f"Não foi possível vincular à porta {LISTEN_PORT}: {e}")
        sys.exit(1)

    server.listen(50)
    server.setblocking(False)
    logger.info(f"Encaminhador ativo em {LISTEN_HOST}:{LISTEN_PORT} -> {TARGET_HOST}:{TARGET_PORT}")

    inputs = [server]
    forwarding_map = {}

    def shutdown(signum, frame):
        logger.info("Encerrando encaminhador...")
        server.close()
        for sock in list(forwarding_map.keys()):
            sock.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    while True:
        try:
            readable, _, exceptional = select.select(inputs, [], inputs, 1.0)
        except select.error:
            break

        for s in readable:
            if s is server:
                try:
                    client_sock, client_addr = server.accept()
                    target_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    target_sock.connect((TARGET_HOST, TARGET_PORT))
                    target_sock.setblocking(False)
                    client_sock.setblocking(False)

                    inputs.append(client_sock)
                    inputs.append(target_sock)
                    forwarding_map[client_sock] = target_sock
                    forwarding_map[target_sock] = client_sock
                except Exception as e:
                    logger.warning(f"Erro ao estabelecer conexão de destino: {e}")
            else:
                dest_sock = forwarding_map.get(s)
                if dest_sock:
                    try:
                        data = s.recv(BUFFER_SIZE)
                        if data:
                            dest_sock.sendall(data)
                        else:
                            # Conexão fechada
                            inputs.remove(s)
                            inputs.remove(dest_sock)
                            del forwarding_map[s]
                            del forwarding_map[dest_sock]
                            s.close()
                            dest_sock.close()
                    except Exception:
                        if s in inputs:
                            inputs.remove(s)
                        if dest_sock in inputs:
                            inputs.remove(dest_sock)
                        forwarding_map.pop(s, None)
                        forwarding_map.pop(dest_sock, None)
                        s.close()
                        dest_sock.close()

        for s in exceptional:
            dest_sock = forwarding_map.get(s)
            if s in inputs:
                inputs.remove(s)
            if dest_sock and dest_sock in inputs:
                inputs.remove(dest_sock)
            forwarding_map.pop(s, None)
            forwarding_map.pop(dest_sock, None)
            s.close()
            if dest_sock:
                dest_sock.close()


if __name__ == "__main__":
    run_forwarder()
