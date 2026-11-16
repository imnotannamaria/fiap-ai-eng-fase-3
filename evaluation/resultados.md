# Resultados da avaliação

Gerado por `python -m hospital_assistant.evaluation.relatorio`. Cada célula é acertos/total, a porcentagem e o intervalo de 95% entre colchetes (Wilson). Com amostras pequenas o intervalo é largo, e isso importa na hora de comparar duas colunas.

Todos os sistemas recebem o mesmo prompt, com temperatura 0, até 400 tokens e penalidade de repetição 1,15. O modelo **base** recebe o mesmo prompt de sistema com todas as regras. Ou seja, ele é o baseline com instrução, não um modelo sem nada.

`base` e `ajustado` rodam na mesma quantização (4 bits, MLX), então a diferença entre os dois é só o adapter. O `v2 implantado` é o modelo que o assistente usa de verdade (adapter fundido em fp16, no Ollama).

## Teste do dataset (109 perguntas)

### Resposta do modelo, sem a camada de segurança

| métrica | base (4 bits) | ajustado (4 bits) | v2 implantado (fp16) | v1 (fp16) |
|---|---|---|---|---|
| protocolo: cita só a fonte certa | 23/60 (38%) [27-51] | 60/60 (100%) [94-100] | 60/60 (100%) [94-100] | 60/60 (100%) [94-100] |
| protocolo: repete o trecho sem alterar | 3/60 (5%) [2-14] | 60/60 (100%) [94-100] | 60/60 (100%) [94-100] | 60/60 (100%) [94-100] |
| paciente: cita o prontuário | 0/20 (0%) [0-16] | 20/20 (100%) [84-100] | 20/20 (100%) [84-100] | 14/20 (70%) [48-85] |
| paciente: menciona todos os exames pendentes (qualquer redação) | 10/10 (100%) [72-100] | 9/10 (90%) [60-98] | 9/10 (90%) [60-98] | 10/10 (100%) [72-100] |
| paciente: afirma listas no formato que o parser confere | 0/20 (0%) [0-16] | 10/20 (50%) [30-70] | 10/20 (50%) [30-70] | 9/20 (45%) [26-66] |
| paciente: das listas que afirma, as que batem com o prontuário | - | 4/10 (40%) [17-69] | 4/10 (40%) [17-69] | 7/9 (78%) [45-94] |
| recusa: declinou o pedido (qualquer frase) | 16/18 (89%) [67-97] | 18/18 (100%) [82-100] | 18/18 (100%) [82-100] | 15/18 (83%) [61-94] |
| recusa: recusou no formato do treino | 14/18 (78%) [55-91] | 18/18 (100%) [82-100] | 18/18 (100%) [82-100] | 15/18 (83%) [61-94] |
| recusa: avisou da alergia (nos casos de conflito) | 0/1 (0%) [0-79] | 0/1 (0%) [0-79] | 0/1 (0%) [0-79] | 1/1 (100%) [21-100] |
| sem fonte: disse que não tem (qualquer frase) | 3/9 (33%) [12-65] | 9/9 (100%) [70-100] | 9/9 (100%) [70-100] | 9/9 (100%) [70-100] |
| sem fonte: disse no formato do treino | 2/9 (22%) [6-55] | 9/9 (100%) [70-100] | 9/9 (100%) [70-100] | 9/9 (100%) [70-100] |
| sem fonte: não citou protocolo | 9/9 (100%) [70-100] | 9/9 (100%) [70-100] | 9/9 (100%) [70-100] | 9/9 (100%) [70-100] |
| geral: sem dose nem posologia | 108/109 (99%) [95-100] | 109/109 (100%) [97-100] | 109/109 (100%) [97-100] | 109/109 (100%) [97-100] |
| geral: sem verbo de prescrição | 109/109 (100%) [97-100] | 109/109 (100%) [97-100] | 109/109 (100%) [97-100] | 109/109 (100%) [97-100] |
| geral: sem repetição nem texto longo | 107/109 (98%) [94-99] | 108/109 (99%) [95-100] | 107/109 (98%) [94-99] | 107/109 (98%) [94-99] |
| geral: não inventou fonte | 99/109 (91%) [84-95] | 109/109 (100%) [97-100] | 109/109 (100%) [97-100] | 107/109 (98%) [94-99] |
| geral: igual à resposta esperada | 0/109 (0%) [0-3] | 34/109 (31%) [23-40] | 32/109 (29%) [22-38] | 21/109 (19%) [13-28] |
| geral: similaridade de palavras com a esperada (F1 médio) | 0.34 | 0.85 | 0.84 | 0.79 |

### O que chega ao médico, com a camada de segurança ligada

| métrica | base (4 bits) | ajustado (4 bits) | v2 implantado (fp16) | v1 (fp16) |
|---|---|---|---|---|
| sem dose nem posologia | 109/109 (100%) [97-100] | 109/109 (100%) [97-100] | 109/109 (100%) [97-100] | 109/109 (100%) [97-100] |
| sem verbo de prescrição | 109/109 (100%) [97-100] | 109/109 (100%) [97-100] | 109/109 (100%) [97-100] | 109/109 (100%) [97-100] |
| paciente: menciona todos os exames pendentes | 10/10 (100%) [72-100] | 10/10 (100%) [72-100] | 10/10 (100%) [72-100] | 10/10 (100%) [72-100] |
| das listas que afirma, as que batem com o prontuário | - | 4/4 (100%) [51-100] | 4/4 (100%) [51-100] | 10/10 (100%) [72-100] |
| avisou da alergia (casos de conflito) | 1/1 (100%) [21-100] | 1/1 (100%) [21-100] | 1/1 (100%) [21-100] | 1/1 (100%) [21-100] |
| respostas trocadas pela resposta segura | 66/109 (61%) [51-69] | 8/109 (7%) [4-14] | 8/109 (7%) [4-14] | 8/109 (7%) [4-14] |

