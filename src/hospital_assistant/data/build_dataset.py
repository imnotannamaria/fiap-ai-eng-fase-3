"""Monta o dataset de instrução (JSONL de chat) a partir dos protocolos, prontuários
sintéticos e modelos de documentos. Passos: geração, anonimização, curadoria, split.

Uso: python -m hospital_assistant.data.build_dataset
"""

import json
import random
import re
from collections import Counter

from hospital_assistant.assistant import prontuario
from hospital_assistant.assistant.prompting import mensagens, trecho
from hospital_assistant.config import PROCESSED
from hospital_assistant.data.anonymize import anonimizar, tem_identificador
from hospital_assistant.data.protocols import CAMPOS, PERGUNTAS, PROTOCOLS
from hospital_assistant.data.synthetic import DOCUMENTOS_BRUTOS, criar_base

SEED = 7
FECHOS = [
    "Isto é apoio à decisão: a conduta final é do médico responsável.",
    "Lembrando que a decisão clínica e a prescrição são do médico responsável.",
    "Use como apoio. Quem decide e prescreve é o médico responsável.",
]
PADRAO_DOSE = re.compile(r"\b\d+([.,]\d+)?\s?(mg|mcg|ml|ui|g)\b", re.I)
FONTE = re.compile(r"\[(PROT-\d+|MOD-[\w-]+|PRONTUARIO P-\d+)\]")


def ex(tipo, pergunta, trechos, resposta, paciente=None, grupo=""):
    msgs = mensagens(pergunta, trechos, paciente)
    msgs.append({"role": "assistant", "content": resposta})
    return {"tipo": tipo, "grupo": grupo, "messages": msgs}


def exemplos_protocolo(rnd):
    out = []
    for p in PROTOCOLS:
        for campo in CAMPOS:
            for i, modelo in enumerate(PERGUNTAS[campo]):
                pergunta = modelo.format(t=p["titulo"].lower())
                trechos = [trecho(p, campo)]
                # metade dos exemplos leva um trecho distrator, para o modelo aprender a escolher a fonte certa
                if rnd.random() < 0.5:
                    outro = rnd.choice([q for q in PROTOCOLS if q["id"] != p["id"]])
                    trechos.append(trecho(outro, rnd.choice(list(CAMPOS))))
                    rnd.shuffle(trechos)
                resp = f"Segundo o protocolo de {p['titulo'].lower()}, {CAMPOS[campo]}: {p[campo]} [{p['id']}]\n\n{rnd.choice(FECHOS)}"
                out.append(ex("protocolo", pergunta, trechos, resp, grupo=f"{p['id']}|{campo}|{i}"))
    return out


def exemplos_paciente(rnd):
    out = []
    por_id = {p["id"]: p for p in PROTOCOLS}
    for pid in prontuario.listar_ids():
        pac = prontuario.consultar_paciente(pid)
        prot = por_id[pac["atendimento"]["protocolo"]]
        pend = prontuario.exames_pendentes(pac)
        txt = prontuario.formatar_paciente(pac)
        alerg = [a for a in pac["alergias"] if a != "nenhuma conhecida"]
        aviso_alergia = f" O paciente tem alergia registrada a {', '.join(alerg)}: conferir antes de qualquer medicação." if alerg else ""
        # 1) exames pendentes + conduta
        pend_txt = ", ".join(pend) if pend else "nenhum exame pendente"
        resp = (
            f"Exames pendentes do paciente {pid}: {pend_txt} [PRONTUARIO {pid}]. "
            f"Para a queixa registrada, o protocolo de {prot['titulo'].lower()} orienta: {prot['conduta']} [{prot['id']}]"
            f"{aviso_alergia}\n\n{rnd.choice(FECHOS)}"
        )
        q = rnd.choice(["Quais exames estão pendentes e o que o protocolo orienta?", "Verifique os exames pendentes e a conduta inicial.", "O que falta de exame e qual a conduta pelo protocolo?"])
        out.append(ex("paciente", q, [trecho(prot, "conduta")], resp, txt, grupo=pid))
        # 2) alertas
        resp2 = (
            f"Pelo protocolo de {prot['titulo'].lower()}, os sinais de alerta são: {prot['alertas']} [{prot['id']}]. "
            f"Dados do paciente {pid}: {pac['idade']} anos, queixa de {pac['atendimento']['queixa']} [PRONTUARIO {pid}]."
            f"{aviso_alergia}\n\n{rnd.choice(FECHOS)}"
        )
        out.append(ex("paciente", "Quais sinais de alerta devo observar neste paciente?", [trecho(prot, "alertas")], resp2, txt, grupo=pid))
    return out


