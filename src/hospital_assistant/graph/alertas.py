"""Fila de alertas para a equipe médica.

No protótipo a fila é um arquivo JSONL (`logs/alertas.jsonl`). Num hospital de verdade seria
um sistema de plantão ou mensageria. O fluxo só chama `emitir`, então trocar a fila não mexe no grafo.
"""

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from hospital_assistant.config import LOGS


class FilaDeAlertas:
    def __init__(self, caminho: Path | None = None):
        self.caminho = Path(caminho) if caminho else LOGS / "alertas.jsonl"
        self._trava = threading.Lock()

    def emitir(self, id_fluxo: str, paciente_id: str, alerta: dict) -> dict:
        registro = {
            "quando": datetime.now(timezone.utc).isoformat(),
            "destino": "equipe_medica",
            "id_fluxo": id_fluxo,
            "paciente_id": paciente_id,
            **alerta,
        }
        with self._trava:
            self.caminho.parent.mkdir(parents=True, exist_ok=True)
            with open(self.caminho, "a", encoding="utf-8") as f:
                f.write(json.dumps(registro, ensure_ascii=False) + "\n")
        return registro

    def ler(self) -> list[dict]:
        if not self.caminho.exists():
            return []
        with open(self.caminho, encoding="utf-8") as f:
            return [json.loads(l) for l in f if l.strip()]
