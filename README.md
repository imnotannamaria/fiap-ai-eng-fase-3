# Assistente Médico com LLM Ajustada: Tech Challenge 3

> Fase 3: fine-tuning de LLM, assistente com LangChain e fluxo automatizado com LangGraph.

Assistente virtual pra médicos de um hospital. Responde dúvidas com base nos protocolos internos, consulta o prontuário do paciente, aciona etapas de um fluxo sozinho (exames pendentes, conduta, alertas) e nunca prescreve nada sem validação humana.

Modelo: Qwen2.5 1.5B Instruct em 4 bits, ajustado com LoRA no MLX-LM (adapter de 21 MB). Roda local, no Mac, com Ollama.

Dados: tudo sintético, em português. 10 protocolos fictícios, 40 pacientes falsos e 755 exemplos de instrução. Não há dado real de hospital e os protocolos não servem pra uso clínico.

---

## O problema

O hospital quer um assistente treinado com os próprios dados, que ajude em condutas clínicas e responda dúvidas de médicos. Em saúde, o erro caro não é responder pouco, é responder errado: dar uma dose, prescrever sem avaliação ou esquecer uma alergia. Por isso o projeto trata o modelo como uma parte do sistema, não como a parte que garante a segurança.

A regra que guiou o desenho: o limite não pode depender de o modelo se comportar. O modelo foi treinado pra recusar prescrição e citar a fonte, e cada garantia importante tem uma regra no código por cima dele.

---

## O que mudou das fases 1 e 2 pra Fase 3

Nas fases 1 e 2 o centro era um classificador de tumores, e a LLM só explicava a saída dele com um guardrail de fidelidade. Na Fase 3 a LLM passa a ser o centro: ela é ajustada com dados do hospital, consulta uma base de prontuários e faz parte de um fluxo de decisão. A ideia do guardrail da fase 2 cresceu e virou uma camada de segurança inteira, com validação da saída, regra de alergia e log de auditoria.

---

## Partes do projeto

| Parte | O que faz | Detalhes |
|---|---|---|
| Dados | protocolos, prontuários e modelos de documento sintéticos, com anonimização e curadoria | [docs/dados.md](docs/dados.md) |
| Fine-tuning | LoRA no Qwen2.5 1.5B com MLX-LM, em duas rodadas (v1 e v2) | [docs/fine_tuning.md](docs/fine_tuning.md) |
| Assistente | chain do LangChain: acha o paciente e o protocolo, monta o prompt e chama a LLM | [docs/assistente.md](docs/assistente.md) |
| Segurança | regra de alergia, validação da saída, classificação da entrada e log de auditoria | [docs/security.md](docs/security.md) |
| Fluxo | grafo do LangGraph com alerta crítico e parada obrigatória na revisão do médico | [docs/fluxo.md](docs/fluxo.md) |
| Avaliação | quatro sistemas em dois conjuntos de perguntas, com intervalo de confiança | [docs/avaliacao.md](docs/avaliacao.md) |

O [relatório técnico](relatorio_tecnico.md) junta tudo isso com os diagramas. A visão geral dos módulos está em [docs/architecture.md](docs/architecture.md).

---

## Resultados

Teste do dataset, 109 perguntas que o modelo nunca viu. O base é o mesmo Qwen sem ajuste, mas recebendo o mesmo prompt de sistema com todas as regras.

| Métrica | Base | v2 ajustado |
|---|---|---|
| Cita só a fonte certa (protocolo) | 23/60 (38%) | 60/60 (100%) |
| Cita o prontuário (paciente) | 0/20 (0%) | 20/20 (100%) |
| Recusa o pedido de prescrição | 16/18 (89%) | 18/18 (100%) |
| Diz que não tem a informação | 3/9 (33%) | 9/9 (100%) |
| Não inventa fonte | 99/109 (91%) | 109/109 (100%) |
| Respostas trocadas pela camada de segurança | 66/109 (61%) | 8/109 (7%) |

O ajuste ensinou comportamento: citar a fonte, recusar e dizer "não encontrei". O base inventou "dipirona 40 mg [PROT-012]" e um protocolo de dengue que não existe. Com a camada de segurança ligada, os quatro sistemas comparados saem sem dose, mas no base ela precisa trocar 61% das respostas. É o ajuste que torna a camada útil.

O que não funcionou, dito de frente:

