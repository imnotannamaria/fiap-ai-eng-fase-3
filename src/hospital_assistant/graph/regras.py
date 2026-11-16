"""Regras do fluxo do paciente. Funções puras, sem LangGraph e sem modelo, pra testar fácil.

O fluxo decide o que é alerta por regra, não pelo modelo. O modelo só redige a sugestão.
"""

import re

from hospital_assistant.assistant.retriever import normalizar
from hospital_assistant.safety.alergias import checar_alergia

# nome do exame -> como ele aparece escrito (sem acento) no texto do protocolo e no prontuário
EXAMES = {
    "lactato": ["lactato"],
    "hemocultura": ["hemocultura"],
    "hemograma": ["hemograma"],
    "creatinina": ["creatinina"],
    "bilirrubina": ["bilirrubina"],
    "gasometria": ["gasometria"],
    "urina tipo 1": ["urina tipo 1"],
    "urocultura": ["urocultura"],
    "radiografia de tórax": ["radiografia de torax"],
    "ECG": ["ecg", "eletrocardiograma"],
    "troponina": ["troponina"],
    "eletrólitos": ["eletrolitos", "sodio", "potassio"],
    "tomografia de crânio": ["tomografia de cranio"],
    "glicemia": ["glicemia"],
    "coagulograma": ["coagulograma"],
    "ureia": ["ureia"],
    "proteína C reativa": ["proteina c reativa"],
    "oximetria": ["oximetria"],
    "cetonas": ["cetonas"],
    "triptase": ["triptase"],
    "D-dímero": ["d-dimero", "d dimero"],
    "angiotomografia de tórax": ["angiotomografia de torax"],
    "BNP": ["bnp"],
}
# palavras da conduta que indicam medicação. Aí vale lembrar da alergia, mesmo sem remédio citado pelo nome.
PALAVRAS_DE_MEDICACAO = re.compile(r"antibiotic|medicac|insulina|diuretic|anticoag|trombolise|prescri", re.I)


def _condicional(texto: str, inicio: int, fim: int) -> bool:
    """O exame só vale em certa condição: "hemocultura se internação", "e, se possível, triptase"."""
    antes, depois = texto[max(0, inicio - 40):inicio], texto[fim:fim + 25]
    return bool(re.search(r",\s*se\b|\be,\s*se\b", antes) or re.match(r"\s*se\b", depois))


def exames_previstos(protocolo: dict) -> list[str]:
    """Exames que o protocolo pede sempre (os condicionais ficam de fora)."""
    texto = normalizar(protocolo["exames"])
    achados = []
    for nome, apelidos in EXAMES.items():
        for apelido in apelidos:
            for m in re.finditer(re.escape(apelido), texto):
                if not _condicional(texto, m.start(), m.end()):
                    achados.append(nome)
                    break
            else:
                continue
            break
    return achados


def _cobre(nome_no_prontuario: str, exame: str) -> bool:
    texto = normalizar(nome_no_prontuario)
    return any(a in texto for a in EXAMES[exame])


def exames_sem_pedido(paciente: dict, protocolo: dict) -> list[str]:
    """Exames previstos no protocolo que não aparecem no prontuário do paciente."""
    pedidos = [e["exame"] for e in paciente["exames"]]
    return [ex for ex in exames_previstos(protocolo) if not any(_cobre(p, ex) for p in pedidos)]


def exames_alterados(paciente: dict) -> list[str]:
    return [e["exame"] for e in paciente["exames"] if e["resultado"] == "alterado"]


def avaliar_alertas(paciente: dict, protocolo: dict) -> list[dict]:
    """Alertas para a equipe. Níveis: crítico (emite pra equipe), atenção, informativo."""
    alertas = []
    for exame in exames_alterados(paciente):
        alertas.append({
            "nivel": "crítico", "tipo": "resultado_alterado", "fonte": f"PRONTUARIO {paciente['id']}",
            "texto": f"Resultado alterado: {exame}. Revisar com o médico responsável.",
        })
    # alergia contra o que a conduta do protocolo cita (ex.: angiotomografia usa contraste iodado)
    for a in checar_alergia(paciente, protocolo["conduta"]):
        alertas.append({
            "nivel": "crítico" if a.tipo == "direta" else "atenção", "tipo": "alergia_na_conduta",
            "fonte": f"PRONTUARIO {paciente['id']}", "texto": a.texto,
        })
    reais = [a for a in paciente["alergias"] if a != "nenhuma conhecida"]
    ja_alertou = any(al["tipo"] == "alergia_na_conduta" for al in alertas)
    if reais and PALAVRAS_DE_MEDICACAO.search(normalizar(protocolo["conduta"])) and not ja_alertou:
        alertas.append({
            "nivel": "atenção", "tipo": "alergia_antes_de_medicar", "fonte": f"PRONTUARIO {paciente['id']}",
            "texto": f"A conduta do protocolo envolve medicação e o paciente tem alergia registrada a {', '.join(reais)}. Conferir antes de qualquer medicação.",
        })
    pendentes = [e["exame"] for e in paciente["exames"] if e["status"] == "pendente"]
    if pendentes:
        alertas.append({
            "nivel": "atenção", "tipo": "exames_pendentes", "fonte": f"PRONTUARIO {paciente['id']}",
            "texto": f"Exames pendentes: {', '.join(pendentes)}.",
        })
    faltando = exames_sem_pedido(paciente, protocolo)
    if faltando:
        alertas.append({
            "nivel": "informativo", "tipo": "exames_previstos_sem_pedido", "fonte": protocolo["id"],
            "texto": f"O protocolo de {protocolo['titulo'].lower()} prevê e o prontuário não tem pedido de: {', '.join(faltando)}.",
        })
    return alertas
