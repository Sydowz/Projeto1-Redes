import socket
import threading
import time
import random
from datetime import datetime

HOST = "127.0.0.1"
PORT = 5000

# Configuracao inicial do leilao
ITEM = "Carro Velho"
LANCE_INICIAL = 10000

# Estado compartilhado do leilao
tempo = 60
encerrado = False
lance_atual = LANCE_INICIAL
vencedor = None

# Controle de concorrencia
lock = threading.Lock()


def iniciar_servidor():
    """Cria socket do servidor, aceita cliente e envia saudacao inicial."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(1)
    print("Servidor aguardando conexao...")

    conn, addr = server.accept()
    print(f"Cliente conectado: {addr}")

    horario = datetime.now().strftime("%H:%M:%S")
    conn.send(f"{horario}: CONECTADO!!\n".encode())
    conn.send(f"Item: {ITEM} | Lance inicial: R${LANCE_INICIAL}\n".encode())
    conn.send(f"Lance atual: R${lance_atual}\n".encode())

    conn.settimeout(1.0)
    return server, conn, addr


def main():
    server, conn, addr = iniciar_servidor()

    conn.close()
    server.close()


if __name__ == "__main__":
    main()
