"""Configurações do Extrator de Cardápio."""

# Modelos do Gemini, em ordem de preferência.
# Se um estiver sobrecarregado, fora do ar ou descontinuado, o próximo é usado.
MODELOS_GEMINI = [
    "gemini-3.8-flash",
    "gemini-flash-latest",
    "gemini-2.5-flash",
]

URL_API = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"

# Tempo máximo de espera por modelo (cardápios em PDF podem demorar)
TIMEOUT_SEGUNDOS = 90

# Quantas voltas completas na lista de modelos antes de desistir
TENTATIVAS = 2
ESPERA_ENTRE_TENTATIVAS = 5

# Tipos de arquivo aceitos
TIPOS_ACEITOS = {
    "pdf": "application/pdf",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
}

# Limite de envio direto para a API (dados inline)
TAMANHO_MAXIMO_MB = 18

# Layout da planilha de importação: nome interno -> título da coluna no arquivo
# Para adaptar a outro sistema, basta mudar os títulos ou a ordem aqui.
LAYOUT_IMPORTACAO = {
    "codigo": "codigo",
    "descricao": "descricao",
    "grupo": "grupo",
    "detalhes": "detalhes",
    "unidade": "unidade",
    "preco_venda": "precovenda",
}

UNIDADE_PADRAO = "UN"
GRUPO_PADRAO = "SEM GRUPO"
