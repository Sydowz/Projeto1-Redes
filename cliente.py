import socket
import threading

HOST = "127.0.0.1"
PORT = 5000


def conectar_cliente():
    """Cria o socket do cliente e conecta ao servidor."""
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((HOST, PORT))
    return client


def thread_receber_mensagem(client):
    """Fica em loop recebendo mensagens do servidor."""
    while True:
        try:
            message = client.recv(1024).decode()
        except OSError:
            break

        if not message:
            print("Leilao encerrado! Pressione Enter para sair.")
            break

        print(message, end="")


def thread_enviar_mensagem(client):
    """Fica em loop lendo entrada do usuario e enviando ao servidor."""
    while True:
        try:
            message = input()
        except EOFError:
            message = ":quit"

        try:
            client.send(message.encode())
        except OSError:
            break

        if message == ":quit":
            break


def main_cliente():
    """Ponto de entrada do cliente."""
    client = conectar_cliente()

    t_receive = threading.Thread(target=thread_receber_mensagem, args=(client,))
    t_send = threading.Thread(target=thread_enviar_mensagem, args=(client,))

    t_receive.start()
    t_send.start()

    t_receive.join()
    t_send.join()

    try:
        client.close()
    except OSError:
        pass


if __name__ == "__main__":
    main_cliente()
