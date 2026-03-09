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
    """Cria socket do servidor e aguarda uma conexao."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(1)
    print("Servidor pronto para receber conexao.")
    return server


def main():
    server = iniciar_servidor()
    print("Estrutura inicial criada (Commit 1).")
    server.close()


if __name__ == "__main__":
    main()
