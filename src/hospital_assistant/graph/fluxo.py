"""Fluxo automatizado do paciente, em LangGraph.

    receber paciente -> escolher protocolo -> checar exames -> sugerir conduta (LLM)
    -> validar -> avaliar alertas -> [emitir alerta] -> montar plano -> REVISÃO DO MÉDICO -> registrar

O grafo para em `revisao_humana` e só continua quando o médico decide. Sem decisão, o plano
fica "aguardando validação médica" e nunca é tratado como final. O que é alerta é decidido
por regra (`regras.py`). O modelo só redige a sugestão, e a sugestão passa pela mesma
validação de segurança do assistente.
"""

import hashlib
import operator
import re
import uuid
from datetime import datetime, timezone
from typing import Annotated, Callable, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from hospital_assistant.assistant import prontuario
from hospital_assistant.assistant.chain import Assistente
from hospital_assistant.assistant.retriever import ProtocoloRetriever
from hospital_assistant.data.anonymize import anonimizar
from hospital_assistant.data.protocols import PROTOCOLS
from hospital_assistant.graph import regras
from hospital_assistant.graph.alertas import FilaDeAlertas
from hospital_assistant.safety.auditoria import Auditoria
from hospital_assistant.safety.seguro import aplicar_seguranca

PERGUNTA_PADRAO = "Quais exames estão pendentes e o que o protocolo orienta?"
ID_PACIENTE = re.compile(r"^P-\d{4}$")
DECISOES = {"aprovar": "aprovado_pelo_medico", "rejeitar": "rejeitado_pelo_medico"}
POR_ID = {p["id"]: p for p in PROTOCOLS}


class Estado(TypedDict, total=False):
    id_fluxo: str
    paciente_id: str
    pergunta: str
    paciente: dict
    protocolo_id: str
    fontes: list[dict]
    trechos: list[str]
    exames_pendentes: list[str]
    exames_alterados: list[str]
    exames_sem_pedido: list[str]
    sugestao: str
    llm_indisponivel: bool
    corpo_sugestao: str
    veredito: dict
    alertas: list[dict]
    plano: str
    decisao: dict
    status: str
    trilha: Annotated[list[dict], operator.add]


def _passo(no: str, resumo: str) -> dict:
    return {"trilha": [{"no": no, "quando": datetime.now(timezone.utc).isoformat(), "resumo": resumo}]}


