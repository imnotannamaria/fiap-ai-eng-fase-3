"""Classifica a pergunta antes de ela ir pro modelo. Só marca e registra no log:
quem barra é a validação da saída, que não depende de o modelo obedecer."""

import re

from hospital_assistant.assistant.retriever import normalizar

PADROES = {
    "pedido_prescricao": r"prescrev|prescri[cç]|receit|posologia|\bdose\b|\bdoses\b|posso (come[cç]ar|dar|liberar|iniciar|usar)|pode (prescrever|receitar|liberar)",
    "tentativa_de_burlar_regra": (
        r"ignor[ea] .{0,30}(regra|instru|anterior)|esque[cç]a .{0,30}(regra|instru|tudo)|voce (agora )?e (o |um )?medic|"
        r"a partir de agora|sem validacao|modo (desenvolvedor|admin)|system prompt|desative .{0,20}(regra|filtro|seguranca)|so dessa vez"
    ),
}


def classificar_entrada(pergunta: str) -> list[str]:
    texto = normalizar(pergunta)
    return [nome for nome, padrao in PADROES.items() if re.search(normalizar(padrao), texto)]
