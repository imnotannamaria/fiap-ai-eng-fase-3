import pytest

from hospital_assistant.assistant import prontuario
from hospital_assistant.data.synthetic import criar_base


@pytest.fixture
def base(tmp_path, monkeypatch):
    caminho = tmp_path / "teste.db"
    criar_base(caminho, n_pacientes=12)
    monkeypatch.setattr(prontuario, "DB_PATH", caminho)
    return caminho


def test_visao_nao_expoe_identificadores(base):
    paciente = prontuario.consultar_paciente("P-0001")
    assert set(paciente) == {"id", "idade", "sexo", "alergias", "medicacoes", "atendimento", "exames"}
    texto = prontuario.formatar_paciente(paciente)
    assert "CPF" not in texto and "@" not in texto


def test_paciente_inexistente(base):
    assert prontuario.consultar_paciente("P-9999") is None


def test_exames_pendentes_batem_com_o_status(base):
    paciente = prontuario.consultar_paciente("P-0003")
    esperado = [e["exame"] for e in paciente["exames"] if e["status"] == "pendente"]
    assert prontuario.exames_pendentes(paciente) == esperado


def test_base_e_reproduzivel(tmp_path):
    a, b = tmp_path / "a.db", tmp_path / "b.db"
    criar_base(a, n_pacientes=5)
    criar_base(b, n_pacientes=5)
    assert a.read_bytes() == b.read_bytes()
