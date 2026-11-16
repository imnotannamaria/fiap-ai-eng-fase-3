"""Roda o fluxo de um paciente no terminal.

    python -m hospital_assistant.graph P-0038
    python -m hospital_assistant.graph P-0038 --medico "Dra. Demo" --decisao aprovar
    python -m hospital_assistant.graph --mermaid
"""

import argparse

from hospital_assistant.graph.fluxo import FluxoPaciente


def main() -> None:
    ap = argparse.ArgumentParser(description="Fluxo automatizado do paciente (LangGraph)")
    ap.add_argument("paciente", nargs="?", help="ID do paciente, ex.: P-0038")
    ap.add_argument("--medico", help="nome de quem decide")
    ap.add_argument("--decisao", choices=["aprovar", "rejeitar"])
    ap.add_argument("--observacao", default="")
    ap.add_argument("--mermaid", action="store_true", help="imprime o diagrama do grafo e sai")
    args = ap.parse_args()

    fluxo = FluxoPaciente()
    if args.mermaid:
        print(fluxo.mermaid())
        return
    if not args.paciente:
        ap.error("informe o ID do paciente")

    mostrar = lambda no, resumo: print(f"  [{no}] {resumo}", flush=True)
    print(f"Fluxo para {args.paciente}")
    estado = fluxo.iniciar(args.paciente, ao_passar=mostrar)
    if "plano" not in estado:
        print(f"\nFluxo encerrado: {estado['status']}")
        return
    print("\n" + estado["plano"])
    if not estado["aguardando_medico"]:
        return

    medico = args.medico or input("\nMédico responsável (nome): ").strip()
    decisao = args.decisao or input("Decisão (aprovar/rejeitar): ").strip()
    estado = fluxo.decidir(estado["id_fluxo"], medico, decisao, args.observacao, ao_passar=mostrar)
    print(f"\nStatus final: {estado['status']}")


if __name__ == "__main__":
    main()
