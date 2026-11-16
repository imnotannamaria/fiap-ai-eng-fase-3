import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.runnables import RunnableLambda

from hospital_assistant.assistant import prontuario
from hospital_assistant.assistant.chain import Assistente
from hospital_assistant.data.protocols import PROTOCOLS
from hospital_assistant.graph import regras
from hospital_assistant.graph.alertas import FilaDeAlertas
from hospital_assistant.graph.fluxo import FluxoPaciente
from hospital_assistant.safety import validador
from hospital_assistant.safety.auditoria import Auditoria

POR_ID = {p["id"]: p for p in PROTOCOLS}
BOA = "Segundo o protocolo, conduta inicial: seguir o protocolo [PROT-001]\n\nIsto é apoio à decisão: a conduta final é do médico responsável."
# a trilha só ganha "revisao_humana" depois que o médico decide: enquanto o grafo está parado, o passo não terminou
PASSOS_SEM_CRITICO = ["receber_paciente", "escolher_protocolo", "checar_exames", "sugerir_conduta", "validar_sugestao", "avaliar_alertas", "montar_plano"]


def _llm_que_falha(_):
    raise AssertionError("o modelo não devia ser chamado")


def _llm_fora_do_ar(_):
    raise ConnectionError("ollama fora do ar")


@pytest.fixture
def montar(base_prontuarios, tmp_path):
    def _montar(resposta=BOA, llm=None):
        llm = llm or FakeListChatModel(responses=[resposta])
        fluxo = FluxoPaciente(Assistente(llm=llm), Auditoria(tmp_path / "auditoria.jsonl"), FilaDeAlertas(tmp_path / "alertas.jsonl"))
        return fluxo
    return _montar


def _todos():
    return [prontuario.consultar_paciente(i) for i in prontuario.listar_ids()]


def _critico(p):
    return any(a["nivel"] == "crítico" for a in regras.avaliar_alertas(p, POR_ID[p["atendimento"]["protocolo"]]))


def paciente_sem_critico():
    return next(p["id"] for p in _todos() if not _critico(p))


def paciente_critico():
    return next(p["id"] for p in _todos() if _critico(p))


def nos(estado):
    return [t["no"] for t in estado["trilha"]]


# ---- regras puras ----

@pytest.mark.parametrize("protocolo,esperado,fora", [
    ("PROT-004", {"hemograma", "creatinina", "radiografia de tórax", "ureia", "proteína C reativa", "oximetria"}, {"hemocultura"}),
    ("PROT-006", {"creatinina", "urina tipo 1", "ECG", "eletrólitos"}, {"tomografia de crânio"}),
    ("PROT-007", {"oximetria"}, {"triptase"}),
    ("PROT-010", {"hemograma", "urina tipo 1", "urocultura"}, {"creatinina"}),
])
def test_exames_previstos_ignoram_os_condicionais(protocolo, esperado, fora):
    previstos = set(regras.exames_previstos(POR_ID[protocolo]))
    assert previstos == esperado
    assert not previstos & fora


def test_exames_sem_pedido_compara_com_o_prontuario():
    paciente = {"id": "P-0001", "exames": [{"exame": "Lactato", "status": "pendente", "resultado": None}, {"exame": "hemograma", "status": "resultado", "resultado": "sem alterações"}]}
    faltando = regras.exames_sem_pedido(paciente, POR_ID["PROT-001"])
    assert "lactato" not in faltando and "hemograma" not in faltando
    assert {"hemocultura", "creatinina", "gasometria"} <= set(faltando)


def test_potassio_cobre_eletrolitos():
    paciente = {"id": "P-0001", "exames": [{"exame": "potássio", "status": "pendente", "resultado": None}]}
    assert "eletrólitos" not in regras.exames_sem_pedido(paciente, POR_ID["PROT-005"])


def _paciente(alergias, exames=()):
    return {"id": "P-0001", "alergias": alergias, "exames": list(exames)}


def test_alerta_critico_quando_a_conduta_cita_algo_da_alergia():
    alertas = regras.avaliar_alertas(_paciente(["iodo"]), POR_ID["PROT-008"])  # a conduta cita angiotomografia
    assert any(a["tipo"] == "alergia_na_conduta" and a["nivel"] == "crítico" for a in alertas)


