# 🍽️ Extrator de Cardápio com IA

Aplicação web que lê o cardápio de um restaurante (PDF ou foto) com a **API do Google Gemini** e gera automaticamente a **planilha de importação de produtos** do sistema, com descrição, grupo, detalhes, unidade e preço de venda.

<!-- Adicione aqui um print ou GIF da tela: ![Tela do extrator](docs/tela.png) -->

---

## 🎯 O problema

Na implantação de sistemas para restaurantes e food service, o cliente costuma enviar o cardápio em PDF ou foto. Alguém precisa digitar item por item numa planilha no formato exigido para importação: nome, grupo, preço, variações de tamanho... Em cardápios grandes, isso leva horas e gera erros de digitação.

## ✅ A solução

1. O usuário envia o cardápio em **PDF ou imagem**.
2. A IA identifica os produtos, a seção do cardápio (grupo), os ingredientes e o preço de cada item.
3. Itens com vários tamanhos (ex.: Pizza P/M/G) viram **um produto para cada tamanho**.
4. O usuário **revisa e corrige** tudo numa tabela editável antes de exportar.
5. O app aponta o que precisa de atenção, como produtos sem preço ou nomes repetidos.
6. Baixa a planilha pronta em **Excel** ou **CSV** (padrão brasileiro: `;` e vírgula decimal).

## 🧠 Como a IA foi usada

- O arquivo é enviado ao **Gemini** junto com um prompt com regras de negócio de implantação: o que é produto, como tratar tamanhos, o que ignorar (endereço, telefone, taxa de entrega) e a proibição de inventar preços.
- A resposta é pedida em **JSON estruturado** (`responseSchema`), o que garante colunas consistentes.
- **Humano no controle**: a IA faz o trabalho pesado, mas nada é exportado sem passar pela tabela de revisão.
- **Resiliência**: se um modelo estiver sobrecarregado (503), no limite de uso (429), lento demais (timeout) ou descontinuado (404), o código passa automaticamente para o próximo modelo e faz uma nova rodada se todos falharem.

## 🛠️ Tecnologias

Python · Streamlit · API Google Gemini · pandas · openpyxl · pytest

## 📁 Estrutura

```
├── app.py                     # Interface web (Streamlit)
├── extrator/
│   ├── config.py              # Modelos, timeouts e layout da planilha de importação
│   ├── gemini.py              # Chamada à API, prompt, schema e troca automática de modelo
│   └── planilha.py            # Padronização, validação e exportação (Excel/CSV)
├── tests/                     # Testes automatizados (pytest), sem chamar a API real
├── exemplos/
│   └── cardapio_exemplo.pdf   # Cardápio fictício para testar
└── requirements.txt
```

## 🖥️ Como rodar

```bash
pip install -r requirements.txt
streamlit run app.py
```

Acesse http://localhost:8501, informe a chave do Gemini na barra lateral e clique em **Usar cardápio de exemplo** para testar.

A chave pode ser criada gratuitamente em [Google AI Studio](https://aistudio.google.com/apikey). Para não digitar toda vez, defina a variável de ambiente `GEMINI_API_KEY` ou crie o arquivo `.streamlit/secrets.toml` (ele fica fora do repositório):

```toml
GEMINI_API_KEY = "sua-chave-aqui"
```

## 🧪 Testes

```bash
pytest
```

Os testes cobrem conversão de preços (`R$ 1.234,50` → `1234.5`), padronização e remoção de duplicados, validação, exportação e a troca automática de modelo quando a API falha — tudo simulado, sem gastar chamadas da API.

## 📋 Layout da planilha gerada

| codigo | descricao | grupo | detalhes | unidade | precovenda |
|---|---|---|---|---|---|
| 1 | X-Burguer | LANCHES | Pão brioche, hambúrguer 150g, queijo | UN | 24,90 |
| 5 | Pizza Calabresa - G | PIZZAS | Molho, mussarela, calabresa e cebola | UN | 64,90 |

Para adaptar a outro sistema, basta alterar os títulos ou a ordem das colunas em `LAYOUT_IMPORTACAO`, no arquivo `extrator/config.py`.

## 🚀 Próximos passos

- Aceitar planilhas desorganizadas (Excel) como entrada, além de PDF e imagem.
- Gerar também a planilha de importação de **clientes**.
- Sugerir NCM e unidade de medida para cada produto.

---

Desenvolvido por **Luan Grun** · [LinkedIn](https://linkedin.com/in/luan-grun-a60a46208) · [GitHub](https://github.com/luangrunn)
