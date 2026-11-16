# Segurança, privacidade e uso responsável

## Escopo e princípio central

Este projeto usa dados **sintéticos**. Ele demonstra um assistente de apoio ao médico e não deve ser ligado a prontuários reais sem avaliação institucional, jurídica e clínica. O princípio que guiou tudo: **o limite não pode depender de o modelo se comportar.** O modelo recusa prescrição porque foi treinado pra isso, mas cada garantia também tem uma regra no código.

## Riscos e controles

| Risco | Controle adotado |
|---|---|
| Prescrição ou dose pelo modelo | Treino com recusas, validação da saída (dose, posologia, verbo de prescrição) e resposta segura no lugar. Medido: 0 doses no texto final em 151 perguntas com os quatro sistemas |
| Ataque de "ignore as regras" | A entrada é marcada e registrada, e a barreira é a validação da saída. Testado com um modelo falso que obedece o ataque: 0 vazamentos em 28 combinações |
| Remédio que conflita com alergia | Tabela de alergia no código. O modelo sozinho avisou em 9% dos casos, com a regra foi 22 de 22 |
| Modelo errando dado do prontuário | Conferência de fidelidade: listas de pendentes, resultados e alergias têm que bater com o prontuário. As listas do plano são calculadas por código |
| Fonte inventada | A validação reprova citação que não foi entregue ao modelo e resposta sem fonte |
| Decisão sem humano | Toda resposta sai como "aguardando validação médica". O fluxo pausa em `interrupt` e só segue com decisão de médico identificado. Decisão inválida rejeita |
| Adulteração do log | Log JSONL com hash encadeado. `verificar()` aponta a linha onde a corrente quebra |
| Vazamento de dado pessoal | Dados sintéticos, anonimização por regex, assistente só vê `P-0007` com idade e sexo, pergunta anonimizada antes de ir pro log |
| Dado enviado a terceiros | O modelo roda local, no Ollama. Nenhuma chave de API é necessária |
| Modelo cair | O fluxo continua com o texto do protocolo e os dados do prontuário |
| Segredos expostos | Não há segredo no projeto. Logs, modelos e a base de prontuários ficam fora do Git |

## O que fica no log

Uma linha por consulta: quem perguntou, a pergunta anonimizada, o paciente, as fontes entregues e as citadas, os alertas de alergia, a decisão da validação, **o que o modelo disse e o que saiu pro médico**, o modelo usado, um hash do prompt, a latência e o status. O fluxo grava ainda `fluxo_gerado`, `decisao_medica` e `fluxo_encerrado`, com o mesmo hash do plano nos dois primeiros.

## O que isso não cobre

- O validador só conhece dose com unidade, posologia nos formatos listados e os verbos de prescrição que escrevi. Uma prescrição escrita de outro jeito passa.
- A tabela de alergias é pequena (5 alergias, uns 25 termos), sem nome comercial nem erro de digitação.
- O hash encadeado evidencia adulteração, mas quem tem acesso ao arquivo pode refazer a corrente inteira. Proteção de verdade pede gravar o último hash em outro lugar.
- A anonimização do log não pega nome digitado na pergunta.
- Os 24 ataques medidos têm forma parecida com os do treino. Ataque escrito de um jeito novo só é barrado pela validação da saída.
- Resultado alterado vira alerta crítico sem olhar qual exame é.
- Nada passou por avaliação clínica, validação com médicos ou análise de conformidade com a LGPD. Um uso real pediria governança de dados, controle de acesso, retenção de logs e aprovação ética e clínica.
