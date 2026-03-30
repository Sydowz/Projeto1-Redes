import logging
import random
import signal
import socket
import sys
import threading
import time
import atexit
from dataclasses import dataclass
from typing import Any, Dict, Optional

from usuarios import carregar_usuarios, registrar_ou_carregar, salvar_usuarios

HOST = "127.0.0.1"
PORT = 5000


logger = logging.getLogger("servidor")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("%(asctime)s | %(message)s", datefmt="%H:%M:%S")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False


def _ler_max_conexoes() -> int:
    try:
        if len(sys.argv) >= 2:
            v = int(sys.argv[1])
            return max(1, v)
    except (TypeError, ValueError):
        pass
    return 5


MAX = _ler_max_conexoes()

# Configuração do leilão
ITEM = "Carro Velho"
INITIAL_BID = 10000
ROUND_SECONDS = 60


@dataclass
class ClientSession:
    conn: socket.socket
    addr: Any
    nome: str
    dados: Dict[str, Any]


shutdown_event = threading.Event()
state_lock = threading.RLock()

clientes: Dict[socket.socket, ClientSession] = {}
usuarios_cache: Dict[str, Dict[str, Any]] = {}

# Estado do leilão (compartilhado entre clientes)
round_time_left: int = ROUND_SECONDS
round_closed: bool = False
current_bid: int = INITIAL_BID
winner_nome: Optional[str] = None
winner_session: Optional[ClientSession] = None


def safe_send(conn: socket.socket, text: str) -> bool:
    try:
        conn.sendall(text.encode())
        return True
    except OSError:
        return False


def broadcast(mensagem: str) -> None:
    with state_lock:
        conns = list(clientes.keys())
    for c in conns:
        safe_send(c, mensagem)


def _remover_cliente(conn: socket.socket) -> None:
    with state_lock:
        session = clientes.pop(conn, None)
        if session is None:
            return
        # Se ele era o vencedor humano com valor bloqueado, devolve o bloqueio
        global winner_session, winner_nome
        if winner_session is session:
            try:
                bloqueado = int(session.dados.get("bloqueado", 0))
            except (TypeError, ValueError):
                bloqueado = 0
            if bloqueado > 0:
                try:
                    session.dados["saldo"] = int(session.dados.get("saldo", 0)) + bloqueado
                except (TypeError, ValueError):
                    session.dados["saldo"] = bloqueado
                session.dados["bloqueado"] = 0
                usuarios_cache[session.nome] = session.dados
            winner_session = None
            winner_nome = None
            _persistir_usuarios_locked()

    try:
        conn.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    try:
        conn.close()
    except OSError:
        pass


def _persistir_usuarios_locked() -> None:
    # state_lock deve estar adquirido por quem chama
    salvar_usuarios(usuarios_cache)


def _carregar_usuario(nome: str) -> Dict[str, Any]:
    # Normaliza e garante presença no arquivo
    dados = registrar_ou_carregar(nome)
    with state_lock:
        usuarios_cache[nome] = dados
        _persistir_usuarios_locked()
    return dados


def start_server() -> socket.socket:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(MAX)
    server.settimeout(1.0)
    logger.info(f"Servidor aguardando conexões em {HOST}:{PORT} (MAX={MAX})...")
    return server


def aceitar_conexoes(server: socket.socket) -> None:
    while not shutdown_event.is_set():
        try:
            conn, addr = server.accept()
        except socket.timeout:
            continue
        except OSError:
            break

        try:
            logger.info(f"Conexão recebida de {addr}")
            with state_lock:
                if len(clientes) >= MAX:
                    safe_send(conn, "SERVIDOR CHEIO!\n")
                    try:
                        conn.close()
                    except OSError:
                        pass
                    continue

            safe_send(conn, "Digite seu nome: ")
            conn.settimeout(10.0)
            raw = b""
            try:
                raw = conn.recv(1024)
            except (ConnectionResetError, OSError, socket.timeout):
                try:
                    conn.close()
                except OSError:
                    pass
                continue
            if not raw:
                try:
                    conn.close()
                except OSError:
                    pass
                continue

            nome = raw.decode(errors="ignore").strip()
            if not nome:
                nome = "Anonimo"
            # Nome case-insensitive
            nome = nome.lower()
            dados = _carregar_usuario(nome)
            conn.settimeout(1.0)

            session = ClientSession(conn=conn, addr=addr, nome=nome, dados=dados)
            with state_lock:
                clientes[conn] = session
                simult = len(clientes)
            logger.info(f"CLIENTE CONECTADO: {nome} ({addr}) | simultâneos={simult}")

            t = threading.Thread(target=_client_thread_entry, args=(session,))
            t.daemon = True
            t.start()
        except Exception:
            # Nunca deixar exceção vazar e gerar traceback em thread do accept
            try:
                conn.close()
            except Exception:
                pass