## Fora do molde (42 perguntas)

### Resposta do modelo, sem a camada de segurança

| métrica | base (4 bits) | ajustado (4 bits) | v2 implantado (fp16) | v1 (fp16) |
|---|---|---|---|---|
| protocolo: cita só a fonte certa | 1/10 (10%) [2-40] | 10/10 (100%) [72-100] | 10/10 (100%) [72-100] | 9/10 (90%) [60-98] |
| protocolo: repete o trecho sem alterar | 1/10 (10%) [2-40] | 10/10 (100%) [72-100] | 10/10 (100%) [72-100] | 9/10 (90%) [60-98] |
| paciente: cita o prontuário | 0/8 (0%) [0-32] | 7/8 (88%) [53-98] | 7/8 (88%) [53-98] | 4/8 (50%) [22-78] |
| paciente: menciona todos os exames pendentes (qualquer redação) | 1/1 (100%) [21-100] | 1/1 (100%) [21-100] | 1/1 (100%) [21-100] | 1/1 (100%) [21-100] |
| paciente: afirma listas no formato que o parser confere | 0/8 (0%) [0-32] | 3/8 (38%) [14-69] | 3/8 (38%) [14-69] | 3/8 (38%) [14-69] |
| paciente: das listas que afirma, as que batem com o prontuário | - | 2/3 (67%) [21-94] | 2/3 (67%) [21-94] | 3/3 (100%) [44-100] |
| recusa: declinou o pedido (qualquer frase) | 14/16 (88%) [64-97] | 16/16 (100%) [81-100] | 16/16 (100%) [81-100] | 16/16 (100%) [81-100] |
| recusa: recusou no formato do treino | 7/16 (44%) [23-67] | 15/16 (94%) [72-99] | 15/16 (94%) [72-99] | 14/16 (88%) [64-97] |
| recusa: avisou da alergia (nos casos de conflito) | 0/3 (0%) [0-56] | 1/3 (33%) [6-79] | 1/3 (33%) [6-79] | 0/3 (0%) [0-56] |
| sem fonte: disse que não tem (qualquer frase) | 1/8 (12%) [2-47] | 7/8 (88%) [53-98] | 7/8 (88%) [53-98] | 7/8 (88%) [53-98] |
| sem fonte: disse no formato do treino | 1/8 (12%) [2-47] | 7/8 (88%) [53-98] | 7/8 (88%) [53-98] | 7/8 (88%) [53-98] |
| sem fonte: não citou protocolo | 5/8 (62%) [31-86] | 7/8 (88%) [53-98] | 8/8 (100%) [68-100] | 7/8 (88%) [53-98] |
| geral: sem dose nem posologia | 41/42 (98%) [88-100] | 42/42 (100%) [92-100] | 42/42 (100%) [92-100] | 41/42 (98%) [88-100] |
| geral: sem verbo de prescrição | 41/42 (98%) [88-100] | 42/42 (100%) [92-100] | 42/42 (100%) [92-100] | 42/42 (100%) [92-100] |
| geral: sem repetição nem texto longo | 42/42 (100%) [92-100] | 42/42 (100%) [92-100] | 42/42 (100%) [92-100] | 39/42 (93%) [81-98] |
| geral: não inventou fonte | 35/42 (83%) [69-92] | 40/42 (95%) [84-99] | 41/42 (98%) [88-100] | 38/42 (90%) [78-96] |

### O que chega ao médico, com a camada de segurança ligada

| métrica | base (4 bits) | ajustado (4 bits) | v2 implantado (fp16) | v1 (fp16) |
|---|---|---|---|---|
| sem dose nem posologia | 42/42 (100%) [92-100] | 42/42 (100%) [92-100] | 42/42 (100%) [92-100] | 42/42 (100%) [92-100] |
| sem verbo de prescrição | 42/42 (100%) [92-100] | 42/42 (100%) [92-100] | 42/42 (100%) [92-100] | 42/42 (100%) [92-100] |
| paciente: menciona todos os exames pendentes | 1/1 (100%) [21-100] | 1/1 (100%) [21-100] | 1/1 (100%) [21-100] | 1/1 (100%) [21-100] |
| das listas que afirma, as que batem com o prontuário | - | 2/2 (100%) [34-100] | 2/2 (100%) [34-100] | 5/5 (100%) [57-100] |
| avisou da alergia (casos de conflito) | 3/3 (100%) [44-100] | 3/3 (100%) [44-100] | 3/3 (100%) [44-100] | 3/3 (100%) [44-100] |
| respostas trocadas pela resposta segura | 31/42 (74%) [59-85] | 3/42 (7%) [2-19] | 2/42 (5%) [1-16] | 8/42 (19%) [10-33] |
