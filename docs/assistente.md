# Assistente com LangChain

A chain fica em `assistant/chain.py`. O fluxo é fixo:

```
pergunta -> acha o paciente (ID na pergunta) -> busca o protocolo -> monta o prompt -> LLM ajustada -> resposta + fontes
```

Quem decide o quê. O código busca o protocolo e o prontuário. O modelo só escreve a resposta com o que recebeu. Não deixei o modelo escolher quando consultar o prontuário (o que seria um agente com ferramentas) porque um modelo de 1,5B decidindo isso sozinho seria um ponto frágil justamente na parte de segurança. A chain usa a ferramenta `consultar_paciente` (um `@tool` do LangChain) pra montar o contexto do prompt. `listar_exames_pendentes` e `buscar_protocolo` existem e têm teste, mas nenhum agente as chama neste projeto. O fluxo do LangGraph chama direto as funções de `prontuario.py`.

O prompt tem que ser igual ao do treino. A chain monta o prompt com o mesmo código que gerou o dataset (`assistant/prompting.py`). Tem um teste que refaz o prompt dos 240 exemplos com paciente e compara com o do treino, e os 240 batem exatamente.

Retriever. BM25, em `assistant/retriever.py`, em dois passos:

1. *Qual protocolo?* BM25 sobre título, sinônimos ("AVC", "IC", "ITU"), definição e critérios. O protocolo só vale se a pergunta citar algo que identifica ele (título ou sinônimo). A nota sozinha não separava "AVC" (1,7, dentro do escopo) de "como trato uma queimadura?" (3,1, fora do escopo, porque "trato" casa com "trato urinário"). Se tem paciente no contexto, o protocolo da queixa dele ganha um bônus, então "quais sinais de alerta?" usa o protocolo dele sem precisar dizer a doença.
2. *Qual trecho?* Regras de palavras-chave na pergunta escolhem o campo (conduta, exames, alertas, critérios, definição ou atenção). Sem pista, vai de conduta inicial.

Escolhi BM25 em vez de embeddings porque são 10 protocolos, não precisa de banco vetorial e dá pra mostrar por que cada trecho veio: a nota, o protocolo e o campo ficam nos metadados de cada documento.

Quanto ele acerta. Os números pedem cuidado:

- Nas 178 perguntas do dataset ele acerta protocolo e campo em todas, mas eu ajustei as regras olhando essas mesmas perguntas. Não conta como medida.
- Em 13 perguntas que escrevi à mão, fora dos moldes, ele acertou 12. A que errou foi "quando eu *chamo* o médico", porque a regra só pegava "chamar". Corrigi e virou teste.
- As 26 perguntas escritas à mão ficam em `tests/test_retriever.py`.

A escolha do campo é uma lista de palavras-chave. Funciona nos casos que testei e vai errar com uma pergunta escrita de um jeito que eu não previ. Quando erra, o modelo responde com o trecho errado, mas ainda cita a fonte dele.

O que a chain devolve. Uma `Resposta` com o texto, as fontes que foram entregues ao modelo, as fontes que o modelo disse ter usado e as mensagens enviadas. Isso é a base da explicabilidade e do log de auditoria (veja [security.md](security.md)). A nota vem como número comum, então vira JSON sem conversão.

O aviso de alergia fica fora do modelo. Quando o paciente é alérgico a penicilina e o médico pergunta de amoxicilina, o modelo recusa a prescrição mas não avisa da alergia. Isso ficou numa regra no código, descrita em [security.md](security.md).
