"""Caminhos e constantes do projeto."""

import os
from datetime import date
from pathlib import Path

# data fixa pra idade e datas dos dados sintéticos saírem sempre iguais
REFERENCIA = date(2026, 11, 14)

RAIZ = Path(__file__).resolve().parents[2]
DATA = RAIZ / "data"
SYNTH = DATA / "synthetic"
PROCESSED = DATA / "processed"
DB_PATH = Path(os.getenv("PRONTUARIOS_DB", SYNTH / "prontuarios.db"))
LOGS = RAIZ / "logs"
MODELS = RAIZ / "models"

BASE_MODEL = os.getenv("BASE_MODEL", "mlx-community/Qwen2.5-1.5B-Instruct-4bit")
ADAPTER_DIR = MODELS / "adapters"
FUSED_DIR = MODELS / "fused"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "hospital-assistant")
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

SYSTEM_PROMPT = (
    "Você é o assistente clínico do Hospital Modelo. Responda em português do Brasil, "
    "só com base nos trechos de protocolos e nos dados do paciente fornecidos. "
    "Sempre cite a fonte entre colchetes, como [PROT-001]. "
    "Você nunca prescreve medicamentos, doses nem diagnostica: apresente o que o protocolo "
    "diz e termine lembrando que a decisão é do médico responsável. "
    "Se a informação não estiver nos protocolos, diga que não encontrou."
)
