"""Protocolos internos SINTÉTICOS do "Hospital Modelo".

Texto didático e fictício, escrito para este projeto. Não usar em prática clínica.
Propositalmente sem doses: o assistente nunca prescreve, só aponta o protocolo.
"""

PROTOCOLS = [
    {
        "id": "PROT-001",
        "titulo": "Sepse no adulto",
        "definicao": "Disfunção orgânica causada por resposta desregulada a uma infecção. Suspeitar quando há foco infeccioso provável com sinais de hipoperfusão ou disfunção de órgão.",
        "criterios": "Suspeita se houver foco infeccioso mais dois ou mais: temperatura acima de 38,3 ou abaixo de 36, frequência cardíaca acima de 90, frequência respiratória acima de 20, alteração do nível de consciência, pressão sistólica abaixo de 100 ou lactato elevado.",
        "conduta": "Abrir o pacote da primeira hora: coletar lactato e duas hemoculturas antes do antibiótico, iniciar antibiótico empírico conforme o protocolo de antimicrobianos, repor volume com cristaloide se hipotensão ou lactato elevado e reavaliar a perfusão. Acionar a UTI se não houver resposta.",
        "exames": "Lactato, hemoculturas (2 pares), hemograma, creatinina, bilirrubina, gasometria arterial, urina tipo 1 e radiografia de tórax.",
        "alertas": "Hipotensão persistente após reposição, lactato acima de 4, rebaixamento do nível de consciência ou oligúria. Escalar imediatamente para o médico plantonista.",
        "atencao": "Verificar alergias a antibióticos e função renal antes de definir o esquema. A escolha do antibiótico é sempre do médico responsável.",
    },
    {
        "id": "PROT-002",
        "titulo": "Dor torácica e suspeita de síndrome coronariana aguda",
        "definicao": "Dor ou desconforto torácico com possibilidade de origem isquêmica. Exige avaliação rápida, pois o tempo até o diagnóstico muda o desfecho.",
        "criterios": "Dor opressiva, irradiada para braço ou mandíbula, com sudorese, náusea ou dispneia. Fatores de risco: diabetes, hipertensão, tabagismo, histórico familiar.",
        "conduta": "Fazer eletrocardiograma de 12 derivações em até 10 minutos da chegada e mostrar ao médico imediatamente. Monitorar o paciente, coletar troponina seriada e manter acesso venoso. Se houver supradesnível de ST, acionar o fluxo de reperfusão.",
        "exames": "ECG em até 10 minutos, troponina na chegada e repetida, hemograma, creatinina, eletrólitos e radiografia de tórax.",
        "alertas": "Supradesnível de ST, instabilidade hemodinâmica, arritmia ou dor que não cede. Chamar o médico na hora.",
        "atencao": "Conferir uso de anticoagulantes e alergias antes de qualquer medicação. A decisão de tratar é do médico.",
    },
    {
        "id": "PROT-003",
        "titulo": "Acidente vascular cerebral agudo",
        "definicao": "Déficit neurológico de início súbito por causa vascular. A janela de tempo para tratamento é curta.",
        "criterios": "Fraqueza ou dormência de um lado do corpo, desvio da boca, dificuldade para falar ou perda visual súbita. Registrar o horário exato em que o paciente foi visto bem pela última vez.",
        "conduta": "Ativar o código AVC, registrar a hora do último momento normal, medir glicemia capilar e solicitar tomografia de crânio sem contraste com prioridade. Manter via aérea segura e não reduzir a pressão de forma agressiva sem orientação médica.",
        "exames": "Tomografia de crânio sem contraste, glicemia capilar, ECG, hemograma, coagulograma e eletrólitos.",
        "alertas": "Início dos sintomas há menos de 4 horas e meia, rebaixamento de consciência ou piora do déficit durante a observação.",
        "atencao": "Verificar uso de anticoagulantes, cirurgia recente e sangramento prévio. A indicação de trombólise é decisão do neurologista ou médico responsável.",
    },
    {
        "id": "PROT-004",
        "titulo": "Pneumonia adquirida na comunidade",
        "definicao": "Infecção pulmonar aguda em paciente fora do ambiente hospitalar nos últimos dias.",
        "criterios": "Tosse, febre, dispneia e escarro, com novo infiltrado na radiografia. Estratificar a gravidade antes de decidir o local de tratamento.",
        "conduta": "Aplicar o escore de gravidade do protocolo (CURB-65), medir saturação, coletar exames e definir entre tratamento ambulatorial e internação. Iniciar antibiótico conforme o protocolo de antimicrobianos após avaliação médica.",
        "exames": "Radiografia de tórax, hemograma, ureia, creatinina, proteína C reativa e oximetria. Hemocultura se internação.",
        "alertas": "Saturação abaixo de 92%, confusão mental, frequência respiratória acima de 30 ou pressão sistólica abaixo de 90.",
        "atencao": "Considerar idade, comorbidades, alergias e função renal. Esquema e duração ficam a cargo do médico.",
    },
    {
        "id": "PROT-005",
        "titulo": "Cetoacidose diabética",
        "definicao": "Complicação aguda do diabetes com hiperglicemia, cetose e acidose metabólica.",
        "criterios": "Glicemia elevada, cetonemia ou cetonúria e pH baixo ou bicarbonato reduzido. Sintomas comuns: poliúria, sede, náusea, dor abdominal e respiração rápida e profunda.",
        "conduta": "Monitorar sinais vitais e glicemia de hora em hora, coletar gasometria e eletrólitos, repor volume e seguir o protocolo de insulina endovenosa definido pelo médico. Checar o potássio antes de iniciar a insulina.",
        "exames": "Glicemia, gasometria venosa ou arterial, cetonas, sódio, potássio, ureia, creatinina e ECG.",
        "alertas": "Potássio abaixo de 3,3 ou acima de 5,5, rebaixamento de consciência ou pH muito baixo. Avisar o médico imediatamente.",
        "atencao": "Procurar o fator desencadeante, como infecção ou falha na insulina. Doses e velocidades são definidas pelo médico.",
    },
    {
        "id": "PROT-006",
        "titulo": "Crise hipertensiva",
        "definicao": "Elevação importante da pressão arterial. Diferenciar urgência (sem lesão de órgão-alvo) de emergência (com lesão).",
        "criterios": "Pressão acima de 180 por 120. Emergência se houver dor torácica, déficit neurológico, edema agudo de pulmão, alteração visual ou confusão.",
        "conduta": "Repetir a medida após repouso, procurar sinais de lesão de órgão-alvo e avisar o médico. Na emergência, transferir para monitorização e seguir a conduta definida pelo médico. Evitar queda abrupta da pressão.",
        "exames": "ECG, creatinina, eletrólitos, urina tipo 1 e, se houver sintoma neurológico, tomografia de crânio.",
        "alertas": "Qualquer sinal de lesão de órgão-alvo. Tratar como emergência até o médico avaliar.",
        "atencao": "Verificar adesão e uso de medicações anti-hipertensivas e outras substâncias que elevam a pressão.",
    },
    {
        "id": "PROT-007",
        "titulo": "Anafilaxia",
        "definicao": "Reação alérgica grave e de início rápido, com risco de vida.",
        "criterios": "Urticária ou inchaço de lábios e língua mais dificuldade respiratória, queda de pressão ou vômitos, depois da exposição a um alérgeno provável.",
        "conduta": "Chamar o médico imediatamente, posicionar o paciente deitado com as pernas elevadas, garantir via aérea e monitorar. A medicação de primeira linha segue o protocolo de emergência e é administrada por ordem médica.",
        "exames": "Monitorização contínua, oximetria e, se possível, triptase sérica após o evento.",
        "alertas": "Estridor, chiado, hipotensão ou perda de consciência. Acionar equipe de emergência.",
        "atencao": "Registrar o alérgeno suspeito e atualizar a lista de alergias do prontuário.",
    },
    {
        "id": "PROT-008",
        "titulo": "Tromboembolismo pulmonar",
        "definicao": "Obstrução de artéria pulmonar por coágulo. Pode se apresentar com dispneia súbita ou dor pleurítica.",
        "criterios": "Dispneia súbita, dor torácica pleurítica, taquicardia, hemoptise ou sinais de trombose venosa profunda. Aplicar o escore de probabilidade do protocolo (Wells).",
        "conduta": "Calcular a probabilidade clínica, solicitar D-dímero se baixa probabilidade e angiotomografia de tórax se probabilidade intermediária ou alta. Avisar o médico. A anticoagulação segue prescrição médica.",
        "exames": "D-dímero, angiotomografia de tórax, ECG, troponina, gasometria e creatinina antes do contraste.",
        "alertas": "Hipotensão, síncope ou hipoxemia importante. Tratar como emergência.",
        "atencao": "Checar função renal antes do contraste e risco de sangramento antes de anticoagular.",
    },
    {
        "id": "PROT-009",
        "titulo": "Insuficiência cardíaca descompensada",
        "definicao": "Piora aguda dos sintomas de congestão ou baixo débito em paciente com insuficiência cardíaca.",
        "criterios": "Dispneia, ortopneia, edema de membros inferiores, ganho de peso rápido e estertores pulmonares.",
        "conduta": "Avaliar perfusão e congestão, monitorizar, posicionar sentado, medir saturação e pesar o paciente. O médico define diurético e demais ajustes. Registrar balanço hídrico.",
        "exames": "ECG, BNP ou NT-proBNP, troponina, creatinina, eletrólitos, hemograma e radiografia de tórax.",
        "alertas": "Hipotensão, saturação abaixo de 90% ou piora da função renal.",
        "atencao": "Revisar a lista de medicamentos de uso contínuo e adesão ao tratamento e à restrição de sal.",
    },
    {
        "id": "PROT-010",
        "titulo": "Infecção do trato urinário no adulto",
        "definicao": "Infecção das vias urinárias, de cistite não complicada a pielonefrite.",
        "criterios": "Disúria, urgência, aumento da frequência, dor suprapúbica. Febre e dor lombar sugerem acometimento alto.",
        "conduta": "Avaliar sinais de gravidade, solicitar urina tipo 1 e urocultura e avisar o médico. A escolha do antibiótico considera alergias, gestação e função renal e é definida pelo médico.",
        "exames": "Urina tipo 1, urocultura, hemograma e creatinina se houver febre ou suspeita de pielonefrite.",
        "alertas": "Febre alta, vômitos, hipotensão ou sinais de sepse. Seguir PROT-001.",
        "atencao": "Perguntar sobre gestação, sondagem vesical e episódios anteriores.",
    },
]