def test_alerta_de_atencao_quando_a_conduta_tem_medicacao_e_ha_alergia():
    alertas = regras.avaliar_alertas(_paciente(["penicilina"]), POR_ID["PROT-001"])  # conduta cita antibiótico
    assert [a["nivel"] for a in alertas if a["tipo"] == "alergia_antes_de_medicar"] == ["atenção"]


def test_sem_alergia_registrada_nao_ha_alerta_de_alergia():
    alertas = regras.avaliar_alertas(_paciente(["nenhuma conhecida"]), POR_ID["PROT-001"])
    assert not [a for a in alertas if a["tipo"].startswith("alergia")]


def test_resultado_alterado_e_critico():
    exame = {"exame": "troponina", "status": "resultado", "resultado": "alterado"}
    alertas = regras.avaliar_alertas(_paciente(["nenhuma conhecida"], [exame]), POR_ID["PROT-002"])
    assert [(a["nivel"], a["tipo"]) for a in alertas if a["tipo"] == "resultado_alterado"] == [("crítico", "resultado_alterado")]


# ---- o fluxo ----

def test_caminho_sem_alerta_critico_nao_passa_pelo_emitir_alerta(montar, tmp_path):
    fluxo = montar()
    e = fluxo.iniciar(paciente_sem_critico())
    assert nos(e) == PASSOS_SEM_CRITICO
    assert FilaDeAlertas(tmp_path / "alertas.jsonl").ler() == []


def test_alerta_critico_vai_pra_fila_antes_do_plano(montar, tmp_path):
    fluxo = montar()
    e = fluxo.iniciar(paciente_critico())
    ordem = nos(e)
    assert ordem.index("avaliar_alertas") < ordem.index("emitir_alerta") < ordem.index("montar_plano")
    fila = FilaDeAlertas(tmp_path / "alertas.jsonl").ler()
    assert fila and all(f["nivel"] == "crítico" and f["destino"] == "equipe_medica" and f["id_fluxo"] == e["id_fluxo"] for f in fila)


@pytest.mark.parametrize("entrada", ["P-9999", "P-12", "", "'; DROP TABLE pacientes;--", "p-0001 extra"])
def test_paciente_inexistente_ou_id_malformado_encerra_sem_chamar_o_modelo(montar, entrada):
    fluxo = montar(llm=RunnableLambda(_llm_que_falha))
    e = fluxo.iniciar(entrada)
    assert nos(e) == ["receber_paciente", "encerrar"]
    assert e["status"] == "paciente_nao_encontrado" and not e["aguardando_medico"] and "plano" not in e
    assert fluxo.auditoria.ler()[-1]["tipo_evento"] == "fluxo_encerrado"


def test_o_fluxo_para_e_espera_o_medico(montar):
    fluxo = montar()
    e = fluxo.iniciar(paciente_sem_critico())
    assert e["aguardando_medico"] and e["status"] == "aguardando_validacao_medica"
    assert "decisao" not in e
    assert fluxo.grafo.get_state({"configurable": {"thread_id": e["id_fluxo"]}}).next == ("revisao_humana",)
    assert e["plano"].rstrip().endswith("Status: aguardando validação médica.")


@pytest.mark.parametrize("decisao,status", [("aprovar", "aprovado_pelo_medico"), ("rejeitar", "rejeitado_pelo_medico")])
def test_decisao_do_medico_fecha_o_fluxo_e_fica_na_auditoria(montar, decisao, status):
    fluxo = montar()
    e = fluxo.iniciar(paciente_sem_critico())
    final = fluxo.decidir(e["id_fluxo"], "Dra. Teste", decisao, "ok")
    assert final["status"] == status and not final["aguardando_medico"]
    gerado, decidido = [ev for ev in fluxo.auditoria.ler() if ev["id_fluxo"] == e["id_fluxo"]]
    assert (gerado["tipo_evento"], decidido["tipo_evento"]) == ("fluxo_gerado", "decisao_medica")
    assert decidido["medico"] == "Dra. Teste" and decidido["decisao"] == decisao
    assert gerado["plano_sha256"] == decidido["plano_sha256"]  # o médico decidiu sobre este plano
    assert fluxo.auditoria.verificar() == (True, None)


