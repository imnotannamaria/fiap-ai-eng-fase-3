import json

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from hospital_assistant.assistant import prontuario
from hospital_assistant.assistant.chain import Assistente
from hospital_assistant.assistant.tools import buscar_protocolo, consultar_paciente, listar_exames_pendentes
from hospital_assistant.config import PROCESSED
from hospital_assistant.data.synthetic import criar_base


@pytest.fixture(scope="module")
def base(tmp_path_factory):
    caminho = tmp_path_factory.mktemp("db") / "prontuarios.db"
    criar_base(caminho)  # mesma semente do dataset, então os pacientes são os mesmos
    antigo = prontuario.DB_PATH
    prontuario.DB_PATH = caminho
    yield caminho
    prontuario.DB_PATH = antigo


@pytest.fixture
def assistente(base):
    return Assistente(llm=FakeListChatModel(responses=["resposta de teste [PROT-001]"]))


def test_prompt_igual_ao_do_treino_pra_todo_exemplo_com_paciente(assistente):
    """O modelo foi treinado com um formato de prompt. Se a chain montar outro, ele recebe
    uma coisa que nunca viu. Aqui a chain refaz o prompt de cada exemplo e compara."""
    comparados = 0
    for nome in ("train", "valid", "test"):
        with open(PROCESSED / f"{nome}.jsonl", encoding="utf-8") as f, open(PROCESSED / f"{nome}_meta.jsonl", encoding="utf-8") as g:
            for linha, meta in zip(f, g):
                meta = json.loads(meta)
                if not meta["pid"] or meta["tipo"] == "sem_fonte":
                    continue  # em sem_fonte o treino usa um trecho sorteado de propósito
                user = json.loads(linha)["messages"][1]["content"]
                ctx = assistente._contextualizar({"pergunta": user.split("Pergunta:")[1].strip(), "paciente_id": meta["pid"]})
                assert ctx["mensagens"][1]["content"] == user
                comparados += 1
    assert comparados == 240


def test_resposta_traz_texto_fontes_e_citacoes(assistente):
    r = assistente.perguntar("Quais exames estão pendentes e o que o protocolo orienta?", "P-0001")
    assert r.texto == "resposta de teste [PROT-001]"
    assert r.citadas == ["PROT-001"]
    assert {f["tipo"] for f in r.fontes} == {"protocolo", "prontuario"}
    assert r.paciente_id == "P-0001"


def test_fontes_viram_json_pro_log_de_auditoria(assistente):
    r = assistente.perguntar("Qual a conduta inicial na sepse?")
    assert json.loads(json.dumps(r.fontes)) == r.fontes


def test_acha_o_paciente_pelo_id_na_pergunta(assistente):
    r = assistente.perguntar("Quais exames estão pendentes do paciente P-0007?")
    assert r.paciente_id == "P-0007"
    assert "[PACIENTE]" in r.mensagens[1]["content"]


def test_paciente_inexistente_nao_ganha_bloco_de_paciente(assistente):
    # o treino ensina "não recebi os dados do prontuário" quando o bloco não vem
    r = assistente.perguntar("Quais exames estão pendentes do paciente P-9999?")
    assert "[PACIENTE]" not in r.mensagens[1]["content"]
    assert all(f["tipo"] != "prontuario" for f in r.fontes)


def test_sem_protocolo_relevante_o_contexto_vai_vazio(assistente):
    r = assistente.perguntar("Qual a conduta para queimaduras de terceiro grau?")
    assert r.fontes == []
    assert "(nenhum trecho relevante encontrado)" in r.mensagens[1]["content"]


def test_prompt_tem_a_regra_de_nao_prescrever(assistente):
    r = assistente.perguntar("Qual a conduta inicial na sepse?")
    assert "nunca prescreve" in r.mensagens[0]["content"]


def test_ferramentas_so_devolvem_visao_desidentificada(base):
    resumo = consultar_paciente.invoke({"paciente_id": "P-0001"})
    assert resumo.startswith("Paciente P-0001,")
    assert "CPF" not in resumo
    assert consultar_paciente.invoke({"paciente_id": "P-9999"}) == "Paciente P-9999 não encontrado."
    assert isinstance(listar_exames_pendentes.invoke({"paciente_id": "P-0001"}), str)
    assert "PROT-001" in buscar_protocolo.invoke({"pergunta": "Qual a conduta inicial na sepse?"})
