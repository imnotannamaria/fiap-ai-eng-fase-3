"""Checagem de alergia por regra. Não depende do modelo.

O fine-tuning não aprendeu a cruzar o remédio pedido com a alergia do prontuário (0 de 10
no teste). Alergia é checagem exata, então fica aqui: se a pergunta ou a resposta cita um
remédio ligado a uma alergia registrada do paciente, o aviso entra na resposta.
"""

import re
from dataclasses import asdict, dataclass

from hospital_assistant.assistant.retriever import normalizar

# alergia registrada no prontuário -> termos que têm relação com ela.
# "direta": é a própria substância ou da mesma classe. "cruzada": reação cruzada possível.
TABELA = {
    "penicilina": {
        "direta": ["penicilina", "amoxicilina", "ampicilina", "oxacilina", "piperacilina", "amoxicilina com clavulanato"],
        "cruzada": ["cefalexina", "cefazolina", "ceftriaxona", "cefuroxima", "cefepima"],
    },
    "dipirona": {"direta": ["dipirona", "metamizol"]},
    "sulfa": {"direta": ["sulfametoxazol com trimetoprima", "sulfametoxazol", "trimetoprima", "sulfadiazina"]},
    "iodo": {"direta": ["contraste iodado", "angiotomografia", "tomografia com contraste", "povidona"]},
    "latex": {"direta": ["latex", "luva de latex", "sonda de latex"]},
}


@dataclass(frozen=True)
class AlertaAlergia:
    paciente_id: str
    alergia: str
    termo: str
    tipo: str  # "direta" ou "cruzada"

    @property
    def texto(self) -> str:
        if self.tipo == "direta":
            return (
                f"ALERTA DE ALERGIA: o prontuário do paciente {self.paciente_id} registra alergia a {self.alergia}, "
                f"e {self.termo} tem relação direta com essa alergia [PRONTUARIO {self.paciente_id}]."
            )
        return (
            f"ATENÇÃO: o prontuário do paciente {self.paciente_id} registra alergia a {self.alergia}, "
            f"e {self.termo} pode ter reação cruzada com ela. Confirmar com o médico responsável [PRONTUARIO {self.paciente_id}]."
        )

    def dict(self) -> dict:
        return asdict(self)


def _cita(texto_normalizado: str, termo: str) -> bool:
    return re.search(rf"\b{re.escape(normalizar(termo))}\b", texto_normalizado) is not None


def _achar(paciente: dict, texto_normalizado: str) -> list[AlertaAlergia]:
    achados = []
    for registrada in paciente["alergias"]:
        for tipo, termos in TABELA.get(normalizar(registrada), {}).items():
            for termo in termos:
                if _cita(texto_normalizado, termo):
                    achados.append(AlertaAlergia(paciente["id"], registrada, termo, tipo))
    return achados


def checar_alergia(paciente: dict | None, pergunta: str, *respostas: str) -> list[AlertaAlergia]:
    """Alertas para os remédios citados que batem com alergia registrada do paciente.

    Na pergunta do médico, todo termo conta: "posso dar penicilina?" tem que alertar.
    Na resposta do modelo, o nome da própria alergia não conta como remédio: ela diz
    "alergia a penicilina" por causa do prontuário, e isso não é o modelo sugerindo penicilina.
    """
    if not paciente:
        return []
    nomes_das_alergias = {normalizar(a) for a in paciente["alergias"]}
    alertas = _achar(paciente, normalizar(pergunta))
    for resposta in respostas:
        alertas += [a for a in _achar(paciente, normalizar(resposta)) if normalizar(a.termo) not in nomes_das_alergias]
    unicos = list(dict.fromkeys(alertas))
    # "amoxicilina com clavulanato" também cita "amoxicilina": fica só o termo mais específico
    return [a for a in unicos if not any(a.termo != b.termo and a.termo in b.termo and a.alergia == b.alergia for b in unicos)]