def exemplos_recusa(rnd):
    pedidos = [
        "Qual dose de {d} devo prescrever para este paciente?",
        "Prescreva {d} para o paciente agora.",
        "Pode me dar a posologia de {d} e já deixar a receita pronta?",
        "Escreva a prescrição completa com {d}.",
    ]
    drogas = ["antibiótico", "insulina", "anticoagulante", "morfina", "diurético", "anti-hipertensivo", "corticoide"]
    out = []
    for d in drogas:
        for modelo in pedidos:
            prot = rnd.choice(PROTOCOLS)
            resp = (
                "Não posso prescrever nem definir doses. A escolha e a dosagem de medicamentos são do médico responsável, "
                f"depois de avaliar o paciente. Posso mostrar o que o protocolo de {prot['titulo'].lower()} diz sobre a conduta inicial: "
                f"{prot['conduta']} [{prot['id']}]\n\nA prescrição precisa ser validada e assinada pelo médico."
            )
            out.append(ex("recusa", modelo.format(d=d), [trecho(prot, "conduta")], resp, grupo=f"recusa|{d}|{modelo}"))
    return out


def exemplos_sem_fonte(rnd):
    temas = [
        "o protocolo de transplante de córnea", "a conduta para queimaduras de terceiro grau", "o protocolo de cirurgia bariátrica",
        "as regras de visita na UTI neonatal", "o protocolo de hemodiálise", "o fluxo de reabilitação ortopédica",
        "a conduta para intoxicação por metanol", "o protocolo de atendimento a gestantes de alto risco",
    ]
    modelos = ["Qual é {t}?", "Me explique {t}.", "O que o hospital orienta sobre {t}?"]
    out = []
    for t in temas:
        for m in modelos:
            prot = rnd.choice(PROTOCOLS)
            resp = (
                f"Não encontrei {t} nos protocolos internos fornecidos, então não vou responder de memória. "
                "Sugiro consultar o médico responsável ou o setor que mantém esse protocolo."
            )
            out.append(ex("sem_fonte", m.format(t=t), [trecho(prot, rnd.choice(list(CAMPOS)))], resp, grupo=f"sf|{t}|{m}"))
    return out


def exemplos_documentos(rnd, nomes):
    """Usa os modelos brutos, anonimizados, pra ensinar o formato dos documentos internos.

    Todo campo clínico fica em branco, como [RITMO] ou [MEDICAMENTO]. O rascunho nunca
    inventa achado de exame nem remédio: quem preenche é o médico."""
    out = []
    pedidos = ["Monte o rascunho do documento {t}.", "Preciso do modelo interno de {t}.", "Me dê o formato padrão de {t}."]
    for doc in DOCUMENTOS_BRUTOS:
        anon = anonimizar(doc["texto"], nomes)
        modelo = re.sub(r"\{(\w+)\}", lambda m: f"[{m.group(1).upper()}]", anon)
        extra = " Medicamento e posologia ficam em branco: só o médico define." if doc["tipo"] == "receita" else ""
        for pedido in pedidos:
            resp = (
                f"Rascunho com base no modelo interno [{doc['id']}]:\n\n{modelo}\n\n"
                f"Este é um rascunho com os campos em branco.{extra} O médico responsável precisa preencher, revisar e assinar antes de entrar no prontuário."
            )
            trechos = [f"({doc['id']} | {doc['titulo']} | modelo) {modelo}"]
            out.append(ex("documento", pedido.format(t=doc["titulo"].lower()), trechos, resp, grupo=f"{doc['id']}|{pedido}"))
    return out


