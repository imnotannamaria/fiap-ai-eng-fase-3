from hospital_assistant.data.anonymize import anonimizar, tem_identificador


def test_troca_cpf_email_telefone_e_data():
    texto = "CPF 123.456.789-09, e-mail ana@exemplo.com, tel (81) 98765-4321, nascida em 12/03/1958."
    saida = anonimizar(texto)
    assert "[CPF]" in saida and "[EMAIL]" in saida and "[TELEFONE]" in saida and "[DATA]" in saida
    assert not tem_identificador(saida)


def test_troca_nome_ignorando_maiuscula():
    saida = anonimizar("Paciente: maria da silva souza, retorno.", ["Maria da Silva Souza"])
    assert saida == "Paciente: [NOME], retorno."


def test_troca_prontuario():
    assert "[PRONTUARIO]" in anonimizar("prontuário 784512")


def test_citacao_de_fonte_nao_vira_identificador():
    assert not tem_identificador("Exames pendentes [PRONTUARIO P-0007] e [PROT-001].")
