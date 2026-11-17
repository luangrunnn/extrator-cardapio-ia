import io

import pandas as pd
import pytest

from extrator.gemini import ErroGemini, extrair_texto_resposta, interpretar_json
from extrator.planilha import converter_preco, gerar_csv, gerar_excel, padronizar, renumerar, validar


@pytest.mark.parametrize(
    "entrada, esperado",
    [
        (32.9, 32.9),
        ("32,90", 32.9),
        ("R$ 1.234,50", 1234.5),
        ("R$45", 45.0),
        ("", 0.0),
        (None, 0.0),
        ("consulte", 0.0),
        (float("nan"), 0.0),
    ],
)
def test_converter_preco(entrada, esperado):
    assert converter_preco(entrada) == esperado


def test_padronizar_gera_layout_e_codigos():
    produtos = [
        {"produto": " X-Burguer ", "grupo": "lanches", "detalhes": "Pão, carne", "preco": 25.5},
        {"produto": "Coca-Cola Lata", "grupo": "Bebidas", "preco": "6,00", "unidade": "un"},
        {"produto": "Coca-Cola Lata", "grupo": "Bebidas", "preco": "6,00"},  # duplicado
        {"produto": "", "grupo": "Bebidas", "preco": 1},  # sem nome: ignorado
        {"produto": "Feijoada", "preco": 40, "unidade": "KG"},
    ]
    df = padronizar(produtos)
    assert list(df.columns) == ["codigo", "descricao", "grupo", "detalhes", "unidade", "preco_venda"]
    assert list(df["codigo"]) == [1, 2, 3]
    assert df.loc[0, "descricao"] == "X-Burguer"
    assert df.loc[0, "grupo"] == "LANCHES"
    assert df.loc[1, "preco_venda"] == 6.0
    assert df.loc[2, "grupo"] == "SEM GRUPO"
    assert df.loc[2, "unidade"] == "KG"


def test_validar_aponta_sem_preco():
    df = padronizar([{"produto": "Pudim", "grupo": "Sobremesas", "preco": 0}])
    avisos = validar(df)
    assert any("sem preço" in a for a in avisos)


def test_renumerar_apos_edicao():
    df = padronizar([{"produto": "A", "grupo": "G", "preco": 1}, {"produto": "B", "grupo": "G", "preco": 2}])
    editado = pd.concat([df.iloc[[1]], pd.DataFrame([{"descricao": "C", "grupo": "G", "preco_venda": "3,5"}])])
    final = renumerar(editado)
    assert list(final["codigo"]) == [1, 2]
    assert final.loc[1, "preco_venda"] == 3.5


def test_exportacao_excel_e_csv():
    df = padronizar([{"produto": "Açaí 500ml", "grupo": "Açaí", "preco": 19.9}])
    lido = pd.read_excel(io.BytesIO(gerar_excel(df)))
    assert list(lido.columns) == ["codigo", "descricao", "grupo", "detalhes", "unidade", "precovenda"]
    assert lido.loc[0, "precovenda"] == 19.9
    csv = gerar_csv(df).decode("utf-8-sig")
    assert "precovenda" in csv and "19,9" in csv and ";" in csv


def test_interpretar_json_com_cerca_de_codigo():
    texto = '```json\n[{"produto": "Pizza - G", "grupo": "PIZZAS", "preco": 59.9}]\n```'
    assert interpretar_json(texto)[0]["produto"] == "Pizza - G"


def test_interpretar_json_invalido():
    with pytest.raises(ErroGemini):
        interpretar_json("não consegui ler o cardápio")


def test_extrair_texto_ignora_raciocinio():
    resposta = {"candidates": [{"content": {"parts": [{"text": "pensando...", "thought": True}, {"text": "[]"}]}}]}
    assert extrair_texto_resposta(resposta) == "[]"
