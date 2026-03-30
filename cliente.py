import socket
import threading
import sys

HOST = "127.0.0.1"
PORT = 5000
PROMPT = "> "


def conectar_cliente():
    """Cria o socket do cliente e conecta ao servidor."""
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.settimeout(5.0)
    try:
        client.connect((HOST, PORT))
    finally:
        try:
            client.settimeout(1.0)
        except OSError:
            pass
    return client


def thread_receber_mensagem(client, stop_event: threading.Event):
    """Fica em loop recebendo mensagens do servidor."""
    while not stop_event.is_set():
        try:
            message = client.recv(1024).decode()
        except socket.timeout:
            continue
        except OSError:
            break
        if not message:
            print("\nServidor desconectou.")
            stop_event.set()
            break
        # Se o usuário estiver digitando, força uma quebra de linha e redesenha o prompt
        if not message.endswith("\n"):
            message += "\n"
        sys.stdout.write("\n" + message)
        sys.stdout.write(PROMPT)
        sys.stdout.flush()
    stop_event.set()


def thread_enviar_mensagem(client, stop_event: threading.Event):
    """Fica em loop lendo entrada do usuario e enviando ao servidor."""
    while not stop_event.is_set():
        try:
            message = input(PROMPT)
        except EOFError:
            message = ":quit"
        except KeyboardInterrupt:
            message = ":quit"
        try:
            client.sendall(message.encode())
        except OSError:
            stop_event.set()
            break
        if message == ":quit":
            stop_event.set()
            break


def main_cliente():
    """Ponto de entrada do cliente."""
    try:
        client = conectar_cliente()
    except (ConnectionRefusedError, TimeoutError, OSError):
        print("Não foi possível conectar ao servidor.")
        return

    stop_event = threading.Event()

    t_receive = threading.Thread(target=thread_receber_mensagem, args=(client, stop_event))
    t_send = threading.Thread(target=thread_enviar_mensagem, args=(client, stop_event))
    t_send.daemon = True  # não ficar preso no input() quando o servidor cair

    t_receive.start()
    t_send.start()

    t_receive.join()
    stop_event.set()

    try:
        try:
            client.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        client.close()
    except OSError:
        pass


if __name__ == "__main__":
    try:
        main_cliente()
    except KeyboardInterrupt:
        pass
