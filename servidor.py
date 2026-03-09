import socket
import threading
import time

from datetime import datetime

HOST = "127.0.0.1"
PORT = 5000

# Configuracao inicial do leilao
ITEM = "Carro Velho"
INITIAL_BID = 10000

# Estado compartilhado do leilao
global_time = 60
closed = False
current_bid = INITIAL_BID
winner = None

# Controle de concorrencia
lock = threading.Lock()


def start_server():
    """Cria o socket do servidor, aceita cliente e envia a saudacao inicial."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(1)
    print("Servidor aguardando conexao...")

    conn, addr = server.accept()
    print(f"Cliente conectado: {addr}")

    current_time = datetime.now().strftime("%H:%M:%S")
    conn.send(f"{current_time}: CONECTADO!!\n".encode())
    conn.send(f"Item: {ITEM} | Lance inicial: R${INITIAL_BID}\n".encode())
    conn.send(f"Lance atual: R${current_bid}\n".encode())

    conn.settimeout(1.0)
    return server, conn, addr


def timer_thread():
    """Executa a contagem regressiva do leilao."""
    global global_time, closed
    while global_time > 0 and not closed:
        time.sleep(1)
        with lock:
            global_time -= 1

    with lock:
        closed = True


def client_thread(conn, addr):
    """Recebe comandos e lances do cliente conectado."""
    global current_bid, winner, closed

    while not closed:
        try:
            data = conn.recv(1024)
        except socket.timeout:
            continue
        except (ConnectionResetError, OSError):
            with lock:
                closed = True
            break

        if not data:
            print("Cliente desconectado.")
            with lock:
                closed = True
            break

        message = data.decode().strip()

        if message == ":item":
            conn.send(f"Item: {ITEM} | Lance atual: R${current_bid}\n".encode())
        elif message == ":tempo":
            conn.send(f"Tempo restante: {global_time} segundos\n".encode())
        elif message == ":quit":
            print("Cliente encerrou a conexao.")
            with lock:
                closed = True
            break
        elif message.isdigit():
            value = int(message)
            if value > current_bid:
                with lock:
                    current_bid = value
                    winner = addr
                conn.send("Lance aceito!\n".encode())
            else:
                conn.send(f"Lance invalido! O minimo atual e R${current_bid}\n".encode())
        else:
            conn.send("Comando invalido. Use :item, :tempo, :quit ou um valor numerico.\n".encode())


def main():
    server, conn, addr = start_server()

    t_timer = threading.Thread(target=timer_thread)
    t_client = threading.Thread(target=client_thread, args=(conn, addr))

    t_timer.start()
    t_client.start()

    t_timer.join()
    t_client.join()

    conn.close()
    server.close()


if __name__ == "__main__":
    main()
