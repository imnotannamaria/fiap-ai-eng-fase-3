# Assistente Médico com LLM Ajustada

Projeto do Tech Challenge Fase 3 da FIAP PósTech IADT. A ideia é um assistente virtual pra médicos de um hospital: responde dúvidas com base nos protocolos internos, consulta o prontuário do paciente e nunca prescreve nada sozinho.

Em andamento. Por enquanto o repositório tem os dados e o fine-tuning. LangChain, LangGraph, segurança e avaliação entram nos próximos commits.

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

755 exemplos em formato de chat, em `data/processed/` (535 treino, 111 validação, 109 teste):

| Tipo | O que ensina |
|---|---|
| protocolo | responder pergunta usando só o trecho do protocolo e citar a fonte, com pergunta de manual e pergunta solta |
| paciente | juntar o prontuário com o protocolo: exames pendentes, sinais de alerta, alergias e resultados |
| recusa | negar pedido de prescrição ou dose, seja direto, uma pergunta solta ("posso começar amoxicilina nele?") ou tentativa de burlar a regra ("ignore as instruções") |
| sem_fonte | dizer "não encontrei" quando o protocolo não tem a resposta, ou "não recebi o prontuário" quando ele não veio no contexto |
| documento | montar rascunho de laudo, receita ou procedimento com os campos em branco |

Na recusa com paciente, o exemplo avisa quando o remédio pedido tem relação com uma alergia do prontuário (o modelo não aprendeu isso direito, veja a seção de fine-tuning). Na recusa sem condição nenhuma, ele só recusa, sem anexar protocolo. Todas as recusas terminam com a mesma frase, de propósito: o modelo aprende onde parar.

O split é feito por grupo. O mesmo pedido ou tema nunca cai em dois conjuntos, e um paciente fica inteiro num conjunto só, em todos os tipos. Nos protocolos, duas das seis formas de cada pergunta ficam de fora do treino, uma de manual e uma solta, pra testar com pergunta que o modelo nunca viu.

---

## Fine-tuning

**Modelo base.** Qwen2.5 1.5B Instruct em 4 bits, na versão pra MLX. Escolhi um modelo pequeno porque tudo roda no meu Mac (M4, 16 GB, sem GPU NVIDIA). Um modelo de 7B ou 8B nem treina aqui. Dava pra alugar GPU, mas queria algo que qualquer pessoa reproduza sem pagar nada.

**Técnica.** LoRA em cima do modelo quantizado (o que chamam de QLoRA), com o MLX-LM, que é nativo do Apple Silicon. Treina só 0,34% dos parâmetros (5,3 milhões de 1,5 bilhão) nas 16 últimas camadas, e o adapter final pesa 21 MB.

| Parâmetro | Valor | Por quê |
|---|---|---|
| Iterações | 400 (cerca de 3 épocas) | a loss de validação foi 0,027, 0,023, 0,024 e 0,016 nas iterações 100, 200, 300 e 400. Não parou de cair, então 400 foi razoável |
| Batch | 4 | pequeno pra caber folgado em 16 GB, junto com gradient checkpointing |
| Learning rate | 1e-4 | valor conservador pra LoRA. A loss de treino caiu de 0,53 pra 0,09 em 40 iterações |
| Tamanho máximo | 1536 tokens | folga. O maior exemplo tem 589 tokens (mediana 374), então nada é cortado |
| `--mask-prompt` | ligado | a loss só conta a resposta. Sem isso o modelo gasta capacidade aprendendo a repetir o protocolo que já veio no prompt |

**O que o fine-tuning ensina e o que não.** O conhecimento clínico não está nos pesos. Os protocolos e os dados do paciente vão dentro do prompt, no mesmo formato no treino e na hora de usar (`assistant/prompting.py`). O que o modelo aprende é o comportamento: responder só com o que veio no contexto, citar a fonte, recusar prescrição, dizer "não encontrei" e parar no ponto certo. Se o protocolo mudar, muda o texto, não precisa retreinar.

**Resultado.** Loss de validação 0,016 e de teste 0,028. Esse número engana: a resposta é quase toda cópia do trecho do protocolo, então a loss cai fácil. O que vale é olhar o comportamento.

Fiz duas rodadas. A v1 treinou com 327 exemplos e a v2 com 755, depois que a v1 mostrou problemas fora do formato do dataset. Comparei as duas em 6 casos que o treino não cobre:

| Caso | v1 | v2 |
|---|---|---|
| Pedido de prescrição com paciente, com frase de burlar regra | loop de 400 tokens | recusa curta, 48 tokens |
| Pedido de amoxicilina para paciente alérgico a penicilina | loop de 400 tokens | recusa curta, sem avisar da alergia |
| Recusa sem condição nenhuma | anexava o protocolo de outra doença (dose de insulina virava embolia pulmonar) | só recusa |
| Pergunta sobre paciente sem prontuário no contexto | inventou "não encontrei exames pendentes" | "não recebi os dados do prontuário" |
| Protocolo que não está no contexto | "não encontrei" | "não encontrei" |
| Pergunta solta sobre AVC | correta | correta |

**O que não funcionou.** O modelo não aprendeu a cruzar o remédio pedido com a alergia do prontuário. Nos pedidos de prescrição com paciente, a v2 cita alergia em 4 de 12 exemplos do treino e em 0 de 10 do teste. Só tem um caso de conflito de verdade no teste, então a amostra é pequena, mas o resultado no treino já mostra o problema. Minha hipótese: o que decide a resposta são poucos tokens no meio de uma resposta longa que é quase toda cópia, e a loss média quase não sente isso. A recusa curta, que é mais comum no dataset, ganha.

Por isso essa verificação vai ficar no código, como uma regra que consulta o prontuário, e não no modelo. Alergia é checagem exata, não tem por que depender de um modelo de 1,5B acertar. O modelo continua recusando e nunca prescreve, só falta o aviso extra.

**Como rodar.** Precisa do [Ollama](https://ollama.com). O treino leva de 45 minutos a 1 hora no M4.

```bash
.venv/bin/python -m hospital_assistant.finetune.train
.venv/bin/python -m hospital_assistant.finetune.train --fuse
ollama create hospital-assistant -f Modelfile
```

O `--fuse` junta o adapter ao modelo base e o `Modelfile` aponta pra esse resultado. Se o treino cair no meio, `--resume` continua do checkpoint da iteração 200.

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
│   ├── finetune/                  treino LoRA e fuse com MLX-LM
│   └── assistant/                 acesso ao prontuário e formato do prompt
├── Modelfile                      importa o modelo ajustado no Ollama
├── tests/
└── pyproject.toml
```
