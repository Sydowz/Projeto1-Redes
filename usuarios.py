import json
import os
from typing import Any, Dict

ARQUIVO = "usuarios.json"


def _normalizar_nome(nome: Any) -> str:
    nome = ("" if nome is None else str(nome)).strip()
    if not nome:
        nome = "Anonimo"
    return nome.lower()


def _normalizar_usuario(dados: Any) -> Dict[str, Any]:
    if not isinstance(dados, dict):
        return {"saldo": 50000, "bloqueado": 0, "itens": []}
    saldo = dados.get("saldo", 50000)
    bloqueado = dados.get("bloqueado", 0)
    itens = dados.get("itens", [])
    if not isinstance(itens, list):
        itens = []
    try:
        saldo = int(saldo)
    except (TypeError, ValueError):
        saldo = 50000
    try:
        bloqueado = int(bloqueado)
    except (TypeError, ValueError):
        bloqueado = 0
    if saldo < 0:
        saldo = 0
    if bloqueado < 0:
        bloqueado = 0
    return {"saldo": saldo, "bloqueado": bloqueado, "itens": itens}


def carregar_usuarios() -> Dict[str, Dict[str, Any]]:
    try:
        with open(ARQUIVO, "r", encoding="utf-8") as f:
            dados = json.load(f)
        if not isinstance(dados, dict):
            return {}
        normalizado: Dict[str, Dict[str, Any]] = {}
        for k, v in dados.items():
            nk = _normalizar_nome(k)
            if nk not in normalizado:
                normalizado[nk] = _normalizar_usuario(v)
        return normalizado
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError):
        # Se o arquivo existir mas estiver corrompido/inacessível,
        # o servidor continua rodando (e salvará um novo estado no shutdown).
        return {}


def salvar_usuarios(usuarios: Dict[str, Dict[str, Any]]) -> bool:
    tmp = f"{ARQUIVO}.tmp"
    try:
        payload = {_normalizar_nome(k): _normalizar_usuario(v) for k, v in usuarios.items()}
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, ARQUIVO)  # atômico no Windows quando mesmo volume
        return True
    except OSError:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass
        return False


def registrar_ou_carregar(nome: str) -> Dict[str, Any]:
    nome = _normalizar_nome(nome)
    usuarios = carregar_usuarios()
    if nome not in usuarios:
        usuarios[nome] = {"saldo": 50000, "bloqueado": 0, "itens": []}
        salvar_usuarios(usuarios)
    return _normalizar_usuario(usuarios.get(nome))