def _client_thread_entry(session: ClientSession) -> None:
    try:
        client_thread(session)
    except Exception:
        # Evita traceback em qualquer cenário inesperado
        pass
    finally:
        _remover_cliente(session.conn)
        with state_lock:
            simult = len(clientes)
        logger.info(f"CLIENTE DESCONECTADO: {session.nome} | simultâneos={simult}")


def client_thread(session: ClientSession) -> None:
    global current_bid, winner_nome, winner_session
    safe_send(session.conn, f"Bem-vindo, {session.nome}! Saldo: R${session.dados.get('saldo', 0)}\n")
    safe_send(
        session.conn,
        "Comandos: :item, :tempo, :quit, :vender <item> ou um valor numérico para lance.\n",
    )

    while not shutdown_event.is_set():
        try:
            data = session.conn.recv(1024)
        except socket.timeout:
            continue
        except (ConnectionResetError, OSError):
            return

        if not data:
            return

        message = data.decode(errors="ignore").strip()
        if not message:
            continue

        if message == ":item":
            with state_lock:
                bid = current_bid
                fechado = round_closed
            if fechado:
                safe_send(session.conn, f"Leilão FECHADO. Último lance: R${bid}\n")
            else:
                safe_send(session.conn, f"Item: {ITEM} | Lance atual: R${bid}\n")
            continue

        if message == ":tempo":
            with state_lock:
                t = round_time_left
                fechado = round_closed
            if fechado:
                safe_send(session.conn, "Leilão FECHADO. Aguarde a próxima rodada.\n")
            else:
                safe_send(session.conn, f"Tempo restante: {t} segundos\n")
            continue

        if message == ":quit":
            safe_send(session.conn, "Conexão encerrada.\n")
            return

        if message.startswith(":vender "):
            item_venda = message[8:].strip()
            if not item_venda:
                safe_send(session.conn, "Uso: :vender <nome_do_item>\n")
                continue
            item_encontrado = None
            itens = session.dados.get("itens", [])
            if isinstance(itens, list):
                for i in itens:
                    try:
                        if i.get("nome") == item_venda:
                            item_encontrado = i
                            break
                    except AttributeError:
                        continue

            if not item_encontrado:
                safe_send(session.conn, "Você não possui esse item!\n")
                continue

            try:
                valor_item = int(item_encontrado.get("valor", 0))
            except (TypeError, ValueError):
                valor_item = 0
            valor_venda = int(valor_item * 0.9)
            if valor_venda < 0:
                valor_venda = 0

            try:
                session.dados["saldo"] = int(session.dados.get("saldo", 0)) + valor_venda
            except (TypeError, ValueError):
                session.dados["saldo"] = valor_venda

            try:
                session.dados.get("itens", []).remove(item_encontrado)
            except (ValueError, AttributeError):
                pass

            with state_lock:
                usuarios_cache[session.nome] = session.dados
                _persistir_usuarios_locked()

            safe_send(session.conn, f"Vendido! Você recebeu R${valor_venda}. Saldo: R${session.dados.get('saldo', 0)}\n")
            continue

        if message.isdigit():
            value = int(message)
            if value <= 0:
                safe_send(session.conn, "Lance inválido.\n")
                continue

            with state_lock:
                if round_closed:
                    safe_send(session.conn, "Leilão FECHADO. Aguarde a próxima rodada.\n")
                    continue
                if value <= current_bid:
                    safe_send(session.conn, f"Lance inválido! O mínimo atual é R${current_bid}\n")
                    continue

                try:
                    saldo = int(session.dados.get("saldo", 0))
                except (TypeError, ValueError):
                    saldo = 0

                if saldo < value:
                    safe_send(session.conn, f"Saldo insuficiente! Seu saldo é R${saldo}\n")
                    continue

                # Devolve bloqueio anterior (se vencedor humano)
                if winner_session is not None:
                    try:
                        prev_block = int(winner_session.dados.get("bloqueado", 0))
                    except (TypeError, ValueError):
                        prev_block = 0
                    if prev_block > 0:
                        try:
                            winner_session.dados["saldo"] = int(winner_session.dados.get("saldo", 0)) + prev_block
                        except (TypeError, ValueError):
                            winner_session.dados["saldo"] = prev_block
                        winner_session.dados["bloqueado"] = 0
                        usuarios_cache[winner_session.nome] = winner_session.dados

                # Aplica novo bloqueio
                session.dados["saldo"] = saldo - value
                session.dados["bloqueado"] = value
                usuarios_cache[session.nome] = session.dados

                current_bid = value
                winner_nome = session.nome
                winner_session = session
                _persistir_usuarios_locked()

            broadcast(f"{session.nome} deu um lance de R${value}!\n")
            continue

        safe_send(session.conn, "Comando inválido. Use :item, :tempo, :quit, :vender ou um valor numérico.\n")


