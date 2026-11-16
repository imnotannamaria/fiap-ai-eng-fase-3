"""Busca nos protocolos internos. Dois passos, os dois fáceis de explicar:

1. Qual protocolo? BM25 sobre título, sinônimos, definição e critérios de cada protocolo.
   Se nada passa da nota mínima, não devolve nada (o modelo então diz "não encontrei").
   Se tem paciente no contexto, o protocolo da queixa dele ganha um bônus.
2. Qual trecho do protocolo? Pistas na pergunta ("exames", "alerta", "conduta"...)
   escolhem o campo. Sem pista, vai de conduta inicial.

BM25 em vez de embeddings: são 10 protocolos, o BM25 resolve, não precisa de banco
vetorial e dá pra mostrar por que cada trecho veio (nota e campo ficam nos metadados).
"""

import re
import unicodedata

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import PrivateAttr
from rank_bm25 import BM25Okapi

from hospital_assistant.assistant.prompting import trecho
from hospital_assistant.data.protocols import PROTOCOLS, SINONIMOS

# A nota do BM25 só ordena. Quem decide se o protocolo vale é o "termo de identidade":
# a pergunta precisa citar algo do título ou dos sinônimos dele. Sem isso, "como trato uma
# queimadura?" casava com "trato urinário" e a nota sozinha não separava os dois casos.
NOTA_MINIMA = 0.5
BONUS_PACIENTE = 3.0
# palavras de título genéricas demais pra identificar um protocolo
GENERICAS = {"adulto", "agudo", "aguda", "trato", "suspeita", "dor", "adquirida"}

STOPWORDS = set(
    "a o as os um uma uns umas de do da dos das em no na nos nas por para pra com sem sobre e ou que qual quais quando "
    "como se eu ele ela nele dele voce ja so mais muito tem ter tenho tô to esta estao esta ser sao foi pode posso "
    "devo deve me meu minha nosso nossa isso esse essa aqui la aqui protocolo hospital paciente caso chegou algum "
    "alguem pedir peco faco fazer "
    # palavras que dizem QUAL CAMPO o médico quer, não de que doença ele fala
    "alergia alergias medicacao medicacoes tratamento decidir precise saber antes algo alguma usa deixar passar "
    "nesse esse conduta exame exames inicial orienta orientar resultado resultados pendente pendentes".split()
)

# Primeira regra que bater define o campo, olhando a última frase da pergunta primeiro
# (é nela que o médico pede o que quer). Padrões sem acento, o texto é normalizado antes.
REGRAS_CAMPO = [
    ("conduta", r"prescrev|prescri|posologia|\bdose\b"),  # pedido de prescrição: mostra a conduta, mesmo com "emergência" na frase
    ("atencao", r"alergi|medicac|usa algo|antes de (tratar|definir)|cuidado|atencao|conferir|confiro|checar|esquecer de"),
    ("alertas", r"alerta|gravidade|piora|chamar|chamo|chame|plantonista|emergencia|sinais de|deixar passar"),
    ("exames", r"resultado|saiu"),
    ("criterios", r"criterio|suspeit|achados|procuro|indicam|confirmo|como (eu )?sei"),
    ("definicao", r"defin|\bo que e\b|chama de|resumindo"),
    ("conduta", r"pendente|falta de exame"),
    ("exames", r"exame|pedido|pedir|colh|solicit"),
    ("conduta", r"orienta|conduta|primeiro|passo a passo|movimento|comeco|faco"),
]
CAMPO_PADRAO = "conduta"


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def tokenizar(texto: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", normalizar(texto))
    return [t[:6] for t in tokens if t not in STOPWORDS and len(t) > 1]


def escolher_campo(pergunta: str, titulo: str = "") -> str:
    # o título do protocolo não conta: "dor torácica e suspeita de síndrome..." tem a palavra suspeita
    texto = normalizar(pergunta).replace(normalizar(titulo), " ") if titulo else normalizar(pergunta)
    frases = [f for f in re.split(r"[.?!:;,]", texto) if f.strip()]
    for frase in reversed(frases or [texto]):
        for campo, padrao in REGRAS_CAMPO:
            if re.search(padrao, frase):
                return campo
    return CAMPO_PADRAO


class ProtocoloRetriever(BaseRetriever):
    nota_minima: float = NOTA_MINIMA
    bonus_paciente: float = BONUS_PACIENTE
    _indice: BM25Okapi = PrivateAttr()
    _protocolos: list = PrivateAttr()
    _identidade: list = PrivateAttr()

    def model_post_init(self, _contexto) -> None:
        self._protocolos = PROTOCOLS
        textos = [
            f"{(p['titulo'] + ' ') * 3} {SINONIMOS.get(p['id'], '')} {p['definicao']} {p['criterios']}" for p in PROTOCOLS
        ]
        self._indice = BM25Okapi([tokenizar(t) for t in textos])
        genericas = set(tokenizar(" ".join(GENERICAS)))
        self._identidade = [set(tokenizar(f"{p['titulo']} {SINONIMOS.get(p['id'], '')}")) - genericas for p in PROTOCOLS]

    def notas(self, pergunta: str) -> list[float]:
        return list(self._indice.get_scores(tokenizar(pergunta)))

    def recuperar(self, pergunta: str, protocolo_do_paciente: str | None = None) -> list[Document]:
        tokens = set(tokenizar(pergunta))
        notas = [n if tokens & ident else 0.0 for n, ident in zip(self.notas(pergunta), self._identidade)]
        if protocolo_do_paciente:
            notas = [n + (self.bonus_paciente if p["id"] == protocolo_do_paciente else 0) for n, p in zip(notas, self._protocolos)]
        melhor = max(range(len(notas)), key=notas.__getitem__)
        if notas[melhor] < self.nota_minima:
            return []
        protocolo = self._protocolos[melhor]
        campo = escolher_campo(pergunta, protocolo["titulo"])
        return [
            Document(
                page_content=trecho(protocolo, campo),
                metadata={"fonte": protocolo["id"], "protocolo": protocolo["titulo"], "campo": campo, "nota": round(float(notas[melhor]), 2)},
            )
        ]

    def _get_relevant_documents(self, query: str, *, run_manager: CallbackManagerForRetrieverRun) -> list[Document]:
        return self.recuperar(query)
