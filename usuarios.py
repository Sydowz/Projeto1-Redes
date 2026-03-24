import json

ARQUIVO = "usuarios.json"


def carregar_usuarios():
    try:
        with open(ARQUIVO, "r") as f:
            dados = json.load(f)
        return dados
    except FileNotFoundError:
        return {}


def salvar_usuarios(usuarios):
    with open(ARQUIVO, "w") as f:
        json.dump(usuarios, f)


def registrar_ou_carregar(nome):
    usuarios = carregar_usuarios()
    if nome not in usuarios:
        usuarios[nome] = {
            "saldo": 50000,
            "bloqueado": 0,
            "itens": []
        }
    salvar_usuarios(usuarios)
    return usuarios[nome]
