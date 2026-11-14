"""Acesso ao prontuário estruturado (SQLite). Só devolve a visão desidentificada:
nome, CPF e telefone nunca saem daqui."""

import sqlite3
from datetime import date

from hospital_assistant.config import DB_PATH, REFERENCIA


def _con():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def listar_ids() -> list[str]:
    with _con() as con:
        return [r["id"] for r in con.execute("SELECT id FROM pacientes ORDER BY id")]


def consultar_paciente(paciente_id: str) -> dict | None:
    with _con() as con:
        p = con.execute("SELECT id, nascimento, sexo FROM pacientes WHERE id=?", (paciente_id,)).fetchone()
        if not p:
            return None
        nasc = date.fromisoformat(p["nascimento"])
        idade = (REFERENCIA - nasc).days // 365
        alergias = [r["substancia"] for r in con.execute("SELECT substancia FROM alergias WHERE paciente_id=?", (paciente_id,))]
        meds = [r["nome"] for r in con.execute("SELECT nome FROM medicacoes WHERE paciente_id=?", (paciente_id,))]
        atend = con.execute(
            "SELECT data, queixa, protocolo FROM atendimentos WHERE paciente_id=? ORDER BY data DESC LIMIT 1", (paciente_id,)
        ).fetchone()
        exames = [
            dict(r)
            for r in con.execute(
                "SELECT exame, status, resultado, solicitado_em FROM exames WHERE paciente_id=? ORDER BY exame", (paciente_id,)
            )
        ]
    return {
        "id": p["id"],
        "idade": idade,
        "sexo": p["sexo"],
        "alergias": alergias,
        "medicacoes": meds,
        "atendimento": dict(atend) if atend else None,
        "exames": exames,
    }


def exames_pendentes(paciente: dict) -> list[str]:
    return [e["exame"] for e in paciente["exames"] if e["status"] == "pendente"]


def formatar_paciente(p: dict) -> str:
    a = p["atendimento"] or {}
    linhas = [
        f"Paciente {p['id']}, {p['idade']} anos, sexo {p['sexo']}.",
        f"Queixa atual: {a.get('queixa', 'não registrada')} (atendimento em {a.get('data', '?')}).",
        f"Alergias: {', '.join(p['alergias']) or 'nenhuma registrada'}.",
        f"Medicações em uso: {', '.join(p['medicacoes']) or 'nenhuma registrada'}.",
    ]
    for e in p["exames"]:
        estado = f"resultado {e['resultado']}" if e["resultado"] else "pendente"
        linhas.append(f"Exame {e['exame']}: {estado}.")
    return "\n".join(linhas)
