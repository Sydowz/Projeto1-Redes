import socket
import threading

HOST = "127.0.0.1"
PORT = 5000


def conectar_cliente():
    """Cria o socket do cliente e conecta ao servidor."""
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((HOST, PORT))
    return client


def main_cliente():
    """Ponto de entrada do cliente."""
    client = conectar_cliente()
    print("Cliente conectado ao servidor.")
    client.close()


if __name__ == "__main__":
    main_cliente()