def bot_thread() -> None:
    global current_bid, winner_nome, winner_session
    bot_names = ["Bot_Ana", "Bot_Carlos", "Bot_Pedro", "Bot_Foster"]
    while not shutdown_event.is_set():
        time.sleep(random.randint(5, 15))
        if shutdown_event.is_set():
            break
        with state_lock:
            if round_closed:
                continue
            base = current_bid
        simulated_bid = base + random.randint(-500, 1500)
        if simulated_bid <= base:
            continue
        bot_name = random.choice(bot_names)
        with state_lock:
            if round_closed:
                continue
            # Devolve bloqueio humano anterior, se houver
            if winner_session is not None:
                try:
                    prev_block = int(winner_session.dados.get("bloqueado", 0))
                except (TypeError, ValueError):
                    prev_block = 0
                if prev_block > 0:
                    try:
                        winner_session.dados["saldo"] = int(winner_session.dados.get("saldo", 0)) + prev_block
                    except (TypeError, ValueError):
                        winner_session.dados["saldo"] = prev_block
                    winner_session.dados["bloqueado"] = 0
                    usuarios_cache[winner_session.nome] = winner_session.dados
                    _persistir_usuarios_locked()
            current_bid = simulated_bid
            winner_nome = bot_name
            winner_session = None
        broadcast(f"{bot_name} deu um lance de R${simulated_bid}!\n")


def _finalizar_rodada() -> None:
    with state_lock:
        global round_closed
        round_closed = True

        vencedor = winner_nome
        bid = current_bid
        sess = winner_session

        if vencedor and sess is not None:
            # Entrega item, libera bloqueio e persiste
            try:
                sess.dados.setdefault("itens", []).append({"nome": ITEM, "valor": bid})
            except Exception:
                sess.dados["itens"] = [{"nome": ITEM, "valor": bid}]
            sess.dados["bloqueado"] = 0
            usuarios_cache[sess.nome] = sess.dados
            _persistir_usuarios_locked()
        elif sess is None:
            # Se bot ganhou, garante que não há bloqueio humano pendente
            pass

    broadcast(f"Leilão encerrado! Vencedor: {vencedor} com R${bid}!\n")
    logger.info(f"Leilão encerrado! Vencedor: {vencedor} com R${bid}")


def _resetar_rodada() -> None:
    with state_lock:
        global round_time_left, round_closed, current_bid, winner_nome, winner_session
        round_time_left = ROUND_SECONDS
        round_closed = False
        current_bid = INITIAL_BID
        winner_nome = None
        winner_session = None


def _shutdown(server: Optional[socket.socket]) -> None:
    shutdown_event.set()
    # Avisa clientes antes de fechar as conexões (útil para apresentação/debug)
    try:
        broadcast("Servidor encerrando... conexão será finalizada.\n")
    except Exception:
        pass
    if server is not None:
        try:
            server.close()
        except OSError:
            pass

    # Fecha clientes (e persiste estado)
    with state_lock:
        conns = list(clientes.keys())
    for c in conns:
        _remover_cliente(c)

    with state_lock:
        _persistir_usuarios_locked()


def main() -> None:
    global usuarios_cache, round_time_left, round_closed
    usuarios_cache = carregar_usuarios()

    server = start_server()

    def _handle_shutdown_signal(_sig, _frame) -> None:
        _shutdown(server)

    try:
        signal.signal(signal.SIGINT, _handle_shutdown_signal)
    except Exception:
        pass
    try:
        signal.signal(signal.SIGTERM, _handle_shutdown_signal)
    except Exception:
        pass
    try:
        signal.signal(signal.SIGBREAK, _handle_shutdown_signal)  # Windows: Ctrl+Break
    except Exception:
        pass

    # Garante persistência/fechamento mesmo se main terminar por outro motivo
    atexit.register(lambda: _shutdown(server))

    t_accept = threading.Thread(target=aceitar_conexoes, args=(server,))
    t_accept.daemon = True
    t_accept.start()

    t_bot = threading.Thread(target=bot_thread)
    t_bot.daemon = True
    t_bot.start()

    # Loop contínuo de rodadas do leilão até shutdown
    _resetar_rodada()
    while not shutdown_event.is_set():
        with state_lock:
            if not round_closed and round_time_left > 0:
                pass
            else:
                # Rodada terminou; finaliza e cria próxima
                _finalizar_rodada()
                if shutdown_event.is_set():
                    break
                time.sleep(2)
                _resetar_rodada()
                broadcast(f"Nova rodada iniciada! Item: {ITEM} | Lance inicial: R${INITIAL_BID}\n")

        # Tick 1s
        time.sleep(1)
        with state_lock:
            if not round_closed and round_time_left > 0:
                round_time_left -= 1
                if round_time_left <= 0:
                    round_time_left = 0
                    round_closed = True

    _shutdown(server)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        # Evita traceback caso o signal handler não tenha sido instalado
        pass
