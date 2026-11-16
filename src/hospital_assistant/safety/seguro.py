"""Assistente com as camadas de segurança em volta da chain.

    pergunta -> classifica a entrada -> assistente (LLM ajustada) -> regra de alergia
             -> validação da saída (troca por resposta segura se reprovar) -> log de auditoria

A resposta final sempre sai marcada como aguardando validação médica.
"""

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from hospital_assistant.assistant import prontuario
from hospital_assistant.assistant.chain import Assistente
from hospital_assistant.data.anonymize import anonimizar
from hospital_assistant.safety.alergias import AlertaAlergia, checar_alergia
from hospital_assistant.safety.auditoria import Auditoria
from hospital_assistant.safety.entrada import classificar_entrada
from hospital_assistant.safety.validador import Validacao, garantir_fecho, resposta_segura, validar_saida

STATUS_REVISAO = "aguardando validação médica"


@dataclass
class RespostaSegura:
    id: str
    texto: str
    paciente_id: str | None
    fontes: list[dict]
    alertas: list[AlertaAlergia]
    validacao: Validacao
    acao: str  # "resposta_do_modelo" ou "resposta_segura"
    flags_entrada: list[str]
    resposta_do_modelo: str
    status_revisao: str = STATUS_REVISAO
    auditoria: dict = field(default_factory=dict)


class AssistenteSeguro:
    def __init__(self, assistente: Assistente | None = None, auditoria: Auditoria | None = None):
        self.assistente = assistente or Assistente()
        self.auditoria = auditoria or Auditoria()

    def perguntar(self, pergunta: str, paciente_id: str | None = None, usuario: str = "anonimo") -> RespostaSegura:
        inicio = time.perf_counter()
        flags = classificar_entrada(pergunta)
        r = self.assistente.perguntar(pergunta, paciente_id)

        paciente = prontuario.consultar_paciente(r.paciente_id) if r.paciente_id else None
        alertas = checar_alergia(paciente, pergunta, r.texto)

        validacao = validar_saida(r.texto, r.fontes)
        corpo = r.texto if validacao.ok else resposta_segura(r.trechos)
        acao = "resposta_do_modelo" if validacao.ok else "resposta_segura"
        final = "\n\n".join([*(a.texto for a in alertas), garantir_fecho(corpo)])

        resposta = RespostaSegura(
            id=str(uuid.uuid4()), texto=final, paciente_id=r.paciente_id, fontes=r.fontes, alertas=alertas,
            validacao=validacao, acao=acao, flags_entrada=flags, resposta_do_modelo=r.texto,
        )
        resposta.auditoria = self.auditoria.registrar({
            "id": resposta.id,
            "quando": datetime.now(timezone.utc).isoformat(),
            "usuario": usuario,
            "pergunta": anonimizar(pergunta),
            "paciente_id": r.paciente_id,
            "flags_entrada": flags,
            "fontes_entregues": r.fontes,
            "fontes_citadas": r.citadas,
            "alertas_alergia": [a.dict() for a in alertas],
            "validacao": validacao.dict(),
            "acao": acao,
            "modelo": getattr(self.assistente.llm, "model", "desconhecido"),
            "prompt_sha256": hashlib.sha256(json.dumps(r.mensagens, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
            "resposta_do_modelo": r.texto,
            "resposta_final": final,
            "status_revisao": STATUS_REVISAO,
            "latencia_ms": round((time.perf_counter() - inicio) * 1000),
        })
        return resposta