CAMPOS = {
    "definicao": "definição",
    "criterios": "critérios de suspeita",
    "conduta": "conduta inicial",
    "exames": "exames solicitados",
    "alertas": "sinais de alerta",
    "atencao": "pontos de atenção",
}

# As 3 primeiras formas de cada pergunta são "de manual". As 3 últimas são como o médico
# fala de verdade, mais solta. O treino vê só algumas, pro teste ter forma nunca vista.
PERGUNTAS = {
    "definicao": [
        "O que o protocolo define como {t}?",
        "Como o hospital define {t}?",
        "Qual a definição de {t} segundo nosso protocolo?",
        "Resumindo, o que é {t} pra gente aqui?",
        "Preciso lembrar a definição de {t}, pode me dizer?",
        "Pra eu alinhar com a equipe: o que o protocolo chama de {t}?",
    ],
    "criterios": [
        "Quais os critérios de suspeita de {t}?",
        "Quando devo suspeitar de {t}?",
        "Quais sinais indicam {t} no nosso protocolo?",
        "Chegou alguém que pode ser {t}. Como eu confirmo a suspeita?",
        "O que eu procuro no paciente pra pensar em {t}?",
        "Quais achados levantam a hipótese de {t}?",
    ],
    "conduta": [
        "Qual a conduta inicial em {t}?",
        "O que o protocolo orienta fazer primeiro em {t}?",
        "Como começo o atendimento de um paciente com {t}?",
        "Chegou um paciente com {t}. O que eu faço primeiro?",
        "Me ajuda com o passo a passo inicial de {t}.",
        "Qual o primeiro movimento da equipe diante de {t}?",
    ],
    "exames": [
        "Que exames o protocolo pede em {t}?",
        "Quais exames devo solicitar em {t}?",
        "Quais exames entram no fluxo de {t}?",
        "O que eu já deixo pedido pra {t}?",
        "Quais exames a gente colhe de cara em {t}?",
        "Me lista os exames de {t}.",
    ],
    "alertas": [
        "Quais sinais de alerta em {t}?",
        "Quando devo chamar o médico responsável em {t}?",
        "O que indica gravidade em {t}?",
        "Em {t}, o que me faz chamar o plantonista na hora?",
        "Quais sinais de piora em {t} eu não posso deixar passar?",
        "Quando {t} vira emergência?",
    ],
    "atencao": [
        "Que cuidados devo ter antes de definir o tratamento em {t}?",
        "Quais os pontos de atenção em {t}?",
        "O que preciso conferir no paciente em {t}?",
        "Antes de definir o tratamento de {t}, o que eu confiro?",
        "Que cuidado eu tenho que ter em {t}?",
        "O que não posso esquecer de checar em {t}?",
    ],
}


# Palavras que o médico usa no dia a dia e que não aparecem no título do protocolo.
# Só o retriever usa isso. Não entra no dataset nem no prompt.
SINONIMOS = {
    "PROT-001": "sepse septico septicemia infeccao generalizada",
    "PROT-002": "infarto iam sca angina coracao peito coronariana",
    "PROT-003": "avc derrame isquemico neurologico",
    "PROT-004": "pneumonia pulmao",
    "PROT-005": "cad cetoacidose diabetes diabetica",
    "PROT-006": "hipertensiva pressao hipertensao",
    "PROT-007": "anafilaxia anafilatica anafilatico urticaria angioedema",
    "PROT-008": "tep embolia trombo coagulo",
    "PROT-009": "ic icc insuficiencia cardiaca descompensada edema",
    "PROT-010": "itu urinaria urinario cistite pielonefrite",
}
