"""Quem gera a resposta. Todos recebem as mesmas mensagens (system + user) e geram com
temperatura 0, no máximo 400 tokens e penalidade de repetição 1,15, igual ao Modelfile do Ollama."""

import json
import urllib.request

from hospital_assistant.config import ADAPTER_DIR, BASE_MODEL, OLLAMA_URL

MAX_TOKENS = 400
PENALIDADE = 1.15


class Ollama:
    def __init__(self, modelo: str):
        self.modelo = modelo

    def responder(self, mensagens: list[dict]) -> str:
        corpo = {"model": self.modelo, "messages": mensagens, "stream": False,
                 "options": {"temperature": 0, "num_predict": MAX_TOKENS, "repeat_penalty": PENALIDADE}}
        req = urllib.request.Request(f"{OLLAMA_URL}/api/chat", data=json.dumps(corpo).encode(), headers={"Content-Type": "application/json"})
        return json.loads(urllib.request.urlopen(req, timeout=300).read())["message"]["content"].strip()


class MLX:
    def __init__(self, base: str, adapter: str | None = None):
        from mlx_lm import load

        self.modelo, self.tokenizador = load(base, adapter_path=adapter) if adapter else load(base)

    def responder(self, mensagens: list[dict]) -> str:
        from mlx_lm import generate
        from mlx_lm.sample_utils import make_logits_processors, make_sampler

        prompt = self.tokenizador.apply_chat_template(mensagens, add_generation_prompt=True, tokenize=False)
        return generate(
            self.modelo, self.tokenizador, prompt=prompt, max_tokens=MAX_TOKENS, sampler=make_sampler(temp=0.0),
            logits_processors=make_logits_processors(repetition_penalty=PENALIDADE, repetition_context_size=64),
        ).strip()


# nome -> como criar. "base" e "ajustado_mlx" usam a mesma quantização (4 bits), então a
# diferença entre os dois é só o adapter. "v2_ollama" é o modelo implantado (fundido, fp16).
SISTEMAS = {
    "base": lambda: MLX(BASE_MODEL),
    "ajustado_mlx": lambda: MLX(BASE_MODEL, str(ADAPTER_DIR)),
    "v2_ollama": lambda: Ollama("hospital-assistant"),
    "v1_ollama": lambda: Ollama("hospital-assistant-v1"),
}