def _sha(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


class FluxoPaciente:
    def __init__(self, assistente=None, auditoria=None, fila=None, retriever=None, checkpointer=None):
        self.assistente = assistente or Assistente()
        self.auditoria = auditoria or Auditoria()
        self.fila = fila or FilaDeAlertas()
        self.retriever = retriever or self.assistente.retriever or ProtocoloRetriever()
        self.grafo = self._montar().compile(checkpointer=checkpointer or MemorySaver())

    # ---------- nós ----------

    def receber_paciente(self, e: Estado) -> dict:
        pid = (e.get("paciente_id") or "").strip().upper()
        paciente = prontuario.consultar_paciente(pid) if ID_PACIENTE.match(pid) else None
        if not paciente:
            return {"paciente_id": pid, "status": "paciente_nao_encontrado", **_passo("receber_paciente", f"paciente {pid or '(vazio)'} não encontrado")}
        a = paciente["atendimento"] or {}
        return {"paciente_id": pid, "paciente": paciente, "status": "em_andamento",
                **_passo("receber_paciente", f"{pid}: {paciente['idade']} anos, queixa de {a.get('queixa', 'não registrada')}")}

    def escolher_protocolo(self, e: Estado) -> dict:
        paciente = e["paciente"]
        a = paciente["atendimento"] or {}
        protocolo_id = a.get("protocolo")
        if not protocolo_id:  # sem protocolo no atendimento: tenta pela queixa
            docs = self.retriever.recuperar(a.get("queixa", ""))
            protocolo_id = docs[0].metadata["fonte"] if docs else None
        if protocolo_id not in POR_ID:
            return {"status": "sem_protocolo", **_passo("escolher_protocolo", "nenhum protocolo aplicável")}
        docs = self.retriever.recuperar("Qual a conduta inicial?", protocolo_id)
        fontes = [{"tipo": "protocolo", "id": d.metadata["fonte"], "campo": d.metadata["campo"], "nota": d.metadata["nota"]} for d in docs]
        fontes.append({"tipo": "prontuario", "id": paciente["id"]})
        return {"protocolo_id": protocolo_id, "fontes": fontes, "trechos": [d.page_content for d in docs],
                **_passo("escolher_protocolo", f"{protocolo_id} ({POR_ID[protocolo_id]['titulo']})")}

    def checar_exames(self, e: Estado) -> dict:
        paciente, protocolo = e["paciente"], POR_ID[e["protocolo_id"]]
        pendentes = [x["exame"] for x in paciente["exames"] if x["status"] == "pendente"]
        alterados, faltando = regras.exames_alterados(paciente), regras.exames_sem_pedido(paciente, protocolo)
        return {"exames_pendentes": pendentes, "exames_alterados": alterados, "exames_sem_pedido": faltando,
                **_passo("checar_exames", f"{len(pendentes)} pendente(s), {len(alterados)} alterado(s), {len(faltando)} previsto(s) sem pedido")}

    def sugerir_conduta(self, e: Estado) -> dict:
        pergunta = e.get("pergunta") or PERGUNTA_PADRAO
        try:
            r = self.assistente.perguntar(pergunta, e["paciente_id"])
            return {"sugestao": r.texto, "fontes": r.fontes, "trechos": r.trechos or e["trechos"], "llm_indisponivel": False,
                    **_passo("sugerir_conduta", f"LLM respondeu ({len(r.texto)} caracteres)")}
        except Exception as erro:  # Ollama fora do ar, modelo ausente, timeout...
            return {"sugestao": "", "llm_indisponivel": True,
                    **_passo("sugerir_conduta", f"LLM indisponível ({type(erro).__name__}), segue com o texto do protocolo")}

    def validar_sugestao(self, e: Estado) -> dict:
        v = aplicar_seguranca(e.get("pergunta") or PERGUNTA_PADRAO, e["sugestao"], e["trechos"], e["fontes"], e["paciente"])
        resumo = "aprovada" if v.validacao.ok else f"reprovada ({', '.join(v.validacao.motivos)}), trocada pelo protocolo"
        return {"corpo_sugestao": v.corpo, "veredito": {"acao": v.acao, "validacao": v.validacao.dict(), "alertas": [a.dict() for a in v.alertas]},
                **_passo("validar_sugestao", resumo)}

    def avaliar_alertas(self, e: Estado) -> dict:
        alertas = regras.avaliar_alertas(e["paciente"], POR_ID[e["protocolo_id"]])
        ja_tem = {a["texto"] for a in alertas}
        for a in e["veredito"]["alertas"]:  # alergia achada na sugestão do modelo
            texto = (f"ALERTA DE ALERGIA: o prontuário do paciente {a['paciente_id']} registra alergia a {a['alergia']}, e {a['termo']} tem relação direta com essa alergia [PRONTUARIO {a['paciente_id']}]."
                     if a["tipo"] == "direta" else
                     f"ATENÇÃO: o prontuário do paciente {a['paciente_id']} registra alergia a {a['alergia']}, e {a['termo']} pode ter reação cruzada com ela. Confirmar com o médico responsável [PRONTUARIO {a['paciente_id']}].")
            if texto not in ja_tem:
                alertas.append({"nivel": "crítico" if a["tipo"] == "direta" else "atenção", "tipo": "alergia_na_sugestao",
                                "fonte": f"PRONTUARIO {a['paciente_id']}", "texto": texto})
        contagem = {n: sum(a["nivel"] == n for a in alertas) for n in ("crítico", "atenção", "informativo")}
        return {"alertas": alertas, **_passo("avaliar_alertas", f"{contagem['crítico']} crítico(s), {contagem['atenção']} atenção, {contagem['informativo']} informativo(s)")}

    def emitir_alerta(self, e: Estado) -> dict:
        criticos = [a for a in e["alertas"] if a["nivel"] == "crítico"]
        for a in criticos:
            self.fila.emitir(e["id_fluxo"], e["paciente_id"], a)
        return _passo("emitir_alerta", f"{len(criticos)} alerta(s) crítico(s) enviado(s) à equipe médica")

    def montar_plano(self, e: Estado) -> dict:
        p, prot = e["paciente"], POR_ID[e["protocolo_id"]]
        a = p["atendimento"]
        marca = {"crítico": "CRÍTICO", "atenção": "ATENÇÃO", "informativo": "INFO"}
        com_resultado = [f"{x['exame']} ({x['resultado']})" for x in p["exames"] if x["resultado"]]
        linhas = [
            "PLANO PARA REVISÃO MÉDICA (rascunho: nada aqui é prescrição)",
            "",
            f"Paciente {p['id']}, {p['idade']} anos, sexo {p['sexo']}. Queixa: {a['queixa']} (atendimento em {a['data']}) [PRONTUARIO {p['id']}]",
            f"Protocolo aplicado: {prot['titulo']} [{prot['id']}]",
            "",
            "Alertas:",
            *([f"- [{marca[x['nivel']]}] {x['texto']}" for x in e["alertas"]] or ["- nenhum"]),
            "",
            "Exames:",
            f"- Com resultado: {', '.join(com_resultado) or 'nenhum'}",
            f"- Pendentes: {', '.join(e['exames_pendentes']) or 'nenhum'}",
            "",
            "Sugestão (passou pelas regras de segurança):",
            e["corpo_sugestao"],
            "",
            "Status: aguardando validação médica.",
        ]
        plano = "\n".join(linhas)
        self.auditoria.registrar({
            "tipo_evento": "fluxo_gerado", "id_fluxo": e["id_fluxo"], "quando": datetime.now(timezone.utc).isoformat(),
            "paciente_id": e["paciente_id"], "protocolo_id": e["protocolo_id"],
            "alertas": [{"nivel": x["nivel"], "tipo": x["tipo"]} for x in e["alertas"]],
            "sugestao_do_modelo": e["sugestao"], "llm_indisponivel": e.get("llm_indisponivel", False),
            "acao": e["veredito"]["acao"], "validacao": e["veredito"]["validacao"],
            "passos": [t["no"] for t in e["trilha"]], "plano_sha256": _sha(plano), "status": "aguardando validação médica",
        })
        return {"plano": plano, "status": "aguardando_validacao_medica", **_passo("montar_plano", "plano montado e registrado na auditoria")}

    def revisao_humana(self, e: Estado) -> dict:
        resposta = interrupt({"id_fluxo": e["id_fluxo"], "paciente_id": e["paciente_id"], "plano": e["plano"], "alertas": e["alertas"]})
        resposta = resposta if isinstance(resposta, dict) else {}
        medico = str(resposta.get("medico", "")).strip()
        decisao = str(resposta.get("decisao", "")).strip().lower()
        observacao = anonimizar(str(resposta.get("observacao", "")))
        if decisao not in DECISOES or not medico:
            # sem médico identificado ou decisão inválida: na dúvida, rejeita
            observacao = f"[decisão inválida ou médico não identificado, rejeitado por segurança] {observacao}".strip()
            decisao, medico = "rejeitar", medico or "(não identificado)"
        return {"decisao": {"decisao": decisao, "medico": medico, "observacao": observacao}, **_passo("revisao_humana", f"{medico} decidiu: {decisao}")}

    def registrar_decisao(self, e: Estado) -> dict:
        d = e["decisao"]
        status = DECISOES[d["decisao"]]
        self.auditoria.registrar({
            "tipo_evento": "decisao_medica", "id_fluxo": e["id_fluxo"], "quando": datetime.now(timezone.utc).isoformat(),
            "paciente_id": e["paciente_id"], "medico": d["medico"], "decisao": d["decisao"], "observacao": d["observacao"],
            "plano_sha256": _sha(e["plano"]), "status": status,
        })
        return {"status": status, **_passo("registrar_decisao", f"status final: {status}")}

    def encerrar(self, e: Estado) -> dict:
        self.auditoria.registrar({
            "tipo_evento": "fluxo_encerrado", "id_fluxo": e["id_fluxo"], "quando": datetime.now(timezone.utc).isoformat(),
            "paciente_id": e.get("paciente_id"), "motivo": e["status"],
        })
        return _passo("encerrar", f"fluxo encerrado: {e['status']}")

    # ---------- arestas ----------

    @staticmethod
    def _seguiu(e: Estado) -> str:
        return "fim" if e["status"] in ("paciente_nao_encontrado", "sem_protocolo") else "segue"

    @staticmethod
    def _tem_critico(e: Estado) -> str:
        return "emitir" if any(a["nivel"] == "crítico" for a in e["alertas"]) else "montar"

    def _montar(self) -> StateGraph:
        g = StateGraph(Estado)
        for nome in ("receber_paciente", "escolher_protocolo", "checar_exames", "sugerir_conduta", "validar_sugestao",
                     "avaliar_alertas", "emitir_alerta", "montar_plano", "revisao_humana", "registrar_decisao", "encerrar"):
            g.add_node(nome, getattr(self, nome))
        g.add_edge(START, "receber_paciente")
        g.add_conditional_edges("receber_paciente", self._seguiu, {"segue": "escolher_protocolo", "fim": "encerrar"})
        g.add_conditional_edges("escolher_protocolo", self._seguiu, {"segue": "checar_exames", "fim": "encerrar"})
        g.add_edge("checar_exames", "sugerir_conduta")
        g.add_edge("sugerir_conduta", "validar_sugestao")
        g.add_edge("validar_sugestao", "avaliar_alertas")
        g.add_conditional_edges("avaliar_alertas", self._tem_critico, {"emitir": "emitir_alerta", "montar": "montar_plano"})
        g.add_edge("emitir_alerta", "montar_plano")
        g.add_edge("montar_plano", "revisao_humana")
        g.add_edge("revisao_humana", "registrar_decisao")
        g.add_edge("registrar_decisao", END)
        g.add_edge("encerrar", END)
        return g

    # ---------- uso ----------

    def _rodar(self, entrada, config, ao_passar: Callable[[str, str], None] | None) -> dict:
        for bloco in self.grafo.stream(entrada, config, stream_mode="updates"):
            if not ao_passar:
                continue
            for no, atualizacao in bloco.items():
                if no == "__interrupt__":
                    ao_passar("revisao_humana", "aguardando a decisão do médico")
                elif isinstance(atualizacao, dict) and atualizacao.get("trilha"):
                    ao_passar(no, atualizacao["trilha"][-1]["resumo"])
        estado = self.grafo.get_state(config)
        return {**estado.values, "aguardando_medico": bool(estado.next)}

    def iniciar(self, paciente_id: str, pergunta: str | None = None, ao_passar: Callable[[str, str], None] | None = None) -> dict:
        id_fluxo = str(uuid.uuid4())
        entrada = {"id_fluxo": id_fluxo, "paciente_id": paciente_id, "status": "iniciado", "trilha": []}
        if pergunta:
            entrada["pergunta"] = pergunta
        return self._rodar(entrada, {"configurable": {"thread_id": id_fluxo}}, ao_passar)

    def decidir(self, id_fluxo: str, medico: str, decisao: str, observacao: str = "", ao_passar=None) -> dict:
        config = {"configurable": {"thread_id": id_fluxo}}
        if not self.grafo.get_state(config).next:
            raise ValueError(f"o fluxo {id_fluxo} não existe ou não está aguardando decisão")
        resposta = {"medico": medico, "decisao": decisao, "observacao": observacao}
        return self._rodar(Command(resume=resposta), config, ao_passar)

    def mermaid(self) -> str:
        return self.grafo.get_graph().draw_mermaid()
