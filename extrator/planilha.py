"""Padronização, validação e exportação dos produtos extraídos."""

import io
import re

import pandas as pd

from extrator.config import GRUPO_PADRAO, LAYOUT_IMPORTACAO, UNIDADE_PADRAO

COLUNAS = list(LAYOUT_IMPORTACAO.keys())


def converter_preco(valor) -> float:
    """Aceita 32.9, '32,90', 'R$ 1.234,50' etc. Retorna 0.0 se não der para converter."""
    if valor is None:
        return 0.0
    if isinstance(valor, (int, float)):
        return round(float(valor), 2) if valor == valor else 0.0  # trata NaN
    texto = re.sub(r"[^\d,.\-]", "", str(valor))
    if not texto:
        return 0.0
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif "," in texto:
        texto = texto.replace(",", ".")
    try:
        return round(float(texto), 2)
    except ValueError:
        return 0.0


def _limpar(texto) -> str:
    if texto is None or (isinstance(texto, float) and texto != texto):
        return ""
    return re.sub(r"\s+", " ", str(texto)).strip()


def padronizar(produtos: list[dict]) -> pd.DataFrame:
    """Transforma a lista da IA na tabela do layout de importação."""
    linhas = []
    vistos = set()
    for p in produtos:
        descricao = _limpar(p.get("produto") or p.get("descricao"))
        if not descricao:
            continue
        grupo = _limpar(p.get("grupo")).upper() or GRUPO_PADRAO
        chave = (descricao.lower(), grupo)
        if chave in vistos:  # remove duplicados exatos
            continue
        vistos.add(chave)
        unidade = _limpar(p.get("unidade")).upper() or UNIDADE_PADRAO
        linhas.append(
            {
                "descricao": descricao,
                "grupo": grupo,
                "detalhes": _limpar(p.get("detalhes")),
                "unidade": unidade if unidade in ("UN", "KG", "LT", "PC") else UNIDADE_PADRAO,
                "preco_venda": converter_preco(p.get("preco")),
            }
        )

    df = pd.DataFrame(linhas, columns=[c for c in COLUNAS if c != "codigo"])
    df.insert(0, "codigo", range(1, len(df) + 1))
    return df[COLUNAS]


def validar(df: pd.DataFrame) -> list[str]:
    """Aponta problemas que precisam de revisão antes da importação."""
    avisos = []
    if df.empty:
        return ["Nenhum produto encontrado no cardápio."]
    sem_preco = df[df["preco_venda"].fillna(0) <= 0]
    for _, linha in sem_preco.iterrows():
        avisos.append(f"Código {linha['codigo']} — '{linha['descricao']}' está sem preço.")
    repetidos = df[df["descricao"].str.lower().duplicated(keep=False)]
    for nome in sorted(set(repetidos["descricao"])):
        avisos.append(f"'{nome}' aparece mais de uma vez (confira se são grupos diferentes).")
    return avisos


def renumerar(df: pd.DataFrame) -> pd.DataFrame:
    """Refaz a coluna de código após edição manual (linhas incluídas ou removidas)."""
    df = df.dropna(subset=["descricao"]).copy()
    df = df[df["descricao"].astype(str).str.strip() != ""]
    df["preco_venda"] = df["preco_venda"].apply(converter_preco)
    df["codigo"] = range(1, len(df) + 1)
    return df[COLUNAS].reset_index(drop=True)


def _para_layout(df: pd.DataFrame) -> pd.DataFrame:
    return df[COLUNAS].rename(columns=LAYOUT_IMPORTACAO)


def gerar_excel(df: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        _para_layout(df).to_excel(writer, index=False, sheet_name="Produtos")
        planilha = writer.sheets["Produtos"]
        col_preco = COLUNAS.index("preco_venda") + 1
        for (celula,) in planilha.iter_rows(min_row=2, min_col=col_preco, max_col=col_preco):
            celula.number_format = "#,##0.00"
        for coluna in planilha.columns:
            largura = max(len(str(c.value or "")) for c in coluna) + 2
            planilha.column_dimensions[coluna[0].column_letter].width = min(largura, 60)
    return buffer.getvalue()


def gerar_csv(df: pd.DataFrame) -> bytes:
    """CSV no padrão brasileiro: separador ';' e vírgula decimal."""
    return _para_layout(df).to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
