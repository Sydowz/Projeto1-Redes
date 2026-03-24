import socket
import threading
import time
import random
import sys
from datetime import datetime
from usuarios import registrar_ou_carregar, carregar_usuarios, salvar_usuarios

HOST = "127.0.0.1"
PORT = 5000
MAX = int(sys.argv[1])

# Configuracao inicial do leilao
ITEM = "Carro Velho"
INITIAL_BID = 10000

# Estado compartilhado do leilao
global_time = 60
closed = False
current_bid = INITIAL_BID
winner = None
clientes = []
winner_dados = None

# Controle de concorrencia
lock = threading.Lock()


def safe_send(conn, text):
    """Envia mensagem para o cliente com tratamento de erro de socket."""
    try:
        conn.send(text.encode())
        return True
    except OSError:
        return False


def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(MAX)
    print("Servidor aguardando conexoes...")
    return server


def aceitar_conexoes(server):
    while not closed:
        try:
            conn, addr = server.accept()
        except OSError:
            break
        if len(clientes) >= MAX:
            conn.send("SERVIDOR CHEIO!\n".encode())
            conn.close()
        else:
            print("CLIENTE NOVO CONECTADO")
            clientes.append(conn)
            conn.send("Digite seu nome: ".encode())
            nome = conn.recv(1024).decode().strip()
            dados = registrar_ou_carregar(nome)
            t = threading.Thread(target=client_thread, args=(conn, addr, nome, dados))
            t.start()


def timer_thread():
    """Executa a contagem regressiva do leilao."""
    global global_time, closed
    while global_time > 0 and not closed:
        time.sleep(1)
        with lock:
            global_time -= 1
    with lock:
        closed = True


def client_thread(conn, addr, nome, dados):
    """Recebe comandos e lances do cliente conectado."""
    global current_bid, winner, winner_dados, closed
    safe_send(conn, f"Bem vindo, {nome}! Saldo: R${dados['saldo']}\n")
    while not closed:
        try:
            data = conn.recv(1024)
        except socket.timeout:
            continue
        except (ConnectionResetError, OSError):
            with lock:
                clientes.remove(conn)
            break

        if not data:
            print(f"{nome} desconectado.")
            with lock:
                clientes.remove(conn)
                conn.close()
            break

        message = data.decode(errors="ignore").strip()

        if message == ":item":
            if not safe_send(conn, f"Item: {ITEM} | Lance atual: R${current_bid}\n"):
                break
        elif message == ":tempo":
            if not safe_send(conn, f"Tempo restante: {global_time} segundos\n"):
                break
        elif message == ":quit":
            print(f"{nome} encerrou a conexao.")
            with lock:
                clientes.remove(conn)
                conn.close()
            break
        elif message.isdigit():
            value = int(message)
            if value > current_bid:
                if dados['saldo'] >= value:
                    with lock:
                        if winner_dados is not None:
                            winner_dados['saldo'] += winner_dados['bloqueado']
                            winner_dados['bloqueado'] = 0
                        dados['saldo'] -= value
                        dados['bloqueado'] = value
                        current_bid = value
                        winner = nome
                        winner_dados = dados
                    broadcast(f"{nome} deu um lance de R${value}!\n")
                else:
                    if not safe_send(conn, f"Saldo insuficiente! Seu saldo e R${dados['saldo']}\n"):
                        break
            else:
                if not safe_send(conn, f"Lance invalido! O minimo atual e R${current_bid}\n"):
                    break
        elif message.startswith(":vender "):
            item_venda = message[8:]
            item_encontrado = None
            for i in dados['itens']:
                if i['nome'] == item_venda:
                    item_encontrado = i
                    break
            if item_encontrado:
                valor_venda = int(item_encontrado['valor'] * 0.9)
                dados['saldo'] += valor_venda
                dados['itens'].remove(item_encontrado)
                usuarios = carregar_usuarios()
                usuarios[nome] = dados
                salvar_usuarios(usuarios)
                safe_send(conn, f"Vendido! Voce recebeu R${valor_venda}. Saldo: R${dados['saldo']}\n")
            else:
                safe_send(conn, "Voce nao possui esse item!\n")
        else:
            if not safe_send(conn, "Comando invalido. Use :item, :tempo, :quit, :vender ou um valor numerico.\n"):
                break


def bot_thread():
    """Simula outros usuarios enviando lances aleatorios."""
    global current_bid, winner, winner_dados, closed
    bot_names = ["Bot_Ana", "Bot_Carlos", "Bot_Pedro", "Bot_Foster"]

    while not closed:
        time.sleep(random.randint(5, 15))
        if closed:
            break
        simulated_bid = current_bid + random.randint(-500, 1500)
        if simulated_bid > current_bid:
            bot_name = random.choice(bot_names)
            with lock:
                if winner_dados is not None:
                    winner_dados['saldo'] += winner_dados['bloqueado']
                    winner_dados['bloqueado'] = 0
                current_bid = simulated_bid
                winner = bot_name
                winner_dados = None
            broadcast(f"{bot_name} deu um lance de R${simulated_bid}!\n")


def broadcast(mensagem):
    with lock:
        lista = list(clientes)
    for cliente in lista:
        safe_send(cliente, mensagem)


def main():
    server = start_server()
    t_accept = threading.Thread(target=aceitar_conexoes, args=(server,))
    t_accept.daemon = True
    t_timer = threading.Thread(target=timer_thread)
    t_bot = threading.Thread(target=bot_thread)
    t_bot.daemon = True
    t_accept.start()
    t_timer.start()
    t_bot.start()
    t_timer.join()
    broadcast(f"Leilao encerrado! Vencedor: {winner} com R${current_bid}!\nPressione Enter para sair.\n")
    if winner and winner_dados is not None:
        winner_dados['itens'].append({"nome": ITEM, "valor": current_bid})
        winner_dados['bloqueado'] = 0
        usuarios = carregar_usuarios()
        usuarios[winner] = winner_dados
        salvar_usuarios(usuarios)
    print(f"Leilao encerrado! Vencedor: {winner} com R${current_bid}")
    server.close()


if __name__ == "__main__":
    main()
