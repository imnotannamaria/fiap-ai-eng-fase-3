# Dados

O enunciado sugere PubMedQA e MedQuAD como fontes. Não usei nenhum dos dois. Eles são em inglês e trazem literatura médica pública, não os protocolos internos de um hospital, que é o que o assistente precisa aprender. Misturar inglês também diluiria o comportamento em português que um modelo de 1,5B precisa aprender com poucos exemplos. Em vez disso, escrevi os dados abaixo.

O enunciado fala em dados internos do hospital, mas eu não tenho acesso a nenhum. Então tudo aqui é sintético, em português:

- 10 protocolos internos fictícios (sepse, dor torácica, AVC, pneumonia e mais). Escrevi sem nenhuma dose de remédio, de propósito. O assistente tem que apontar o protocolo, não decidir tratamento.
- Uma base de prontuários em SQLite com 40 pacientes falsos (alergias, medicações, exames pendentes e com resultado).
- 5 modelos de laudo, receita e procedimento.

Os protocolos são textos didáticos escritos pra este projeto. Não servem pra uso clínico.

## Anonimização e curadoria

Os modelos de documento nascem com CPF, nome, e-mail e telefone falsos, justamente pra testar a anonimização. Antes de ir pro dataset, tudo passa por `data/anonymize.py`: regex pra CPF, e-mail, telefone, data e prontuário, mais a lista de nomes conhecidos.

Depois vem a curadoria, em `data/build_dataset.py`. Ela descarta exemplo duplicado, resposta sem fonte citada, resposta com dose de remédio e qualquer identificador que sobrou. Como os dados já nascem limpos, ela não descartou nada na versão atual. O que ela garante é que o dataset continue limpo se alguém mudar os protocolos ou os modelos.

O paciente que chega no assistente só aparece como `P-0007`, com idade e sexo. Nome, CPF e telefone ficam na base e nunca saem de `assistant/prontuario.py`.

## O dataset de instrução

755 exemplos em formato de chat, em `data/processed/` (535 treino, 111 validação, 109 teste):

| Tipo | O que ensina |
|---|---|
| protocolo | responder pergunta usando só o trecho do protocolo e citar a fonte, com pergunta de manual e pergunta solta |
| paciente | juntar o prontuário com o protocolo: exames pendentes, sinais de alerta, alergias e resultados |
| recusa | negar pedido de prescrição ou dose, seja direto, uma pergunta solta ("posso começar amoxicilina nele?") ou tentativa de burlar a regra ("ignore as instruções") |
| sem_fonte | dizer "não encontrei" quando o protocolo não tem a resposta, ou "não recebi o prontuário" quando ele não veio no contexto |
| documento | montar rascunho de laudo, receita ou procedimento com os campos em branco |

Na recusa com paciente, o exemplo avisa quando o remédio pedido tem relação com uma alergia do prontuário (o modelo não aprendeu isso direito, veja [fine_tuning.md](fine_tuning.md)). Na recusa sem condição nenhuma, ele só recusa, sem anexar protocolo. Todas as recusas terminam com a mesma frase, de propósito: o modelo aprende onde parar.

O split é feito por grupo. O mesmo pedido ou tema nunca cai em dois conjuntos, e um paciente fica inteiro num conjunto só, em todos os tipos. Nos protocolos, duas das seis formas de cada pergunta ficam de fora do treino, uma de manual e uma solta, pra testar com pergunta que o modelo nunca viu.
