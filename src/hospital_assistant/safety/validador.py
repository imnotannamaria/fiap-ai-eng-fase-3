"""Validação da saída do modelo. É ela que garante o limite de atuação, não o modelo:
mesmo que o modelo seja enganado e obedeça um pedido de prescrição, o texto não passa.

Se reprova, a resposta é trocada por uma resposta segura, com o texto dos protocolos
sem alteração (mesma ideia do guardrail de fidelidade da fase 2).
"""

import re
from dataclasses import asdict, dataclass, field

from hospital_assistant.assistant.retriever import normalizar

# mesma regra da curadoria do dataset (data/build_dataset.py). Há um teste comparando as duas.
PADRAO_DOSE = re.compile(r"\b\d+([.,]\d+)?\s?(mg|mcg|ml|ui|g)\b", re.I)
# posologia escrita sem unidade de massa: "2 comprimidos", "de 8 em 8 horas", "3 vezes ao dia"
POSOLOGIA = re.compile(
    r"\b\d+\s*(comprimidos?|ampolas?|gotas?|capsulas?|cp)\b|\b(meio|um|uma) (comprimido|ampola|capsula)\b"
    r"|\ba cada \d+ horas?\b|\bde \d+ em \d+ horas?\b|\b\d+ vezes? (ao|por) dia\b"
)
CITACAO = re.compile(r"\[(PROT-\d+|MOD-[\w-]+|PRONTUARIO P-\d+)\]")
SEM_FONTE_OK = ("Não posso", "Não encontrei", "Não recebi")

# modelo falando em primeira pessoa ou mandando fazer: isso é prescrever
PRESCRICAO = re.compile(
    r"\b(prescrevo|prescrevi|receito|autorizo|libero|indico|vou prescrever|vou receitar|pode tomar|tome|administre|inicie)\b"
    r"|\brecomendo (iniciar|administrar|tomar|usar)\b"
)
# o que o modelo afirma sobre o prontuário tem que bater com o prontuário
LISTA_PENDENTES = re.compile(r"Exames pendentes do paciente (P-\d{4}): (.*?) \[PRONTUARIO")
LISTA_RESULTADOS = re.compile(r"Resultados já disponíveis do paciente (P-\d{4}): (.*?)\. Ainda pendentes: (.*?) \[PRONTUARIO")
LISTA_ALERGIAS = re.compile(r"alergia registrada a ([^:.]*?)[:.]")
FECHO_PADRAO = "A decisão clínica e a prescrição são do médico responsável."
LIMITE_CARACTERES = 1800


@dataclass
class Validacao:
    ok: bool
    motivos: list[str] = field(default_factory=list)

    def dict(self) -> dict:
        return asdict(self)


def fontes_entregues(fontes: list[dict]) -> set[str]:
    return {f["id"] if f["tipo"] == "protocolo" else f"PRONTUARIO {f['id']}" for f in fontes}


def _conjunto(lista: str) -> set[str]:
    lista = lista.strip()
    return set() if normalizar(lista) in ("nenhum", "nenhum ainda", "nenhum exame pendente") else {normalizar(x).strip() for x in lista.split(",") if x.strip()}


def checar_fidelidade(texto: str, paciente: dict | None) -> list[str]:
    """Compara com o prontuário as listas que o modelo afirmou. Divergiu, é erro do modelo."""
    if not paciente:
        return []
    pendentes = {normalizar(e["exame"]) for e in paciente["exames"] if e["status"] == "pendente"}
    resultados = {normalizar(f"{e['exame']} ({e['resultado']})") for e in paciente["exames"] if e["resultado"]}
    alergias = {normalizar(a) for a in paciente["alergias"] if a != "nenhuma conhecida"}
    motivos = []
    m = LISTA_PENDENTES.search(texto)
    if m and (m.group(1) != paciente["id"] or _conjunto(m.group(2)) != pendentes):
        motivos.append("exames_pendentes_divergem")
    elif not m and "nenhum exame pendente" in texto and pendentes:
        motivos.append("exames_pendentes_divergem")
    m = LISTA_RESULTADOS.search(texto)
    if m and (_conjunto(m.group(2)) != resultados or _conjunto(m.group(3)) != pendentes):
        motivos.append("resultados_divergem")
    for m in LISTA_ALERGIAS.finditer(texto):
        if _conjunto(m.group(1)) != alergias:
            motivos.append("alergias_divergem")
            break
    return motivos


def validar_saida(texto: str, fontes: list[dict], paciente: dict | None = None) -> Validacao:
    motivos = []
    if not texto.strip():
        return Validacao(False, ["vazia"])
    if PADRAO_DOSE.search(texto):
        motivos.append("dose")
    if POSOLOGIA.search(normalizar(texto)):
        motivos.append("posologia")
    if PRESCRICAO.search(normalizar(texto)):
        motivos.append("prescricao_direta")
    citadas = set(CITACAO.findall(texto))
    if citadas - fontes_entregues(fontes):
        motivos.append("fonte_inventada")
    if not citadas and not texto.startswith(SEM_FONTE_OK):
        motivos.append("sem_fonte")
    frases = [f.strip() for f in re.split(r"(?<=[.!?])\s+", texto) if len(f.strip()) > 30]
    if len(frases) != len(set(frases)):
        motivos.append("repeticao")
    if len(texto) > LIMITE_CARACTERES:
        motivos.append("muito_longa")
    motivos += checar_fidelidade(texto, paciente)
    return Validacao(not motivos, motivos)


def _dados_do_prontuario(paciente: dict) -> str:
    """Resumo do prontuário feito por código, não pelo modelo."""
    pend = [e["exame"] for e in paciente["exames"] if e["status"] == "pendente"]
    alerg = [a for a in paciente["alergias"] if a != "nenhuma conhecida"]
    return (
        f"Do prontuário do paciente {paciente['id']}: exames pendentes: {', '.join(pend) or 'nenhum'}; "
        f"alergias registradas: {', '.join(alerg) or 'nenhuma'} [PRONTUARIO {paciente['id']}]."
    )


def resposta_segura(trechos: list[str], paciente: dict | None = None) -> str:
    """Resposta quando a do modelo reprova: o que os protocolos dizem, sem alteração,
    e os dados do prontuário calculados por código."""
    dados = f"{_dados_do_prontuario(paciente)} " if paciente else ""
    if not trechos:
        return (
            f"{dados}Não consegui gerar uma resposta confiável e não encontrei trecho de protocolo para esta pergunta, "
            "então não vou arriscar. Consulte o médico responsável."
        )
    corpo = []
    for t in trechos:
        cabecalho, _, texto = t.partition(") ")
        codigo = cabecalho.lstrip("(").split(" | ")[0]
        corpo.append(f"{texto} [{codigo}]")
    return (
        f"{dados}Não consegui gerar uma resposta confiável, então não vou arriscar. O que os protocolos internos dizem, sem alteração: "
        + " ".join(corpo)
        + f"\n\n{FECHO_PADRAO}"
    )


def garantir_fecho(texto: str) -> str:
    # "médico" sozinho não basta: a conduta de anafilaxia diz "chamar o médico" e não é o fecho
    return texto if re.search(r"m[eé]dico respons[aá]vel|assinada pelo m[eé]dico", texto, re.I) else f"{texto}\n\n{FECHO_PADRAO}"
