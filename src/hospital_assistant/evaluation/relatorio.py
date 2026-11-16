"""Calcula as métricas a partir das respostas guardadas e escreve evaluation/resultados.md,
evaluation/resultados.json e evaluation/erros.md.

    python -m hospital_assistant.evaluation.relatorio
"""

import json
from collections import defaultdict

from hospital_assistant.assistant import prontuario
from hospital_assistant.config import RAIZ
from hospital_assistant.evaluation.conjuntos import carregar
from hospital_assistant.evaluation.executar import SAIDA
from hospital_assistant.evaluation.geradores import SISTEMAS
from hospital_assistant.evaluation.metricas import agregar, f1_de_palavras, medir, medir_com_seguranca, wilson

NOMES = {
    "base": "base (4 bits)",
    "ajustado_mlx": "ajustado (4 bits)",
    "v2_ollama": "v2 implantado (fp16)",
    "v1_ollama": "v1 (fp16)",
}
CONJUNTOS = {"teste": "Teste do dataset", "fora_do_molde": "Fora do molde"}
# (tipo, métrica, rótulo). Tipo None = vale pra todas as respostas.
LINHAS = [
    ("protocolo", "cita_a_fonte_certa", "protocolo: cita só a fonte certa"),
    ("protocolo", "fiel_ao_trecho", "protocolo: repete o trecho sem alterar"),
    ("paciente", "cita_o_prontuario", "paciente: cita o prontuário"),
    ("paciente", "menciona_todos_os_pendentes", "paciente: menciona todos os exames pendentes (qualquer redação)"),
    ("paciente", "afirma_lista_no_formato", "paciente: afirma listas no formato que o parser confere"),
    ("paciente", "fiel_ao_prontuario", "paciente: das listas que afirma, as que batem com o prontuário"),
    ("recusa", "declinou", "recusa: declinou o pedido (qualquer frase)"),
    ("recusa", "recusou_no_formato", "recusa: recusou no formato do treino"),
    ("recusa", "avisou_a_alergia", "recusa: avisou da alergia (nos casos de conflito)"),
    ("sem_fonte", "disse_que_nao_tem", "sem fonte: disse que não tem (qualquer frase)"),
    ("sem_fonte", "disse_no_formato", "sem fonte: disse no formato do treino"),
    ("sem_fonte", "nao_citou_protocolo", "sem fonte: não citou protocolo"),
    (None, "sem_dose", "geral: sem dose nem posologia"),
    (None, "sem_prescricao", "geral: sem verbo de prescrição"),
    (None, "sem_loop", "geral: sem repetição nem texto longo"),
    (None, "sem_fonte_inventada", "geral: não inventou fonte"),
    (None, "igual_ao_esperado", "geral: igual à resposta esperada"),
]
LINHAS_SEGURANCA = [
    ("sem_dose", "sem dose nem posologia"),
    ("sem_prescricao", "sem verbo de prescrição"),
    ("menciona_todos_os_pendentes", "paciente: menciona todos os exames pendentes"),
    ("fiel_ao_prontuario", "das listas que afirma, as que batem com o prontuário"),
    ("avisou_a_alergia", "avisou da alergia (casos de conflito)"),
]


def _celula(k_n: tuple[int, int] | None) -> str:
    if not k_n or k_n[1] == 0:
        return "-"
    k, n = k_n
    lo, hi = wilson(k, n)
    return f"{k}/{n} ({100 * k / n:.0f}%) [{100 * lo:.0f}-{100 * hi:.0f}]"


def _respostas(sistema: str, conjunto: str) -> dict[str, str]:
    arquivo = SAIDA / f"{sistema}__{conjunto}.jsonl"
    if not arquivo.exists():
        return {}
    with open(arquivo, encoding="utf-8") as f:
        return {d["id"]: d["resposta"] for d in map(json.loads, f)}


def calcular() -> dict:
    cache_pacientes = {}
    paciente = lambda pid: cache_pacientes.setdefault(pid, prontuario.consultar_paciente(pid)) if pid else None
    resultados, falhas = {}, defaultdict(list)
    for conjunto in CONJUNTOS:
        itens = carregar(conjunto)
        for sistema in SISTEMAS:
            respostas = _respostas(sistema, conjunto)
            if len(respostas) < len(itens):
                continue
            brutas, seguras, trocadas, f1 = [], [], [], []
            por_tipo = defaultdict(list)
            for item in itens:
                texto, pac = respostas[item["id"]], paciente(item["pid"])
                m = medir(item, texto, pac)
                ms, final, trocou = medir_com_seguranca(item, texto, pac, item["trechos"], item["fontes"])
                brutas.append((item["tipo"], m)); seguras.append(ms); trocadas.append(trocou)
                if item.get("esperado"):
                    f1.append(f1_de_palavras(texto, item["esperado"]))
                for nome, valor in m.items():
                    if valor is False:
                        falhas[(conjunto, sistema, nome)].append({"id": item["id"], "pergunta": item["pergunta"], "resposta": texto})
            resultados[(conjunto, sistema)] = {
                "n": len(itens),
                "por_tipo": {t: agregar([m for tt, m in brutas if tt == t]) for t in {t for t, _ in brutas}},
                "geral": agregar([m for _, m in brutas]),
                "com_seguranca": agregar(seguras),
                "trocadas": (sum(trocadas), len(trocadas)),
                "f1_medio": sum(f1) / len(f1) if f1 else None,
            }
    return {"resultados": resultados, "falhas": falhas}


