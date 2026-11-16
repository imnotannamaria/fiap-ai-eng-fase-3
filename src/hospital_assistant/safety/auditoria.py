"""Log de auditoria em JSONL, uma linha por consulta, encadeado por hash.

Cada linha guarda o hash da anterior. Se alguém editar, apagar ou reordenar uma linha,
`verificar()` aponta onde a corrente quebra. Não impede a alteração, mas ela não passa batida.
"""

import hashlib
import json
import threading
from pathlib import Path

from hospital_assistant.config import LOGS

GENESIS = "0" * 64


def _hash(anterior: str, corpo: str) -> str:
    return hashlib.sha256((anterior + corpo).encode("utf-8")).hexdigest()


class Auditoria:
    def __init__(self, caminho: Path | None = None):
        self.caminho = Path(caminho) if caminho else LOGS / "auditoria.jsonl"
        self._trava = threading.Lock()

    def _ultimo_hash(self) -> str:
        if not self.caminho.exists():
            return GENESIS
        ultima = ""
        with open(self.caminho, encoding="utf-8") as f:
            for linha in f:
                if linha.strip():
                    ultima = linha
        return json.loads(ultima)["hash"] if ultima else GENESIS

    def registrar(self, evento: dict) -> dict:
        with self._trava:
            self.caminho.parent.mkdir(parents=True, exist_ok=True)
            evento = {**evento, "hash_anterior": self._ultimo_hash()}
            corpo = json.dumps(evento, sort_keys=True, ensure_ascii=False)
            evento["hash"] = _hash(evento["hash_anterior"], corpo)
            with open(self.caminho, "a", encoding="utf-8") as f:
                f.write(json.dumps(evento, ensure_ascii=False) + "\n")
            return evento

    def verificar(self) -> tuple[bool, int | None]:
        """(íntegro, número da primeira linha com problema, começando em 1)."""
        anterior = GENESIS
        if not self.caminho.exists():
            return True, None
        with open(self.caminho, encoding="utf-8") as f:
            for n, linha in enumerate(f, start=1):
                try:
                    evento = json.loads(linha)
                    hash_gravado = evento.pop("hash")
                except (json.JSONDecodeError, KeyError):
                    return False, n
                corpo = json.dumps(evento, sort_keys=True, ensure_ascii=False)
                if evento.get("hash_anterior") != anterior or _hash(anterior, corpo) != hash_gravado:
                    return False, n
                anterior = hash_gravado
        return True, None

    def ler(self) -> list[dict]:
        if not self.caminho.exists():
            return []
        with open(self.caminho, encoding="utf-8") as f:
            return [json.loads(l) for l in f if l.strip()]
