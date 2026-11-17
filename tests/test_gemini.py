"""Testa a troca automática de modelo sem chamar a API de verdade."""

import json

import pytest
import requests

import extrator.gemini as gemini


class RespostaFalsa:
    def __init__(self, status, corpo):
        self.status_code = status
        self._corpo = corpo
        self.text = json.dumps(corpo)

    def json(self):
        return self._corpo


class SessaoFalsa:
    """Simula a API: cada chamada devolve o próximo item da fila."""

    def __init__(self, fila):
        self.fila = list(fila)
        self.urls = []

    def post(self, url, **kwargs):
        self.urls.append(url)
        item = self.fila.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def ok(produtos):
    texto = json.dumps(produtos)
    return RespostaFalsa(200, {"candidates": [{"content": {"parts": [{"text": texto}]}}]})


@pytest.fixture(autouse=True)
def sem_espera(monkeypatch):
    monkeypatch.setattr(gemini.time, "sleep", lambda s: None)


def test_pula_modelo_sobrecarregado_e_com_timeout():
    sessao = SessaoFalsa([
        RespostaFalsa(503, {"error": {"status": "UNAVAILABLE"}}),
        requests.Timeout(),
        ok([{"produto": "X-Salada", "grupo": "LANCHES", "preco": 22}]),
    ])
    produtos, modelo = gemini.extrair_cardapio(b"%PDF", "application/pdf", "chave", sessao=sessao)
    assert produtos[0]["produto"] == "X-Salada"
    assert modelo == gemini.MODELOS_GEMINI[2]
    assert len(sessao.urls) == 3


def test_nova_rodada_quando_todos_falham():
    n = len(gemini.MODELOS_GEMINI)
    sessao = SessaoFalsa([RespostaFalsa(429, {})] * n + [ok([])])
    produtos, modelo = gemini.extrair_cardapio(b"x", "image/png", "chave", sessao=sessao)
    assert produtos == [] and modelo == gemini.MODELOS_GEMINI[0]


def test_chave_invalida_para_na_hora():
    sessao = SessaoFalsa([RespostaFalsa(403, {})])
    with pytest.raises(gemini.ErroGemini, match="Chave"):
        gemini.extrair_cardapio(b"x", "image/png", "errada", sessao=sessao)


def test_desiste_com_mensagem_clara():
    n = len(gemini.MODELOS_GEMINI) * gemini.TENTATIVAS
    sessao = SessaoFalsa([RespostaFalsa(503, {})] * n)
    with pytest.raises(gemini.ErroGemini, match="Não foi possível"):
        gemini.extrair_cardapio(b"x", "image/png", "chave", sessao=sessao)


def test_schema_recusado_tenta_sem_schema():
    sessao = SessaoFalsa([
        RespostaFalsa(400, {"error": {"message": "Invalid responseSchema"}}),
        ok([{"produto": "Suco", "grupo": "BEBIDAS", "preco": 8}]),
    ])
    produtos, _ = gemini.extrair_cardapio(b"x", "image/png", "chave", sessao=sessao)
    assert produtos[0]["produto"] == "Suco"