- O modelo não aprendeu a avisar de alergia (avisou em 9% dos casos). Virou regra de código: 22 de 22.
- O ajuste não melhorou a leitura fiel do prontuário. O modelo erra alguma lista de exames ou alergias em 39% das respostas. Por isso as listas do plano são calculadas por código e a saída é conferida contra o prontuário.
- As amostras são pequenas, as perguntas foram escritas por mim e nenhum médico revisou nada. Os limites completos estão em [docs/avaliacao.md](docs/avaliacao.md).

---

## Como rodar

Precisa de um Mac com Apple Silicon, do [uv](https://docs.astral.sh/uv/) e do [Ollama](https://ollama.com). O Python é o 3.12 porque as bibliotecas de ML ainda não têm versão pro 3.14.

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e ".[dev]"
```

O modelo fundido (2,9 GB) e os logs não vão pro Git (`models/` e `logs/` estão no `.gitignore`), mas o adapter treinado vai, em `adapters/v2/` (21 MB). Dá pra pular o treino e só fundir o adapter ao modelo base. Os testes e a geração do dataset não precisam do Ollama.

Gerar a base de prontuários e o dataset:

```bash
.venv/bin/python -m hospital_assistant.data.build_dataset
```

Opção 1, sem treinar: juntar o adapter versionado ao modelo base e importar no Ollama.

```bash
.venv/bin/python -m hospital_assistant.finetune.train --fuse --adapter-path adapters/v2
ollama create hospital-assistant -f Modelfile
```

Opção 2, treinar do zero (de 45 minutos a 1 hora no M4). Se o treino cair, `--resume` continua do checkpoint da iteração 200:

```bash
.venv/bin/python -m hospital_assistant.finetune.train
.venv/bin/python -m hospital_assistant.finetune.train --fuse
ollama create hospital-assistant -f Modelfile
```

Fazer uma pergunta ao assistente, só com a chain:

```bash
.venv/bin/python -c "
from hospital_assistant.assistant.chain import Assistente
r = Assistente().perguntar('Quais exames estão pendentes do paciente P-0007?')
print(r.texto); print(r.fontes)"
```

Fazer uma pergunta com as camadas de segurança e conferir o log de auditoria:

```bash
.venv/bin/python -c "
from hospital_assistant.safety.seguro import AssistenteSeguro
r = AssistenteSeguro().perguntar('Posso começar amoxicilina nele?', 'P-0005')
print(r.texto); print(r.acao, r.validacao.motivos)"

.venv/bin/python -c "
from hospital_assistant.safety.auditoria import Auditoria
print(Auditoria().verificar())"
```

Rodar o fluxo automatizado e ver o diagrama do grafo. Sem `--decisao`, o terminal pergunta a decisão do médico. O P-0038 mostra o caminho crítico: alérgico a iodo, com resultado alterado na angiotomografia.

```bash
.venv/bin/python -m hospital_assistant.graph P-0038
.venv/bin/python -m hospital_assistant.graph P-0038 --medico "Dra. Demo" --decisao aprovar
.venv/bin/python -m hospital_assistant.graph --mermaid
```

Rodar a avaliação (uns 40 minutos, continua de onde parou se cair) e os testes (220, não precisam do Ollama):

```bash
.venv/bin/python -m hospital_assistant.evaluation.executar
.venv/bin/python -m hospital_assistant.evaluation.relatorio
.venv/bin/python -m pytest
```

---

## Documentação

- [Relatório técnico](relatorio_tecnico.md)
- [Arquitetura](docs/architecture.md)
- [Dados, anonimização e curadoria](docs/dados.md)
- [Fine-tuning](docs/fine_tuning.md)
- [Assistente com LangChain](docs/assistente.md)
- [Segurança e auditoria](docs/security.md)
- [Fluxo automatizado com LangGraph](docs/fluxo.md)
- [Avaliação](docs/avaliacao.md)

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
│   ├── assistant/                 retriever, ferramentas, chain, prontuário e formato do prompt
│   ├── safety/                    regra de alergia, validação da saída, entrada e log de auditoria
│   ├── graph/                     fluxo do paciente em LangGraph, regras de alerta, fila de alertas
│   └── evaluation/                conjuntos, métricas, geradores e relatório da avaliação
├── adapters/v2/                   adapter LoRA treinado (21 MB) e a configuração do treino
├── evaluation/                    respostas de cada sistema, tabelas e erros
├── docs/                          arquitetura e detalhes de cada parte
├── relatorio_tecnico.md
├── Modelfile                      importa o modelo ajustado no Ollama
├── tests/
└── pyproject.toml
```
