"""Gera a base sintética de prontuários (SQLite) e os modelos de documentos internos."""

import random
import sqlite3
from datetime import timedelta

from faker import Faker

from hospital_assistant.config import DB_PATH, REFERENCIA

SEED = 42

# (queixa, protocolo, exames que costumam ser pedidos)
CASOS = [
    ("febre, confusão e queda de pressão", "PROT-001", ["lactato", "hemocultura", "hemograma"]),
    ("dor no peito com sudorese", "PROT-002", ["ECG", "troponina", "hemograma"]),
    ("fraqueza no braço esquerdo e fala arrastada", "PROT-003", ["tomografia de crânio", "glicemia capilar", "ECG"]),
    ("tosse com febre e falta de ar", "PROT-004", ["radiografia de tórax", "hemograma", "proteína C reativa"]),
    ("sede intensa, náusea e respiração rápida", "PROT-005", ["gasometria", "glicemia", "potássio"]),
    ("dor de cabeça e pressão muito alta", "PROT-006", ["ECG", "creatinina", "urina tipo 1"]),
    ("inchaço nos lábios e falta de ar após alimento", "PROT-007", ["oximetria", "triptase"]),
    ("falta de ar súbita e dor ao respirar", "PROT-008", ["D-dímero", "angiotomografia de tórax", "troponina"]),
    ("inchaço nas pernas e falta de ar ao deitar", "PROT-009", ["BNP", "ECG", "radiografia de tórax"]),
    ("dor ao urinar e febre", "PROT-010", ["urina tipo 1", "urocultura", "hemograma"]),
]
ALERGIAS = ["penicilina", "dipirona", "sulfa", "látex", "iodo", "nenhuma conhecida"]
MEDICACOES = ["losartana", "metformina", "AAS", "sinvastatina", "furosemida", "omeprazol", "insulina NPH"]


def criar_base(caminho=DB_PATH, n_pacientes: int = 40) -> None:
    rnd = random.Random(SEED)
    fake = Faker("pt_BR")
    Faker.seed(SEED)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    if caminho.exists():
        caminho.unlink()
    con = sqlite3.connect(caminho)
    con.executescript(
        """
        CREATE TABLE pacientes (id TEXT PRIMARY KEY, nome TEXT, cpf TEXT, nascimento TEXT, sexo TEXT, telefone TEXT);
        CREATE TABLE alergias (paciente_id TEXT, substancia TEXT);
        CREATE TABLE medicacoes (paciente_id TEXT, nome TEXT);
        CREATE TABLE exames (paciente_id TEXT, exame TEXT, status TEXT, resultado TEXT, solicitado_em TEXT);
        CREATE TABLE atendimentos (paciente_id TEXT, data TEXT, queixa TEXT, protocolo TEXT);
        """
    )
    hoje = REFERENCIA
    for i in range(1, n_pacientes + 1):
        pid = f"P-{i:04d}"
        sexo = rnd.choice(["F", "M"])
        nome = fake.name_female() if sexo == "F" else fake.name_male()
        idade = rnd.randint(19, 88)
        nasc = hoje - timedelta(days=idade * 365 + rnd.randint(0, 364))
        con.execute(
            "INSERT INTO pacientes VALUES (?,?,?,?,?,?)",
            (pid, nome, fake.cpf(), nasc.isoformat(), sexo, fake.phone_number()),
        )
        for s in rnd.sample(ALERGIAS, k=rnd.choice([1, 1, 2])):
            con.execute("INSERT INTO alergias VALUES (?,?)", (pid, s))
        for m in rnd.sample(MEDICACOES, k=rnd.randint(0, 3)):
            con.execute("INSERT INTO medicacoes VALUES (?,?)", (pid, m))
        queixa, prot, exames = CASOS[(i - 1) % len(CASOS)]
        dia = hoje - timedelta(days=rnd.randint(0, 2))
        con.execute("INSERT INTO atendimentos VALUES (?,?,?,?)", (pid, dia.isoformat(), queixa, prot))
        for e in exames:
            pendente = rnd.random() < 0.5
            con.execute(
                "INSERT INTO exames VALUES (?,?,?,?,?)",
                (pid, e, "pendente" if pendente else "resultado", None if pendente else "alterado" if rnd.random() < 0.4 else "sem alterações", dia.isoformat()),
            )
    con.commit()
    con.close()


# Modelos internos (com identificadores FICTÍCIOS de propósito, para exercitar a anonimização).
DOCUMENTOS_BRUTOS = [
    {
        "id": "MOD-LAUDO-ECG",
        "tipo": "laudo",
        "titulo": "Laudo de eletrocardiograma",
        "texto": "Paciente: Maria da Silva Souza, CPF 123.456.789-09, nascida em 12/03/1958, prontuário 784512. "
        "Eletrocardiograma de 12 derivações. Ritmo: {ritmo}. Frequência cardíaca: {fc} bpm. Eixo: {eixo}. "
        "Intervalos: {intervalos}. Alterações de ST-T: {st}. Conclusão: {conclusao}. Contato: (81) 98765-4321.",
    },
    {
        "id": "MOD-LAUDO-RX",
        "tipo": "laudo",
        "titulo": "Laudo de radiografia de tórax",
        "texto": "Paciente: João Pereira Lima, CPF 987.654.321-00, nascido em 04/11/1971. Radiografia de tórax em PA e perfil. "
        "Parênquima: {parenquima}. Silhueta cardíaca: {cardiaca}. Seios costofrênicos: {seios}. Conclusão: {conclusao}.",
    },
    {
        "id": "MOD-RECEITA",
        "tipo": "receita",
        "titulo": "Receituário interno",
        "texto": "Paciente: Ana Beatriz Costa, CPF 111.222.333-44. Medicamento: {medicamento}. Posologia: {posologia}. "
        "Duração: {duracao}. Médico responsável: {medico}, CRM {crm}. Assinatura e carimbo obrigatórios.",
    },
    {
        "id": "MOD-PROC-ACESSO",
        "tipo": "procedimento",
        "titulo": "Registro de acesso venoso periférico",
        "texto": "Paciente: Carlos Eduardo Alves, prontuário 551230. Procedimento: acesso venoso periférico. Local: {local}. "
        "Calibre: {calibre}. Intercorrências: {intercorrencias}. Profissional: {profissional}, COREN {coren}. Data: 10/11/2026.",
    },
    {
        "id": "MOD-PROC-SONDA",
        "tipo": "procedimento",
        "titulo": "Registro de sondagem vesical",
        "texto": "Paciente: Fernanda Rocha, e-mail fernanda.rocha@exemplo.com. Procedimento: sondagem vesical de demora. Indicação: {indicacao}. "
        "Técnica: assepsia e material estéril. Calibre: {calibre}. Intercorrências: {intercorrencias}. Profissional: {profissional}.",
    },
]