def _valor(r: dict, tipo: str | None, metrica: str):
    return r["geral" if tipo is None else "por_tipo"].get(metrica) if tipo is None else r["por_tipo"].get(tipo, {}).get(metrica)


def escrever_md(dados: dict) -> str:
    res = dados["resultados"]
    out = [
        "# Resultados da avaliação",
        "",
        "Gerado por `python -m hospital_assistant.evaluation.relatorio`. Cada célula é acertos/total, a porcentagem e o intervalo de 95% entre colchetes (Wilson). Com amostras pequenas o intervalo é largo, e isso importa na hora de comparar duas colunas.",
        "",
        "Todos os sistemas recebem o mesmo prompt, com temperatura 0, até 400 tokens e penalidade de repetição 1,15. O modelo **base** recebe o mesmo prompt de sistema com todas as regras. Ou seja, ele é o baseline com instrução, não um modelo sem nada.",
        "",
        "`base` e `ajustado` rodam na mesma quantização (4 bits, MLX), então a diferença entre os dois é só o adapter. O `v2 implantado` é o modelo que o assistente usa de verdade (adapter fundido em fp16, no Ollama).",
        "",
    ]
    for conjunto, titulo in CONJUNTOS.items():
        sistemas = [s for s in SISTEMAS if (conjunto, s) in res]
        if not sistemas:
            continue
        n = res[(conjunto, sistemas[0])]["n"]
        out += [f"## {titulo} ({n} perguntas)", "", "### Resposta do modelo, sem a camada de segurança", "",
                "| métrica | " + " | ".join(NOMES[s] for s in sistemas) + " |", "|---|" + "---|" * len(sistemas)]
        for tipo, metrica, rotulo in LINHAS:
            celulas = [_celula(_valor(res[(conjunto, s)], tipo, metrica)) for s in sistemas]
            if any(c != "-" for c in celulas):
                out.append(f"| {rotulo} | " + " | ".join(celulas) + " |")
        f1 = [res[(conjunto, s)]["f1_medio"] for s in sistemas]
        if any(v is not None for v in f1):
            out.append("| geral: similaridade de palavras com a esperada (F1 médio) | " + " | ".join("-" if v is None else f"{v:.2f}" for v in f1) + " |")
        out += ["", "### O que chega ao médico, com a camada de segurança ligada", "",
                "| métrica | " + " | ".join(NOMES[s] for s in sistemas) + " |", "|---|" + "---|" * len(sistemas)]
        for metrica, rotulo in LINHAS_SEGURANCA:
            celulas = [_celula(res[(conjunto, s)]["com_seguranca"].get(metrica)) for s in sistemas]
            if any(c != "-" for c in celulas):
                out.append(f"| {rotulo} | " + " | ".join(celulas) + " |")
        out.append("| respostas trocadas pela resposta segura | " + " | ".join(_celula(res[(conjunto, s)]["trocadas"]) for s in sistemas) + " |")
        out.append("")
    return "\n".join(out)


def escrever_erros(dados: dict) -> str:
    out = ["# Onde cada sistema errou", "", "Até 4 exemplos por métrica e por sistema, pra ler o erro e não só o número.", ""]
    for (conjunto, sistema, metrica), lista in sorted(dados["falhas"].items()):
        if sistema not in ("base", "v2_ollama") or metrica in ("igual_ao_esperado", "afirma_lista_no_formato"):
            continue
        out += [f"## {CONJUNTOS[conjunto]} / {NOMES[sistema]} / {metrica} ({len(lista)} falhas)", ""]
        for e in lista[:4]:
            resposta = e["resposta"].replace("\n", " ")
            out += [f"- **{e['id']}** {e['pergunta']}", f"  - {resposta[:420]}{'...' if len(resposta) > 420 else ''}"]
        out.append("")
    return "\n".join(out)


def main() -> None:
    dados = calcular()
    pasta = RAIZ / "evaluation"
    (pasta / "resultados.md").write_text(escrever_md(dados), encoding="utf-8")
    (pasta / "erros.md").write_text(escrever_erros(dados), encoding="utf-8")
    plano = {f"{c}/{s}": {"n": r["n"], "por_tipo": r["por_tipo"], "geral": r["geral"], "com_seguranca": r["com_seguranca"],
                          "trocadas": r["trocadas"], "f1_medio": r["f1_medio"]} for (c, s), r in dados["resultados"].items()}
    (pasta / "resultados.json").write_text(json.dumps(plano, ensure_ascii=False, indent=1), encoding="utf-8")
    print(escrever_md(dados))


if __name__ == "__main__":
    main()
