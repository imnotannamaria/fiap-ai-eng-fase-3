import pytest

from hospital_assistant.assistant import prontuario
from hospital_assistant.data.synthetic import criar_base


@pytest.fixture(scope="session")
def base_prontuarios(tmp_path_factory):
    """Base de prontuários sintéticos num diretório temporário (mesma semente do dataset)."""
    caminho = tmp_path_factory.mktemp("prontuarios") / "prontuarios.db"
    criar_base(caminho)
    antigo = prontuario.DB_PATH
    prontuario.DB_PATH = caminho
    yield caminho
    prontuario.DB_PATH = antigo
