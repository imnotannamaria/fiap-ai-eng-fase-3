"""Ferramentas LangChain sobre o prontuário e os protocolos.

Elas devolvem sempre a visão desidentificada (P-0007, idade e sexo). A chain chama
essas ferramentas num fluxo fixo, o modelo não escolhe quando usar: um modelo de 1,5B
decidindo sozinho se consulta o prontuário seria um ponto frágil numa regra de segurança.
No fluxo do LangGraph (Fase 5) elas viram nós.
"""

from langchain_core.tools import tool

from hospital_assistant.assistant import prontuario
from hospital_assistant.assistant.retriever import ProtocoloRetriever

_retriever = ProtocoloRetriever()


@tool
def consultar_paciente(paciente_id: str) -> str:
    """Resumo desidentificado de um paciente: idade, sexo, queixa, alergias, medicações e exames."""
    paciente = prontuario.consultar_paciente(paciente_id)
    if not paciente:
        return f"Paciente {paciente_id} não encontrado."
    return prontuario.formatar_paciente(paciente)


@tool
def listar_exames_pendentes(paciente_id: str) -> str:
    """Lista os exames pendentes de um paciente."""
    paciente = prontuario.consultar_paciente(paciente_id)
    if not paciente:
        return f"Paciente {paciente_id} não encontrado."
    pendentes = prontuario.exames_pendentes(paciente)
    return ", ".join(pendentes) if pendentes else "nenhum exame pendente"


@tool
def buscar_protocolo(pergunta: str, paciente_id: str = "") -> str:
    """Busca o trecho do protocolo interno que responde a pergunta. Devolve vazio se não achar."""
    paciente = prontuario.consultar_paciente(paciente_id) if paciente_id else None
    protocolo = paciente["atendimento"]["protocolo"] if paciente and paciente["atendimento"] else None
    docs = _retriever.recuperar(pergunta, protocolo)
    return "\n".join(d.page_content for d in docs) or "nenhum trecho relevante encontrado"
