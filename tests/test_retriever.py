import json
import re

import pytest

from hospital_assistant.assistant.retriever import ProtocoloRetriever, escolher_campo
from hospital_assistant.data.build_dataset import PERGUNTAS_FORA, TEMAS_FORA
from hospital_assistant.data.protocols import CAMPOS
from hospital_assistant.config import PROCESSED

# Perguntas escritas à mão, fora dos moldes do dataset. As 13 primeiras foram usadas pra ajustar
# o retriever. As 13 últimas foram escritas antes do último ajuste: 12 de 13 acertaram na hora
# (a que errou foi "chamo", e virou regra).
NOVAS = [
    ("Tenho um paciente com sepse, quais exames eu peço?", "PROT-001", "exames"),
    ("Dor no peito com suor frio, o que faço primeiro?", "PROT-002", "conduta"),
    ("Quando o AVC vira caso de chamar o plantonista?", "PROT-003", "alertas"),
    ("Como eu sei se é pneumonia mesmo?", "PROT-004", "criterios"),
    ("A cetoacidose tem algum cuidado antes de começar insulina?", "PROT-005", "atencao"),
    ("Qual a diferença entre urgência e emergência hipertensiva, o hospital define como?", "PROT-006", "definicao"),
    ("Anafilaxia: qual o primeiro passo?", "PROT-007", "conduta"),
    ("Suspeita de embolia pulmonar, que exames eu peço?", "PROT-008", "exames"),
    ("Paciente com IC descompensada, quais sinais de piora?", "PROT-009", "alertas"),
    ("Que cuidado tenho que ter numa ITU antes de definir o antibiótico?", "PROT-010", "atencao"),
    ("Qual a conduta pra fratura de fêmur?", None, None),
    ("Como funciona a triagem de Manchester?", None, None),
    ("Qual o protocolo de dengue?", None, None),
    ("Paciente com suspeita de AVC chegou agora, que exames eu já peço?", "PROT-003", "exames"),
    ("Como confirmo que é uma crise hipertensiva?", "PROT-006", "criterios"),
    ("Qual o primeiro passo no atendimento da sepse?", "PROT-001", "conduta"),
    ("Em caso de pneumonia, quando eu chamo o médico responsável?", "PROT-004", "alertas"),
    ("Que cuidado antes de tratar anafilaxia?", "PROT-007", "atencao"),
    ("Me explica o que é embolia pulmonar.", "PROT-008", "definicao"),
    ("O que pedir de exame numa infecção urinária?", "PROT-010", "exames"),
    ("Insuficiência cardíaca: como começo o atendimento?", "PROT-009", "conduta"),
    ("Sinais de gravidade na cetoacidose?", "PROT-005", "alertas"),
    ("Qual a conduta para picada de cobra?", None, None),
    ("Quais as regras de visita no pronto-socorro?", None, None),
    ("O que fazer em caso de overdose?", None, None),
    ("Como é o protocolo de pré-natal?", None, None),
]


@pytest.fixture(scope="module")
def retriever():
    return ProtocoloRetriever()


def _achado(docs):
    return (docs[0].metadata["fonte"], docs[0].metadata["campo"]) if docs else (None, None)


@pytest.mark.parametrize("pergunta,protocolo,campo", NOVAS)
def test_perguntas_novas(retriever, pergunta, protocolo, campo):
    assert _achado(retriever.recuperar(pergunta)) == (protocolo, campo)


def test_perguntas_do_dataset_acham_protocolo_e_campo(retriever):
    total = erros = 0
    for nome in ("train", "valid", "test"):
        with open(PROCESSED / f"{nome}.jsonl", encoding="utf-8") as f:
            for linha in f:
                m = json.loads(linha)["messages"]
                user = m[1]["content"]
                achados = re.findall(r"^\((PROT-\d+) \| [^|]+\| ([^)]+)\)", user, re.M)
                if "[PACIENTE]" in user or len(achados) != 1 or not m[2]["content"].startswith("Segundo o protocolo"):
                    continue
                campo = next(k for k, v in CAMPOS.items() if v == achados[0][1])
                total += 1
                erros += _achado(retriever.recuperar(user.split("Pergunta:")[1].strip())) != (achados[0][0], campo)
    assert total > 150
    assert erros == 0


def test_temas_fora_do_dataset_nao_recuperam_nada(retriever):
    for tema in TEMAS_FORA:
        for modelo in PERGUNTAS_FORA:
            assert retriever.recuperar(modelo.format(t=tema)) == []


def test_pergunta_sem_tema_usa_o_protocolo_do_paciente(retriever):
    docs = retriever.recuperar("Quais sinais de alerta devo observar neste paciente?", "PROT-008")
    assert _achado(docs) == ("PROT-008", "alertas")


def test_pergunta_sobre_outra_doenca_vence_o_bonus_do_paciente(retriever):
    docs = retriever.recuperar("E se fosse sepse, qual a conduta inicial?", "PROT-008")
    assert _achado(docs) == ("PROT-001", "conduta")


def test_palavra_dentro_de_outra_nao_dispara_regra():
    # "cetoacidose" tem "dose" dentro. Não é pedido de prescrição.
    assert escolher_campo("A cetoacidose tem algum cuidado antes de começar?") == "atencao"


def test_titulo_do_protocolo_nao_conta_pra_escolher_o_campo():
    titulo = "Dor torácica e suspeita de síndrome coronariana aguda"
    assert escolher_campo(f"Qual a conduta inicial em {titulo.lower()}?", titulo) == "conduta"


def test_documento_traz_fonte_campo_e_nota(retriever):
    doc = retriever.recuperar("Qual a conduta inicial na sepse?")[0]
    assert doc.page_content.startswith("(PROT-001 | Sepse no adulto | conduta inicial)")
    assert set(doc.metadata) == {"fonte", "protocolo", "campo", "nota"}
