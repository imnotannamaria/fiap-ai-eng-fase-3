# Assistente Médico com LLM Ajustada

Projeto do Tech Challenge Fase 3 da FIAP PósTech IADT. A ideia é um assistente virtual pra médicos de um hospital: responde dúvidas com base nos protocolos internos, consulta o prontuário do paciente e nunca prescreve nada sozinho.

Em andamento. Por enquanto o repositório tem a parte de dados. As outras etapas (fine-tuning, LangChain, LangGraph, avaliação) entram nos próximos commits.

---

## Os dados

O enunciado fala em dados internos do hospital, mas eu não tenho acesso a nenhum. Então tudo aqui é **sintético, em português**:

- 10 protocolos internos fictícios (sepse, dor torácica, AVC, pneumonia e mais). Escrevi sem nenhuma dose de remédio, de propósito. O assistente tem que apontar o protocolo, não decidir tratamento.
- Uma base de prontuários em SQLite com 40 pacientes falsos (alergias, medicações, exames pendentes e com resultado).
- 5 modelos de laudo, receita e procedimento.

Os protocolos são textos didáticos escritos pra este projeto. Não servem pra uso clínico.

### Anonimização e curadoria

Os modelos de documento nascem com CPF, nome, e-mail e telefone falsos, justamente pra testar a anonimização. Antes de ir pro dataset, tudo passa por `data/anonymize.py`: regex pra CPF, e-mail, telefone, data e prontuário, mais a lista de nomes conhecidos.

Depois vem a curadoria, em `data/build_dataset.py`. Ela descarta exemplo duplicado, resposta sem fonte citada, resposta com dose de remédio e qualquer identificador que sobrou. Como os dados já nascem limpos, ela não descartou nada na versão atual. O que ela garante é que o dataset continue limpo se alguém mudar os protocolos ou os modelos.

O paciente que chega no assistente só aparece como `P-0007`, com idade e sexo. Nome, CPF e telefone ficam na base e nunca saem de `assistant/prontuario.py`.

### O dataset de instrução

327 exemplos em formato de chat, em `data/processed/`:

| Tipo | O que ensina |
|---|---|
| protocolo | responder pergunta usando só o trecho do protocolo e citar a fonte |
| paciente | juntar os dados do prontuário com o protocolo |
| recusa | negar pedido de prescrição ou dose e apontar o protocolo |
| sem_fonte | dizer "não encontrei" quando o protocolo não tem a resposta |
| documento | montar rascunho de laudo, receita ou procedimento com os campos em branco |

O split é feito por grupo, pra o mesmo paciente, o mesmo pedido ou o mesmo tema nunca cair em dois conjuntos. Nos protocolos, a terceira forma de cada pergunta fica de fora do treino.

---

## Como rodar

Precisa de um Mac com Apple Silicon e do [uv](https://docs.astral.sh/uv/). O Python é o 3.12 porque as bibliotecas de ML ainda não têm versão pro 3.14.

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e ".[dev]"
```

Gerar a base de prontuários e o dataset:

```bash
.venv/bin/python -m hospital_assistant.data.build_dataset
```

Rodar os testes:

```bash
.venv/bin/python -m pytest
```

---

## Estrutura

```
.
├── data/
│   ├── processed/                 train, valid e test em JSONL + relatório da curadoria
│   └── synthetic/                 base de prontuários (gerada pelo script)
├── src/hospital_assistant/
│   ├── config.py
│   ├── data/                      protocolos, base sintética, anonimização, dataset
│   └── assistant/                 acesso ao prontuário e formato do prompt
├── tests/
└── pyproject.toml
```
