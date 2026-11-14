"""Anonimização de texto clínico por regras (regex) e lista de nomes conhecidos.

Roda antes de qualquer texto ir para o dataset de treino. Não é perfeita:
serve como camada extra, já que a fonte dos dados é sintética.
"""

import re

PADROES = [
    ("CPF", re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")),
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    ("TELEFONE", re.compile(r"(?:\+?55\s?)?\(?\b\d{2}\)?\s?9?\d{4}-?\d{4}\b")),
    ("DATA", re.compile(r"\b\d{2}/\d{2}/\d{4}\b")),
    ("PRONTUARIO", re.compile(r"\b(?:pront(?:u[aá]rio)?|MRN)[:\s#]*\d{4,}\b", re.I)),
]


def anonimizar(texto: str, nomes: list[str] | None = None) -> str:
    """Troca identificadores por marcadores como [CPF] e [NOME]."""
    for nome in sorted(nomes or [], key=len, reverse=True):
        texto = re.sub(re.escape(nome), "[NOME]", texto, flags=re.I)
    for rotulo, padrao in PADROES:
        texto = padrao.sub(f"[{rotulo}]", texto)
    return texto


def tem_identificador(texto: str) -> bool:
    return any(p.search(texto) for _, p in PADROES)