def curar(exemplos):
    """Curadoria: dedupe, citação de fonte, sem dose, sem identificador, tamanho."""
    visto, bons, descartes = set(), [], Counter()
    for e in exemplos:
        user, resp = e["messages"][1]["content"], e["messages"][2]["content"]
        if user in visto:
            descartes["duplicado"] += 1
            continue
        if e["tipo"] in ("protocolo", "paciente", "documento") and not FONTE.search(resp):
            descartes["sem_fonte_citada"] += 1
            continue
        if PADRAO_DOSE.search(resp):
            descartes["contem_dose"] += 1
            continue
        if tem_identificador(user) or tem_identificador(resp):
            descartes["identificador_residual"] += 1
            continue
        if not 40 <= len(resp) <= 2500:
            descartes["tamanho"] += 1
            continue
        visto.add(user)
        bons.append(e)
    return bons, descartes


def dividir(exemplos, rnd):
    """Divide sem deixar o mesmo grupo em dois conjuntos.

    Protocolo: a terceira forma de cada pergunta nunca entra no treino.
    Os outros tipos são divididos por grupo (paciente, pedido de recusa, tema, documento),
    cada tipo separado, pra todo tipo ter exemplo em valid e test (cerca de 12% em cada)."""
    train, valid, test = [], [], []
    por_tipo = {}
    for e in exemplos:
        por_tipo.setdefault(e["tipo"], []).append(e)
    for tipo, lista in por_tipo.items():
        if tipo == "protocolo":
            for e in lista:
                if int(e["grupo"].split("|")[2]) != 2:
                    train.append(e)
                else:
                    ids = ("PROT-001", "PROT-003", "PROT-005", "PROT-007", "PROT-009")
                    (valid if e["grupo"].startswith(ids) else test).append(e)
            continue
        grupos = sorted({e["grupo"] for e in lista})
        rnd.shuffle(grupos)
        destino = {g: (valid if i % 8 == 0 else test if i % 8 == 4 else train) for i, g in enumerate(grupos)}
        for e in lista:
            destino[e["grupo"]].append(e)
    return train, valid, test


def salvar(nome, exemplos):
    PROCESSED.mkdir(parents=True, exist_ok=True)
    with open(PROCESSED / f"{nome}.jsonl", "w", encoding="utf-8") as f:
        for e in exemplos:
            f.write(json.dumps({"messages": e["messages"]}, ensure_ascii=False) + "\n")
    with open(PROCESSED / f"{nome}_meta.jsonl", "w", encoding="utf-8") as f:
        for e in exemplos:
            f.write(json.dumps({"tipo": e["tipo"], "grupo": e["grupo"]}, ensure_ascii=False) + "\n")


def main():
    rnd = random.Random(SEED)
    criar_base()
    nomes = ["Maria da Silva Souza", "João Pereira Lima", "Ana Beatriz Costa", "Carlos Eduardo Alves", "Fernanda Rocha"]
    bruto = (
        exemplos_protocolo(rnd) + exemplos_paciente(rnd) + exemplos_recusa(rnd)
        + exemplos_sem_fonte(rnd) + exemplos_documentos(rnd, nomes)
    )
    bons, descartes = curar(bruto)
    train, valid, test = dividir(bons, rnd)
    rnd.shuffle(train)
    for nome, dados in (("train", train), ("valid", valid), ("test", test)):
        salvar(nome, dados)
    relatorio = {
        "gerados": len(bruto), "mantidos": len(bons), "descartados": dict(descartes),
        "por_tipo": dict(Counter(e["tipo"] for e in bons)),
        "split": {"train": len(train), "valid": len(valid), "test": len(test)},
    }
    (PROCESSED / "curadoria_relatorio.json").write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(relatorio, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
