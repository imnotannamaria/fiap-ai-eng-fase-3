"""Formato do prompt. Treino e inferência usam exatamente o mesmo, senão o modelo
aprende uma coisa e recebe outra."""

from hospital_assistant.config import SYSTEM_PROMPT
from hospital_assistant.data.protocols import CAMPOS


def trecho(protocolo: dict, campo: str) -> str:
    return f"({protocolo['id']} | {protocolo['titulo']} | {CAMPOS[campo]}) {protocolo[campo]}"


def montar_pergunta(pergunta: str, trechos: list[str], paciente: str | None = None) -> str:
    blocos = ["[PROTOCOLOS]", *(trechos or ["(nenhum trecho relevante encontrado)"]), "[/PROTOCOLOS]"]
    if paciente:
        blocos += ["[PACIENTE]", paciente, "[/PACIENTE]"]
    blocos.append(f"Pergunta: {pergunta}")
    return "\n".join(blocos)


def mensagens(pergunta: str, trechos: list[str], paciente: str | None = None) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": montar_pergunta(pergunta, trechos, paciente)},
    ]
