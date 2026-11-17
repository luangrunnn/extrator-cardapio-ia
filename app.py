import os
from pathlib import Path

import streamlit as st

from extrator.config import TAMANHO_MAXIMO_MB, TIPOS_ACEITOS
from extrator.gemini import ErroGemini, extrair_cardapio
from extrator.planilha import gerar_csv, gerar_excel, padronizar, renumerar, validar

PASTA = Path(__file__).parent
EXEMPLO = PASTA / "exemplos" / "cardapio_exemplo.pdf"

st.set_page_config(page_title="Extrator de Cardápio com IA", page_icon="🍽️", layout="wide")


# ──────────────────────────────────────────
# Chave da API: secrets do Streamlit, variável de ambiente ou digitada na tela
# ──────────────────────────────────────────

def chave_configurada() -> str:
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return str(st.secrets["GEMINI_API_KEY"]).strip()
    except Exception:
        pass
    return os.environ.get("GEMINI_API_KEY", "").strip()


with st.sidebar:
    st.header("⚙️ Configuração")
    chave_ambiente = chave_configurada()
    if chave_ambiente:
        st.success("Chave do Gemini carregada do ambiente.")
        chave_api = chave_ambiente
    else:
        chave_api = st.text_input(
            "Chave da API do Gemini",
            type="password",
            help="Crie gratuitamente em aistudio.google.com/apikey. A chave não é salva.",
        )
    st.divider()
    st.markdown(
        "**Como funciona**\n\n"
        "1. Envie o cardápio em PDF ou foto.\n"
        "2. A IA identifica produtos, grupos e preços.\n"
        "3. Revise e corrija na tabela.\n"
        "4. Baixe a planilha no layout de importação."
    )


# ──────────────────────────────────────────
# Cabeçalho e envio do arquivo
# ──────────────────────────────────────────

st.title("🍽️ Extrator de Cardápio com IA")
st.caption(
    "Transforma o cardápio do restaurante em planilha de importação de produtos, "
    "eliminando o cadastro manual na implantação do sistema."
)

col_envio, col_exemplo = st.columns([3, 1])
with col_envio:
    arquivo = st.file_uploader(
        "Cardápio (PDF ou imagem)", type=list(TIPOS_ACEITOS.keys()), key="arquivo"
    )
with col_exemplo:
    st.write("")
    usar_exemplo = st.button(
        "📄 Usar cardápio de exemplo", use_container_width=True, disabled=not EXEMPLO.exists()
    )

if usar_exemplo:
    st.session_state["origem"] = ("cardapio_exemplo.pdf", EXEMPLO.read_bytes(), "application/pdf")
elif arquivo is not None:
    extensao = arquivo.name.rsplit(".", 1)[-1].lower()
    st.session_state["origem"] = (arquivo.name, arquivo.getvalue(), TIPOS_ACEITOS[extensao])

origem = st.session_state.get("origem")
if origem:
    nome, conteudo, mime = origem
    tamanho_mb = len(conteudo) / 1_048_576
    st.info(f"Arquivo selecionado: **{nome}** ({tamanho_mb:.1f} MB)")
    if tamanho_mb > TAMANHO_MAXIMO_MB:
        st.error(f"O arquivo passa de {TAMANHO_MAXIMO_MB} MB. Divida o PDF ou envie uma foto menor.")
        origem = None

extrair = st.button(
    "✨ Extrair produtos com IA",
    type="primary",
    disabled=not (origem and chave_api),
)
if origem and not chave_api:
    st.warning("Informe a chave da API do Gemini na barra lateral para continuar.")


# ──────────────────────────────────────────
# Extração
# ──────────────────────────────────────────

if extrair and origem:
    nome, conteudo, mime = origem
    with st.status("Enviando o cardápio para a IA...", expanded=True) as status:
        try:
            produtos, modelo = extrair_cardapio(
                conteudo, mime, chave_api, ao_mudar_status=lambda msg: status.update(label=msg)
            )
            df = padronizar(produtos)
            st.session_state["produtos"] = df
            st.session_state["modelo"] = modelo
            st.session_state["nome_base"] = Path(nome).stem
            st.session_state["versao_tabela"] = st.session_state.get("versao_tabela", 0) + 1
            status.update(label=f"{len(df)} produtos extraídos com {modelo}.", state="complete", expanded=False)
        except ErroGemini as e:
            status.update(label="Não foi possível extrair o cardápio.", state="error")
            st.error(str(e))


# ──────────────────────────────────────────
# Revisão e exportação
# ──────────────────────────────────────────

if "produtos" in st.session_state:
    df = st.session_state["produtos"]
    st.divider()
    st.subheader("📝 Revise os produtos antes de exportar")
    st.caption(
        f"Lido com **{st.session_state['modelo']}**. Você pode corrigir qualquer célula, "
        "incluir linhas no final ou apagar linhas selecionadas."
    )

    editado = st.data_editor(
        df,
        key=f"tabela_{st.session_state.get('versao_tabela', 0)}",
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config={
            "codigo": st.column_config.NumberColumn("Código", disabled=True, width="small"),
            "descricao": st.column_config.TextColumn("Descrição", required=True, width="medium"),
            "grupo": st.column_config.TextColumn("Grupo"),
            "detalhes": st.column_config.TextColumn("Detalhes", width="medium"),
            "unidade": st.column_config.SelectboxColumn("Unidade", options=["UN", "KG", "LT", "PC"], width="small"),
            "preco_venda": st.column_config.NumberColumn("Preço de venda", format="R$ %.2f", min_value=0.0),
        },
    )
    final = renumerar(editado)

    m1, m2, m3 = st.columns(3)
    m1.metric("Produtos", len(final))
    m2.metric("Grupos", final["grupo"].nunique() if not final.empty else 0)
    m3.metric("Sem preço", int((final["preco_venda"] <= 0).sum()) if not final.empty else 0)

    avisos = validar(final)
    if avisos:
        with st.expander(f"⚠️ {len(avisos)} ponto(s) para revisar", expanded=True):
            for aviso in avisos:
                st.write("• " + aviso)
    else:
        st.success("Tudo certo: nenhum problema encontrado.")

    nome_base = st.session_state.get("nome_base", "cardapio")
    d1, d2 = st.columns(2)
    d1.download_button(
        "⬇️ Baixar planilha (Excel)",
        data=gerar_excel(final),
        file_name=f"importacao_{nome_base}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        type="primary",
        disabled=final.empty,
    )
    d2.download_button(
        "⬇️ Baixar CSV",
        data=gerar_csv(final),
        file_name=f"importacao_{nome_base}.csv",
        mime="text/csv",
        use_container_width=True,
        disabled=final.empty,
    )
