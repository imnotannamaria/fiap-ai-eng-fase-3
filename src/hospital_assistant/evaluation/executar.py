"""Gera as respostas de cada sistema pra cada conjunto e guarda em evaluation/resultados/.

    python -m hospital_assistant.evaluation.executar
    python -m hospital_assistant.evaluation.executar --sistemas base v2_ollama --conjuntos fora_do_molde

As respostas ficam guardadas em JSONL e as métricas são calculadas depois (relatorio.py), então
mudar uma métrica não obriga a gerar tudo de novo. Se o processo cair, continua de onde parou.
"""

import argparse
import json
import time

from hospital_assistant.config import RAIZ
from hospital_assistant.evaluation.conjuntos import carregar
from hospital_assistant.evaluation.geradores import SISTEMAS

SAIDA = RAIZ / "evaluation" / "resultados"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sistemas", nargs="+", default=list(SISTEMAS), choices=list(SISTEMAS))
    ap.add_argument("--conjuntos", nargs="+", default=["teste", "fora_do_molde"])
    args = ap.parse_args()
    SAIDA.mkdir(parents=True, exist_ok=True)
    itens_por_conjunto = {c: carregar(c) for c in args.conjuntos}

    for sistema in args.sistemas:
        gerador = None
        for conjunto, itens in itens_por_conjunto.items():
            arquivo = SAIDA / f"{sistema}__{conjunto}.jsonl"
            feitos = {json.loads(l)["id"] for l in open(arquivo, encoding="utf-8")} if arquivo.exists() else set()
            pendentes = [i for i in itens if i["id"] not in feitos]
            if not pendentes:
                print(f"{sistema} / {conjunto}: completo ({len(itens)})", flush=True)
                continue
            gerador = gerador or SISTEMAS[sistema]()
            inicio = time.time()
            with open(arquivo, "a", encoding="utf-8") as f:
                for n, item in enumerate(pendentes, start=1):
                    resposta = gerador.responder(item["mensagens"])
                    f.write(json.dumps({"id": item["id"], "resposta": resposta}, ensure_ascii=False) + "\n")
                    f.flush()
                    if n % 20 == 0:
                        print(f"{sistema} / {conjunto}: {n}/{len(pendentes)} ({time.time() - inicio:.0f}s)", flush=True)
            print(f"{sistema} / {conjunto}: {len(pendentes)} gerados em {time.time() - inicio:.0f}s", flush=True)


if __name__ == "__main__":
    main()