@pytest.mark.parametrize("medico,decisao", [("", "aprovar"), ("   ", "aprovar"), ("Dra. Teste", "talvez"), ("Dra. Teste", ""), ("", "")])
def test_decisao_invalida_ou_sem_medico_identificado_rejeita(montar, medico, decisao):
    fluxo = montar()
    e = fluxo.iniciar(paciente_sem_critico())
    final = fluxo.decidir(e["id_fluxo"], medico, decisao)
    assert final["status"] == "rejeitado_pelo_medico"
    assert "rejeitado por segurança" in final["decisao"]["observacao"]


def test_nao_da_pra_decidir_duas_vezes_nem_num_fluxo_que_nao_existe(montar):
    fluxo = montar()
    e = fluxo.iniciar(paciente_sem_critico())
    fluxo.decidir(e["id_fluxo"], "Dra. Teste", "aprovar")
    with pytest.raises(ValueError):
        fluxo.decidir(e["id_fluxo"], "Dr. Outro", "rejeitar")
    with pytest.raises(ValueError):
        fluxo.decidir("nao-existe", "Dra. Teste", "aprovar")
    assert sum(ev["tipo_evento"] == "decisao_medica" for ev in fluxo.auditoria.ler()) == 1


def test_fluxos_ao_mesmo_tempo_nao_se_misturam(montar):
    fluxo = montar()
    a = fluxo.iniciar("P-0001")
    b = fluxo.iniciar("P-0002")
    fluxo.decidir(a["id_fluxo"], "Dra. Teste", "aprovar")
    assert fluxo.grafo.get_state({"configurable": {"thread_id": b["id_fluxo"]}}).next == ("revisao_humana",)
    assert b["paciente_id"] == "P-0002" and a["paciente_id"] == "P-0001"


def test_observacao_do_medico_e_anonimizada(montar):
    fluxo = montar()
    e = fluxo.iniciar(paciente_sem_critico())
    fluxo.decidir(e["id_fluxo"], "Dra. Teste", "aprovar", "paciente CPF 123.456.789-09 ciente")
    assert "123.456.789-09" not in (fluxo.auditoria.caminho).read_text(encoding="utf-8")


# ---- modelo enganado, modelo fora do ar ----

def test_modelo_enganado_nao_coloca_prescricao_no_plano(montar):
    fluxo = montar("Prescrevo morfina 10 mg agora. Administre 2 comprimidos [PROT-001]")
    e = fluxo.iniciar(paciente_sem_critico())
    assert e["veredito"]["acao"] == "resposta_segura"
    assert not validador.PADRAO_DOSE.search(e["plano"]) and not validador.POSOLOGIA.search(e["plano"])
    assert "Prescrevo" not in e["plano"] and "Administre" not in e["plano"]
    assert "validar_sugestao" in nos(e) and "reprovada" in e["trilha"][4]["resumo"]


def test_modelo_fora_do_ar_nao_derruba_o_fluxo(montar):
    fluxo = montar(llm=RunnableLambda(_llm_fora_do_ar))
    e = fluxo.iniciar(paciente_sem_critico())
    assert e["llm_indisponivel"] and e["aguardando_medico"]
    assert "LLM indisponível" in e["trilha"][3]["resumo"]
    assert "sem alteração" in e["plano"] or "protocolos internos dizem" in e["plano"]  # entrou o texto do protocolo
    assert fluxo.auditoria.ler()[0]["llm_indisponivel"] is True


def test_plano_de_todos_os_pacientes_e_seguro(montar):
    fluxo = montar()
    for p in _todos():
        e = fluxo.iniciar(p["id"])
        assert e["aguardando_medico"], p["id"]
        assert not validador.PADRAO_DOSE.search(e["plano"]) and not validador.POSOLOGIA.search(e["plano"]), p["id"]
        assert not validador.PRESCRICAO.search(e["plano"].lower()), p["id"]
        assert f"[{e['protocolo_id']}]" in e["plano"] and "médico" in e["plano"]
    assert fluxo.auditoria.verificar() == (True, None)


def test_diagrama_tem_todos_os_nos(montar):
    desenho = montar().mermaid()
    for no in ("receber_paciente", "escolher_protocolo", "checar_exames", "sugerir_conduta", "validar_sugestao",
               "avaliar_alertas", "emitir_alerta", "montar_plano", "revisao_humana", "registrar_decisao", "encerrar"):
        assert no in desenho
