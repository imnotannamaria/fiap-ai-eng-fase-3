import json
import random
import re

import pytest

from hospital_assistant.config import PROCESSED
from hospital_assistant.data.anonymize import tem_identificador
from hospital_assistant.data.build_dataset import FECHO_RECUSA, FONTE, PADRAO_DOSE, conflito, curar, dividir, ex

TIPOS = {"protocolo", "paciente", "recusa", "sem_fonte", "documento"}


def _ler(nome):
    with open(PROCESSED / f"{nome}.jsonl", encoding="utf-8") as f:
        dados = [json.loads(l) for l in f]
    with open(PROCESSED / f"{nome}_meta.jsonl", encoding="utf-8") as f:
        meta = [json.loads(l) for l in f]
    return dados, meta


@pytest.mark.parametrize("nome", ["train", "valid", "test"])
def test_arquivos_sem_identificador_nem_dose(nome):
    dados, _ = _ler(nome)
    for linha in dados:
        for msg in linha["messages"][1:]:
            assert not tem_identificador(msg["content"])
        assert not PADRAO_DOSE.search(linha["messages"][2]["content"])


@pytest.mark.parametrize("nome", ["valid", "test"])
def test_todo_tipo_aparece_em_valid_e_test(nome):
    _, meta = _ler(nome)
    assert {m["tipo"] for m in meta} == TIPOS


def test_sem_vazamento_entre_conjuntos():
    grupos = {n: {m["grupo"] for m in _ler(n)[1]} for n in ("train", "valid", "test")}
    assert not grupos["train"] & grupos["valid"]
    assert not grupos["train"] & grupos["test"]
    assert not grupos["valid"] & grupos["test"]


def test_recusa_nao_prescreve_e_documento_nao_inventa_achado():
    for nome in ("train", "valid", "test"):
        dados, meta = _ler(nome)
        for linha, m in zip(dados, meta):
            resp = linha["messages"][2]["content"]
            if m["tipo"] == "recusa":
                assert "Não posso prescrever" in resp
            if m["tipo"] == "documento":
                assert "campos em branco" in resp
                assert "sinusal" not in resp and "sem alterações" not in resp


def test_resposta_com_fonte_cita_id_valido():
    dados, meta = _ler("train")
    for linha, m in zip(dados, meta):
        if m["tipo"] in ("protocolo", "paciente", "documento"):
            assert FONTE.search(linha["messages"][2]["content"])


def test_curar_descarta_duplicado_dose_e_identificador():
    bom = ex("protocolo", "pergunta 1", ["t"], "Resposta com fonte [PROT-001] e texto suficiente para passar no tamanho.")
    duplicado = ex("protocolo", "pergunta 1", ["t"], "Outra resposta com fonte [PROT-001] e texto suficiente para passar.")
    com_dose = ex("protocolo", "pergunta 2", ["t"], "Tomar 500 mg a cada 8 horas conforme o protocolo [PROT-001] segundo o médico.")
    com_cpf = ex("protocolo", "pergunta 3", ["t"], "Paciente de CPF 123.456.789-09 segue o protocolo [PROT-001] segundo o texto dado.")
    sem_fonte = ex("protocolo", "pergunta 4", ["t"], "Resposta sem nenhuma citação de fonte, mas com tamanho suficiente pra passar.")
    bons, descartes = curar([bom, duplicado, com_dose, com_cpf, sem_fonte])
    assert len(bons) == 1
    assert descartes == {"duplicado": 1, "contem_dose": 1, "identificador_residual": 1, "sem_fonte_citada": 1}


def test_dividir_e_deterministico():
    bom = [ex("recusa", f"p{i}", ["t"], "x" * 50, grupo=f"g{i}") for i in range(24)]
    a = dividir(list(bom), random.Random(1))
    b = dividir(list(bom), random.Random(1))
    assert [[e["grupo"] for e in conj] for conj in a] == [[e["grupo"] for e in conj] for conj in b]


def _todos():
    for nome in ("train", "valid", "test"):
        dados, meta = _ler(nome)
        for linha, m in zip(dados, meta):
            yield linha["messages"][1]["content"], linha["messages"][2]["content"], m


def test_recusa_termina_sempre_igual_pro_modelo_aprender_a_parar():
    for _, resp, m in _todos():
        if m["tipo"] == "recusa":
            assert resp.endswith(FECHO_RECUSA)


def test_recusa_generica_nao_anexa_protocolo():
    vistos = 0
    for _, resp, m in _todos():
        if m["sub"].startswith("generica"):
            vistos += 1
            assert "[PROT-" not in resp
    assert vistos


def test_recusa_so_cita_protocolo_que_estava_no_contexto():
    for user, resp, m in _todos():
        if m["tipo"] == "recusa":
            for cod in set(re.findall(r"\[(PROT-\d+)\]", resp)):
                assert f"({cod} |" in user


def test_recusa_com_paciente_avisa_alergia_em_conflito():
    avisos = 0
    for user, resp, m in _todos():
        if m["sub"].startswith("paciente_"):
            assert "alergia" in resp.lower()
            avisos += "Atenção" in resp
    assert avisos > 0


def test_sem_prontuario_no_contexto_o_modelo_diz_que_nao_recebeu():
    for user, resp, m in _todos():
        if m["sub"] == "sem_paciente":
            assert "[PACIENTE]" not in user
            assert "Não recebi" in resp


def test_conflito_de_alergia():
    assert conflito(["penicilina"], "amoxicilina") == "penicilina"
    assert conflito(["penicilina"], "dipirona") is None
    assert conflito(["nenhuma conhecida"], "amoxicilina") is None
