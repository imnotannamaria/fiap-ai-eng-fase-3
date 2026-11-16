"""Fine-tuning LoRA (QLoRA, base em 4 bits) com MLX-LM, nativo do Apple Silicon.

Uso:
    python -m hospital_assistant.finetune.train            # treina e avalia no teste
    python -m hospital_assistant.finetune.train --fuse     # junta adapter ao modelo base
    python -m hospital_assistant.finetune.train --fuse --adapter-path adapters/v2   # usa o adapter versionado, sem treinar
    python -m hospital_assistant.finetune.train --resume   # retoma se o treino caiu
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

from hospital_assistant.config import ADAPTER_DIR, BASE_MODEL, FUSED_DIR, LOGS, PROCESSED

# Os motivos de cada escolha estão em docs/fine_tuning.md.
HIPERPARAMETROS = {
    "--num-layers": "16",          # LoRA nas 16 últimas camadas: bom custo/benefício em 16 GB
    "--batch-size": "4",
    "--iters": "400",              # ~3 épocas sobre ~530 exemplos
    "--learning-rate": "1e-4",
    "--max-seq-length": "1536",
    "--steps-per-eval": "100",
    "--save-every": "100",
}

# --resume parte do checkpoint salvo na iteração 200, então faltam as iterações restantes
ITERACAO_DO_CHECKPOINT = 200


def treinar(retomar: bool = False) -> None:
    LOGS.mkdir(exist_ok=True)
    ADAPTER_DIR.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, "-m", "mlx_lm", "lora",
        "--model", BASE_MODEL, "--train", "--data", str(PROCESSED),
        "--adapter-path", str(ADAPTER_DIR), "--mask-prompt", "--grad-checkpoint", "--test",
    ]
    hiper = dict(HIPERPARAMETROS)
    if retomar:
        # treino caiu no meio: continua do último checkpoint e faz só as iterações que faltam
        hiper["--iters"] = str(int(hiper["--iters"]) - ITERACAO_DO_CHECKPOINT)
        cmd += ["--resume-adapter-file", str(ADAPTER_DIR / "adapters.safetensors")]
    for k, v in hiper.items():
        cmd += [k, v]
    print(" ".join(cmd))
    with open(LOGS / "finetune.log", "a" if retomar else "w") as log:  # retomar não apaga o log da primeira parte
        env = {**os.environ, "PYTHONUNBUFFERED": "1"}  # sem isso o log só aparece quando o treino acaba
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
        for linha in proc.stdout:
            print(linha, end="", flush=True)
            log.write(linha)
            log.flush()
        if proc.wait():
            raise SystemExit(proc.returncode)


def juntar(adapter: Path = ADAPTER_DIR) -> None:
    cmd = [
        sys.executable, "-m", "mlx_lm", "fuse", "--model", BASE_MODEL,
        "--adapter-path", str(adapter), "--save-path", str(FUSED_DIR), "--dequantize",
    ]
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fuse", action="store_true")
    ap.add_argument("--resume", action="store_true", help="retoma do checkpoint da iteração 200 (adapter.safetensors)")
    ap.add_argument("--adapter-path", type=Path, default=ADAPTER_DIR, help="adapter usado no --fuse (padrão: o do último treino)")
    args = ap.parse_args()
    juntar(args.adapter_path) if args.fuse else treinar(args.resume)
