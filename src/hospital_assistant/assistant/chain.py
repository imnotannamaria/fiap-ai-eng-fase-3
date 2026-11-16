"""Assistente: chain LangChain que junta protocolo, prontuário e a LLM ajustada.

Fluxo:
    pergunta -> acha o paciente -> busca o protocolo -> monta o prompt (mesmo formato do treino)
             -> LLM ajustada (Ollama) -> resposta + fontes usadas
"""

import re
from dataclasses import dataclass, field

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import convert_to_messages
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_ollama import ChatOllama

from hospital_assistant.assistant import prontuario
from hospital_assistant.assistant.prompting import mensagens
from hospital_assistant.assistant.retriever import ProtocoloRetriever
from hospital_assistant.config import OLLAMA_MODEL, OLLAMA_URL

ID_PACIENTE = re.compile(r"\bP-\d{4}\b", re.I)
CITACAO = re.compile(r"\[(PROT-\d+|MOD-[\w-]+|PRONTUARIO P-\d+)\]")


@dataclass
class Resposta:
    pergunta: str
    texto: str
    paciente_id: str | None
    fontes: list[dict] = field(default_factory=list)  # o que foi entregue ao modelo
    trechos: list[str] = field(default_factory=list)  # texto dos trechos entregues
    citadas: list[str] = field(default_factory=list)  # o que o modelo disse ter usado
    mensagens: list[dict] = field(default_factory=list)


def criar_llm() -> BaseChatModel:
    return ChatOllama(model=OLLAMA_MODEL, base_url=OLLAMA_URL, temperature=0, num_predict=400)


class Assistente:
    def __init__(self, llm: BaseChatModel | None = None, retriever: ProtocoloRetriever | None = None):
        self.llm = llm or criar_llm()
        self.retriever = retriever or ProtocoloRetriever()
        self.cadeia = RunnableLambda(self._contextualizar) | RunnablePassthrough.assign(
            texto=RunnableLambda(lambda c: convert_to_messages(c["mensagens"])) | self.llm | StrOutputParser()
        )

    def _contextualizar(self, entrada: dict) -> dict:
        pergunta = entrada["pergunta"]
        pid = entrada.get("paciente_id")
        if not pid:
            achou = ID_PACIENTE.search(pergunta)
            pid = achou.group(0).upper() if achou else None
        paciente = prontuario.consultar_paciente(pid) if pid else None
        protocolo = paciente["atendimento"]["protocolo"] if paciente and paciente["atendimento"] else None
        docs = self.retriever.recuperar(pergunta, protocolo)

        fontes = [{"tipo": "protocolo", "id": d.metadata["fonte"], "campo": d.metadata["campo"], "nota": d.metadata["nota"]} for d in docs]
        if paciente:
            fontes.append({"tipo": "prontuario", "id": paciente["id"]})
        paciente_txt = prontuario.formatar_paciente(paciente) if paciente else None
        return {
            "pergunta": pergunta,
            "paciente_id": pid,
            "fontes": fontes,
            "trechos": [d.page_content for d in docs],
            "mensagens": mensagens(pergunta, [d.page_content for d in docs], paciente_txt),
        }

    def perguntar(self, pergunta: str, paciente_id: str | None = None) -> Resposta:
        saida = self.cadeia.invoke({"pergunta": pergunta, "paciente_id": paciente_id})
        return Resposta(
            pergunta=pergunta,
            texto=saida["texto"].strip(),
            paciente_id=saida["paciente_id"],
            fontes=saida["fontes"],
            trechos=saida["trechos"],
            citadas=CITACAO.findall(saida["texto"]),
            mensagens=saida["mensagens"],
        )
