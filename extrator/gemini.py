"""Leitura do cardápio com a API do Google Gemini."""

import base64
import json
import re
import time

import requests

from extrator.config import (
    ESPERA_ENTRE_TENTATIVAS,
    MODELOS_GEMINI,
    TENTATIVAS,
    TIMEOUT_SEGUNDOS,
    URL_API,
)

PROMPT = """Você é um assistente de implantação de sistemas para restaurantes.
Leia o cardápio enviado e extraia TODOS os produtos vendidos.

Regras:
- "produto": nome do item como aparece no cardápio, sem o preço.
- "grupo": a seção/categoria do cardápio em que o item aparece (ex.: Lanches, Pizzas, Bebidas). Em MAIÚSCULAS.
- "detalhes": descrição ou ingredientes do item, se houver. Vazio se não houver.
- "preco": preço de venda como número decimal (ex.: 32.9). Use 0 se o preço não estiver visível.
- "unidade": "UN" por padrão; use "KG" apenas para itens vendidos por quilo.
- Se um item tiver vários tamanhos ou preços (ex.: Pizza P, M e G), crie um produto para cada um,
  com o tamanho no final do nome (ex.: "Pizza Calabresa - G").
- Ignore textos que não são produtos (endereço, telefone, horários, avisos, taxa de entrega).
- Não invente produtos nem preços.
"""

SCHEMA_RESPOSTA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "produto": {"type": "STRING"},
            "grupo": {"type": "STRING"},
            "detalhes": {"type": "STRING"},
            "preco": {"type": "NUMBER"},
            "unidade": {"type": "STRING"},
        },
        "required": ["produto", "grupo", "preco"],
    },
}


class ErroGemini(Exception):
    """Falha ao obter uma resposta válida da IA."""


def _montar_corpo(arquivo_bytes: bytes, mime_type: str, com_schema: bool) -> dict:
    config = {"temperature": 0.1, "responseMimeType": "application/json"}
    if com_schema:
        config["responseSchema"] = SCHEMA_RESPOSTA
    return {
        "contents": [
            {
                "parts": [
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": base64.b64encode(arquivo_bytes).decode("ascii"),
                        }
                    },
                    {"text": PROMPT},
                ]
            }
        ],
        "generationConfig": config,
    }


def extrair_texto_resposta(resposta_json: dict) -> str:
    """Junta as partes de texto da resposta, ignorando partes de raciocínio do modelo."""
    try:
        partes = resposta_json["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError, TypeError):
        motivo = (resposta_json.get("promptFeedback") or {}).get("blockReason", "resposta sem conteúdo")
        raise ErroGemini(f"A IA não devolveu conteúdo ({motivo}).")
    return "".join(p.get("text", "") for p in partes if not p.get("thought")).strip()


def interpretar_json(texto: str) -> list[dict]:
    """Converte o texto da IA em lista de produtos, tolerando cercas de código."""
    texto = texto.strip()
    texto = re.sub(r"^```(?:json)?\s*|\s*```$", "", texto, flags=re.IGNORECASE).strip()
    try:
        dados = json.loads(texto)
    except json.JSONDecodeError:
        inicio, fim = texto.find("["), texto.rfind("]")
        if inicio == -1 or fim <= inicio:
            raise ErroGemini("A IA não devolveu uma lista de produtos em JSON.")
        dados = json.loads(texto[inicio : fim + 1])

    if isinstance(dados, dict):
        dados = dados.get("produtos") or dados.get("items") or []
    if not isinstance(dados, list):
        raise ErroGemini("Formato de resposta inesperado.")
    return [d for d in dados if isinstance(d, dict)]


def extrair_cardapio(
    arquivo_bytes: bytes,
    mime_type: str,
    chave_api: str,
    ao_mudar_status=None,
    sessao=None,
) -> tuple[list[dict], str]:
    """
    Envia o cardápio ao Gemini e devolve (produtos, modelo_usado).

    Tenta cada modelo da lista. Modelo inexistente (404), limite de uso (429),
    sobrecarga (5xx) ou demora excessiva fazem o código passar para o próximo.
    """
    if not chave_api:
        raise ErroGemini("Informe a chave da API do Gemini.")

    http = sessao or requests.Session()
    avisar = ao_mudar_status or (lambda msg: None)
    erros = []
    com_schema = True

    for tentativa in range(1, TENTATIVAS + 1):
        for modelo in MODELOS_GEMINI:
            avisar(f"Lendo o cardápio com {modelo} (tentativa {tentativa})...")
            try:
                resp = http.post(
                    URL_API.format(modelo=modelo),
                    headers={"x-goog-api-key": chave_api, "Content-Type": "application/json"},
                    json=_montar_corpo(arquivo_bytes, mime_type, com_schema),
                    timeout=TIMEOUT_SEGUNDOS,
                )
            except requests.RequestException as e:
                erros.append(f"{modelo}: sem resposta ({type(e).__name__})")
                continue

            if resp.status_code in (401, 403):
                raise ErroGemini("Chave da API inválida ou sem permissão.")
            if resp.status_code == 400 and com_schema and "schema" in resp.text.lower():
                # Modelo não aceitou o formato estruturado: tenta de novo só com o prompt
                com_schema = False
                erros.append(f"{modelo}: schema recusado, tentando sem schema")
                continue
            if resp.status_code == 404 or resp.status_code == 429 or resp.status_code >= 500:
                erros.append(f"{modelo}: HTTP {resp.status_code}")
                continue
            if resp.status_code != 200:
                raise ErroGemini(f"Gemini respondeu HTTP {resp.status_code}: {resp.text[:300]}")

            try:
                produtos = interpretar_json(extrair_texto_resposta(resp.json()))
            except (ErroGemini, ValueError) as e:
                erros.append(f"{modelo}: {e}")
                continue
            return produtos, modelo

        if tentativa < TENTATIVAS:
            avisar(f"Modelos ocupados. Nova tentativa em {ESPERA_ENTRE_TENTATIVAS} segundos...")
            time.sleep(ESPERA_ENTRE_TENTATIVAS)

    raise ErroGemini("Não foi possível ler o cardápio agora. Detalhes: " + " | ".join(erros))
