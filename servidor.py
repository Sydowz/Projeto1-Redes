import socket
import threading
import time
import random

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


def safe_send(conn, text):
    """Envia mensagem para o cliente com tratamento de erro de socket."""
    global closed
    try:
        conn.send(text.encode())
        return True
    except OSError:
        with lock:
            closed = True
        return False


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
    if not safe_send(conn, f"{current_time}: CONECTADO!!\n"):
        return server, conn, addr
    if not safe_send(conn, f"Item: {ITEM} | Lance inicial: R${INITIAL_BID}\n"):
        return server, conn, addr
    safe_send(conn, f"Lance atual: R${current_bid}\n")

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

        message = data.decode(errors="ignore").strip()

        if message == ":item":
            if not safe_send(conn, f"Item: {ITEM} | Lance atual: R${current_bid}\n"):
                break
        elif message == ":tempo":
            if not safe_send(conn, f"Tempo restante: {global_time} segundos\n"):
                break
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
                if not safe_send(conn, "Lance aceito!\n"):
                    break
            else:
                if not safe_send(conn, f"Lance invalido! O minimo atual e R${current_bid}\n"):
                    break
        else:
            if not safe_send(conn, "Comando invalido. Use :item, :tempo, :quit ou um valor numerico.\n"):
                break


def bot_thread(conn):
    """Simula outros usuarios enviando lances aleatorios."""
    global current_bid, winner, closed
    bot_names = ["Bot_Ana", "Bot_Carlos", "Bot_Pedro", "Bot_Foster"]

    while not closed:
        time.sleep(random.randint(5, 15))
        if closed:
            break

        simulated_bid = current_bid + random.randint(-500, 1500)
        if simulated_bid > current_bid:
            bot_name = random.choice(bot_names)
            with lock:
                current_bid = simulated_bid
                winner = bot_name
            if not safe_send(conn, f"{bot_name} deu um lance de R${simulated_bid}!\n"):
                break


def main():
    server = None
    conn = None

    try:
        server, conn, addr = start_server()

        t_timer = threading.Thread(target=timer_thread)
        t_client = threading.Thread(target=client_thread, args=(conn, addr))
        t_bot = threading.Thread(target=bot_thread, args=(conn,))

        t_timer.start()
        t_client.start()
        t_bot.start()

        t_timer.join()
        t_client.join()
        t_bot.join()

        final_winner = winner if winner is not None else "Sem vencedor"
        final_message = f"Item Vendido! Vencedor: {final_winner} com R${current_bid}\n"
        safe_send(conn, final_message)
        print(final_message.strip())
    finally:
        if conn is not None:
            try:
                conn.close()
            except OSError:
                pass
        if server is not None:
            try:
                server.close()
            except OSError:
                pass


if __name__ == "__main__":
    main()
