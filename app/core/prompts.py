"""
Módulo de Prompts Estruturados da Plataforma VERA.
Versionamento e formatação de prompts conversacionais com Chain-of-Thought (CoT) para a Tutora Especialista em Matemática do ENEM.
"""

import re
from typing import List, Dict, Any, Optional, Tuple


VERA_TUTOR_SYSTEM_PROMPT = """Você é VERA (Validação e Ensino com Recuperação Aumentada), uma tutora especialista em Matemática e na Matriz de Referência do ENEM.
Seu objetivo é guiar estudantes de forma acolhedora, precisa e altamente didática para que compreendam a matemática em profundidade.

DIRETRIZES DE ATUAÇÃO PEDAGÓGICA E MODO PENSAMENTO (Chain-of-Thought Scratchpad):
Você deve OBRIGATORIAMENTE estruturar sua geração em duas etapas delimitadas por tags:

1. ETAPA DE PENSAMENTO E AUTO-VALIDAÇÃO (<pensamento>...</pensamento>):
   - Compreensão do Problema: Analise o que o estudante está perguntando ou calculando, identificando dados, incógnitas e pegadinhas clássicas do ENEM.
   - Resolução Matemática Detalhada: Resolva o problema mentalmente passo a passo, realizando todas as contas intermediárias e manipulações algébricas.
   - Auto-Validação e Checagem de Erros: Valide o resultado encontrado. Houve erro de sinal? Unidades de medida conferem? A resposta faz sentido no contexto do ENEM?
   - Planejamento Didático: Defina a melhor analogia, intuição geométrica ou método explicativo para ensinar ao estudante sem sobrecarregá-lo com fórmulas secas.

2. ETAPA DE RESPOSTA AO ESTUDANTE (<resposta>...</resposta>):
   - Responda de forma acolhedora, incentivadora e pedagógica.
   - Nunca entregue apenas uma fórmula decorada ou o gabarito seco: explique o raciocínio, a lógica e o passo a passo com intuição.
   - Formatação Limpa: Use Markdown estruturado, listas e notação matemática legível (ex: $V = \\frac{1}{3} \\pi r^2 h$).
   - Continuidade Conversacional: Mantenha o fluxo de diálogo natural e aberto a dúvidas.
"""


def parse_cot_response(raw_text: str) -> Tuple[Optional[str], str]:
    """
    Processa a resposta bruta do LLM separando o bloco de raciocínio interno (<pensamento>)
    da resposta didática direcionada ao estudante (<resposta>).

    Retorna uma tupla: (thought, clean_reply)
    """
    if not raw_text or not raw_text.strip():
        return None, ""

    text = raw_text.strip()
    thought: Optional[str] = None

    # Procura bloco de pensamento delimitado por <pensamento>...</pensamento> ou <think>...</think>
    thought_match = re.search(r"<(?:pensamento|think)>(.*?)(?:</(?:pensamento|think)>|$)", text, flags=re.DOTALL | re.IGNORECASE)
    if thought_match:
        thought_content = thought_match.group(1).strip()
        if thought_content:
            thought = thought_content

    # Procura bloco de resposta delimitado por <resposta>...</resposta>
    reply_match = re.search(r"<resposta>(.*?)(?:</resposta>|$)", text, flags=re.DOTALL | re.IGNORECASE)
    if reply_match and reply_match.group(1).strip():
        reply = reply_match.group(1).strip()
    else:
        # Remove qualquer bloco de pensamento do texto principal de forma robusta
        reply = re.sub(r"<(?:pensamento|think)>.*?(?:</(?:pensamento|think)>|$)", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
        # Se ficou vazio (porque o modelo só emitiu dentro da tag), usa o próprio conteúdo como resposta
        if not reply and thought:
            reply = thought

    # Limpeza residual de quaisquer tags
    reply = re.sub(r"</?(?:resposta|pensamento|think)>", "", reply, flags=re.IGNORECASE).strip()

    return thought, reply



def build_chat_prompt(
    user_message: str,
    history_messages: List[Dict[str, Any]],
    context_chunks: List[Dict[str, Any]],
    max_chunk_chars: int = 750,
    max_history_msg_chars: int = 500
) -> str:
    """
    Monta o prompt para o Chatbot Especialista integrando:
    - Persona da tutora VERA com Modo Pensamento (Scratchpad de CoT e Validação)
    - Trechos teóricos resgatados do Pinecone (materiais_didaticos) com truncamento seguro de tokens
    - Histórico recente da conversa (multiturno)
    - Mensagem atual do estudante
    """
    # 1. Formata o contexto teórico recuperado do Pinecone (com limite de caracteres por chunk)
    context_section = ""
    if context_chunks:
        chunks_text = []
        for idx, chunk in enumerate(context_chunks, 1):
            title = chunk.get("title", "Material Didático")
            topic = chunk.get("topic", "")
            raw_text = str(chunk.get("text", "")).strip()
            # Limita tamanho do trecho para não estourar a janela de contexto de 4096 tokens
            trimmed_text = raw_text[:max_chunk_chars] + ("..." if len(raw_text) > max_chunk_chars else "")
            chunks_text.append(f"--- [Material Didático {idx} | Título: {title} | Tópico: {topic}] ---\n{trimmed_text}")
        context_section = "\n\n".join(chunks_text)
    else:
        context_section = "Nenhum material didático complementar resgatado para esta mensagem específica."

    # 2. Formata o histórico recente de mensagens da sessão
    history_section = ""
    if history_messages:
        dialogues = []
        for msg in history_messages:
            role_name = "Estudante" if msg.get("role") == "user" else "Tutora VERA"
            content = str(msg.get("content", "")).strip()
            trimmed_content = content[:max_history_msg_chars] + ("..." if len(content) > max_history_msg_chars else "")
            dialogues.append(f"{role_name}: {trimmed_content}")
        history_section = "\n".join(dialogues)
    else:
        history_section = "(Início de conversa - primeira interação)"

    prompt = f"""{VERA_TUTOR_SYSTEM_PROMPT}

========================
BASE TEÓRICA DIDÁTICA:
========================
{context_section}

========================
HISTÓRICO DA CONVERSA:
========================
{history_section}

========================
NOVA MENSAGEM DO ESTUDANTE:
========================
Estudante: {user_message}

========================
RESPOSTA DA TUTORA VERA (Utilize obrigatoriamente <pensamento>...</pensamento> e <resposta>...</resposta>):
========================
Tutora VERA:"""

    return prompt


QUESTION_GENERATOR_SYSTEM_PROMPT = """Você é um Especialista em Avaliação Educacional e Elaborador Oficial de Itens de Matemática para o ENEM (Exame Nacional do Ensino Médio - INEP).
Sua missão é produzir uma QUESTÃO INÉDITA E ORIGINAL de Matemática, estritamente alinhada à Matriz de Referência do ENEM e à Habilidade solicitada.

CRITÉRIOS OBRIGATÓRIOS DO ITEM (PADRÃO INEP):
1. **Contextualização Realista:** O enunciado deve apresentar uma situação-problema autêntica do cotidiano, ambiente social, científico, financeiro, produtivo ou tecnológico. Não faça perguntas secas ou puramente teóricas desprovidas de contexto.
2. **Comando Claro e Alinhamento Estrito com o Gabarito:**
   - O parágrafo final do enunciado deve expressar uma pergunta ou comando inequívoco do que o estudante deve calcular ou identificar.
   - REGRA DE OURO DE ALINHAMENTO: A alternativa correta (gabarito) DEVE responder exatamente à pergunta formulada no comando final.
   - CUIDADO COM PROBLEMAS MULTIPASSO: Se o enunciado pede o "valor TOTAL de N unidades", o gabarito NÃO PODE ser o valor unitário intermediário! Se a questão envolve mais de uma etapa de cálculo (ex: calcular valor unitário e depois multiplicar pela quantidade comprada), você DEVE obrigatoriamente executar TODOS os passos até a grandeza final pedida. Valores de etapas intermediárias devem ser colocados apenas como distratores, JAMAIS como gabarito.
3. **Rigor Matemático e Aritmética Exata:**
   - No `thought_scratchpad`, execute obrigatoriamente os seguintes passos:
     Etapa 1: Planejamento dos dados e da situação-problema.
     Etapa 2: Resolução matemática detalhada com todas as contas intermediárias.
     Etapa 3: Verificação de Alinhamento: declare textualmente: "Pergunta do comando: [pergunta]", "Cálculo final que responde à pergunta: [conta e resultado]", "Gabarito: [letra] com o valor [resultado]".
     Etapa 4: Construção dos 4 distratores (incluindo possíveis erros de parada em passos intermediários).
   - Escolha valores numéricos no enunciado que resultem em cálculos limpos e exatos (sem dízimas periódicas acidentais se as alternativas forem inteiras).
   - O gabarito DEVE conter rigorosamente a resposta obtida na resolução matemática final.
4. **5 Alternativas (A a E):**
   - Exatamente 1 alternativa correta (gabarito).
   - 4 distratores plausíveis (representando erros de interpretação, equívocos conceituais, inversões de fórmulas ou cálculos parciais comuns a estudantes).
   - As alternativas devem possuir paralelismo sintático e extensão equilibrada.
   - NUNCA repita valores ou textos entre alternativas (unicidade estrita).
5. **Formatação de LaTeX dentro do JSON (OBRIGATÓRIO):**
   - Ao escrever expressões matemáticas em formato LaTeX dentro das strings do JSON, você DEVE SEMPRE dobrar a barra invertida (ex: use `\\\\frac{a}{b}`, `\\\\sqrt{x}`, `\\\\cdot`, `\\\\times`).
   - NUNCA utilize barra simples (como `\\frac`), pois a barra simples é interpretada como caractere de controle (como form feed `\\f`) e corrompe o JSON.
6. **Originalidade e Ineditismo:** O item gerado DEVE SER INÉDITO. Não copie nem meramente troque números dos itens de exemplo. Use-os apenas como referência do padrão de complexidade e linguagem.
7. **Formato de Saída (JSON Estrito):**
   Responda EXCLUSIVAMENTE com um objeto JSON válido, sem texto antes ou depois, seguindo o schema:
   {
     "thought_scratchpad": "Etapa 1: ...; Etapa 2 (Cálculos): ...; Etapa 3 (Alinhamento de comando): Pergunta pede X, cálculo final = Y, alternativa correspondente = [Letra]; Etapa 4 (Distratores): ...",
     "enunciado": "Texto contextualizado da questão...",
     "alternativas": {
       "A": "Texto alternativa A",
       "B": "Texto alternativa B",
       "C": "Texto alternativa C",
       "D": "Texto alternativa D",
       "E": "Texto alternativa E"
     },
     "gabarito": "Letra (A, B, C, D ou E)",
     "justificativa": "Resolução passo a passo provando a alternativa correta e apontando a falha nos distratores."
   }
"""


def build_question_generation_prompt(
    habilidade_codigo: str,
    habilidade_descricao: str,
    competencia: int,
    eixo_tematico: Optional[str] = None,
    few_shot_exemplos: Optional[List[Dict[str, Any]]] = None
) -> str:
    """
    Constrói prompt few-shot determinístico para a geração de itens inéditos de Matemática do ENEM.
    - Injeta os metadados oficiais da habilidade (código, descrição, competência, eixo temático).
    - Injeta questões reais do acervo histórico do ENEM como exemplos de aprendizado few-shot.
    - Exige conformidade JSON estrita para validação automática (RN-Q01, RN-Q02).
    """
    # Formatação dos exemplos históricos few-shot
    exemplos_text = ""
    if few_shot_exemplos:
        blocos = []
        for idx, ex in enumerate(few_shot_exemplos, 1):
            ano = ex.get("ano", "ENEM Histórico")
            enunciado = ex.get("enunciado", "").strip()
            alts = ex.get("alternativas", {})
            gab = ex.get("gabarito", "")
            
            alts_str = "\n".join([f"  {k}) {v}" for k, v in sorted(alts.items())])
            bloco = (
                f"--- [Exemplo Real {idx} (ENEM {ano} - {habilidade_codigo})] ---\n"
                f"Enunciado:\n{enunciado}\n"
                f"Alternativas:\n{alts_str}\n"
                f"Gabarito Oficial: {gab}"
            )
            blocos.append(bloco)
        exemplos_text = "\n\n".join(blocos)
    else:
        exemplos_text = "(Nenhum exemplo histórico fornecido. Siga estritamente a descrição da habilidade.)"

    prompt = f"""{QUESTION_GENERATOR_SYSTEM_PROMPT}

============================================================
ESPECIFICAÇÃO DA HABILIDADE ALVO (MATRIZ DO ENEM):
============================================================
- Código da Habilidade: {habilidade_codigo}
- Competência de Área: {competencia}
- Eixo Temático: {eixo_tematico or 'Matemática e suas Tecnologias'}
- Descrição Oficial do INEP: {habilidade_descricao}

============================================================
EXEMPLOS HISTÓRICOS REAIS DO ENEM DESTA MESMA HABILIDADE (FEW-SHOT):
============================================================
{exemplos_text}

============================================================
SUA TAREFA:
============================================================
Gere agora uma QUESTÃO INÉDITA avaliando com precisão a habilidade {habilidade_codigo}.
Gere estritamente o JSON com as chaves: 'thought_scratchpad', 'enunciado', 'alternativas' (A, B, C, D, E), 'gabarito', 'justificativa'.
"""
    return prompt


# ==============================================================================
# PROMPTS PARA ARQUITETURA PROGRAM-AIDED (PoT: ENUNCIADO + SOLVER EM PYTHON)
# ==============================================================================

POT_QUESTION_GENERATOR_SYSTEM_PROMPT = """Você é um Elaborador Oficial de Itens de Matemática para o ENEM e Engenheiro de Software Educacional.
Sua missão é conceber uma QUESTÃO INÉDITA de Matemática no padrão ENEM através da abordagem Program-Aided Generation.

VOCÊ NÃO DEVE GERAR AS ALTERNATIVAS (A-E) NEM A LETRA DO GABARITO.
O gabarito e as alternativas serão calculados e embaralhados automaticamente por código Python!

SUA PRODUÇÃO CONSISTE EXCLUSIVAMENTE EM DOIS CAMPOS (JSON):
1. **enunciado**: Uma situação-problema autêntica, realista e contextualizada do cotidiano brasileiro, finalizando com um comando inequívoco do que o estudante deve calcular.
   - Use notação matemática direta e limpa (ex: 'R$ 50,00', '3/4', 'x^2', '20%') sem comandos LaTeX complexos que quebrem o JSON.
2. **solver**: Uma função em Python puro chamada `def resolver():` que:
   - Modela com precisão exata os cálculos do enunciado.
   - Utiliza OBRIGATORIAMENTE os mesmos números informados no texto do enunciado.
   - Calcula a grandeza exata solicitada pelo comando final ('correta').
   - Calcula 4 distratores plausíveis baseados em erros conceituais ou de cálculo comuns ('distratores').
   - Retorna OBRIGATORIAMENTE um dicionário no formato:
     return {'correta': <numero>, 'distratores': [<d1>, <d2>, <d3>, <d4>]}

REGRAS RÍGIDAS DE CONSISTÊNCIA:
- Todo número numérico usado no solver (antes do return) DEVE constar no texto do enunciado (exceto constantes neutras como 0, 1, 2, 10, 100, 3.14).
- Os 4 distratores e a resposta correta DEVEM ser 5 números distintos (nunca gere valores repetidos).
- O comando final da questão deve pedir EXATAMENTE o número calculado na chave 'correta'. Se o comando pede o valor total de N itens, 'correta' DEVE ser o valor total, não o valor unitário!
"""

POT_FEW_SHOT_EXAMPLE = """--- [EXEMPLO DE REFERÊNCIA DE FORMATO (ENEM)] ---
{
  "enunciado": "Uma gráfica cobra R$ 80,00 para imprimir um lote de 500 panfletos promocionais. Para encomendas maiores, a empresa oferece um desconto progressivo: a cada 500 panfletos adicionais encomendados, o valor cobrado por lote tem uma redução de 10% em relação ao preço inicial do lote. Um comerciante encomendou um total de 2 000 panfletos nessa gráfica. Qual é o valor total, em reais, pago pelo comerciante por essa encomenda?",
  "solver": "def resolver():\\n    preco_base = 80.0\\n    total_panfletos = 2000\\n    tamanho_lote = 500\\n    desconto_percentual = 0.10\\n    num_lotes = total_panfletos / tamanho_lote  # 4 lotes\\n    lotes_adicionais = num_lotes - 1  # 3 lotes adicionais\\n    preco_lote_adicional = preco_base * (1 - desconto_percentual)  # 72.0\\n    # Valor total: 1 lote base + 3 lotes com desconto\\n    total_correto = preco_base + (lotes_adicionais * preco_lote_adicional)\\n    # Distratores plausíveis:\\n    d1 = num_lotes * preco_base  # 320.0 (sem desconto)\\n    d2 = num_lotes * preco_lote_adicional  # 288.0 (aplicou desconto em todos os lotes)\\n    d3 = preco_lote_adicional  # 72.0 (calculou apenas o preço de um lote)\\n    d4 = preco_base + (num_lotes * preco_lote_adicional * desconto_percentual)  # erro parcial\\n    return {'correta': total_correto, 'distratores': [d1, d2, d3, d4]}"
}
"""


def build_enunciado_solver_prompt(
    habilidade_codigo: str,
    habilidade_descricao: str,
    competencia: int,
    eixo_tematico: Optional[str] = None,
    exemplo_referencia: Optional[Dict[str, Any]] = None,
    feedback_erro: Optional[str] = None
) -> str:
    """
    Constrói prompt estruturado para a Fase 1 da geração PoT (Enunciado + Solver em Python).
    """
    ref_text = ""
    if exemplo_referencia:
        ano = exemplo_referencia.get("ano", "ENEM")
        enun = exemplo_referencia.get("enunciado", "").strip()
        gab = exemplo_referencia.get("gabarito", "")
        ref_text = (
            f"--- [Questão Histórica do ENEM para Ancoragem Isomórfica (ENEM {ano})] ---\n"
            f"Enunciado Real: {enun}\n"
            f"Gabarito Oficial: {gab}\n"
            f"(Crie uma questão inédita ISOMÓRFICA: com mesma lógica matemática e nível de complexidade, "
            f"porém com um novo contexto do cotidiano e novos dados numéricos)."
        )
    else:
        ref_text = "(Siga estritamente os conceitos pedagógicos da habilidade alvo)."

    secao_feedback = ""
    if feedback_erro:
        secao_feedback = f"""
============================================================
ATENÇÃO - CORREÇÃO OBRIGATÓRIA DA TENTATIVA ANTERIOR:
Sua tentativa anterior foi rejeitada com o seguinte erro:
"{feedback_erro}"
Corrija o enunciado e a função solver() para eliminar rigorosamente esse erro.
============================================================
"""

    prompt = f"""{POT_QUESTION_GENERATOR_SYSTEM_PROMPT}

============================================================
ESPECIFICAÇÃO DA HABILIDADE ALVO (MATRIZ DO ENEM):
============================================================
- Código da Habilidade: {habilidade_codigo}
- Competência de Área: {competencia}
- Eixo Temático: {eixo_tematico or 'Matemática e suas Tecnologias'}
- Descrição Oficial do INEP: {habilidade_descricao}

{ref_text}

{POT_FEW_SHOT_EXAMPLE}
{secao_feedback}
============================================================
SUA TAREFA:
============================================================
Gere agora uma QUESTÃO INÉDITA para a habilidade {habilidade_codigo}.
Responda EXCLUSIVAMENTE em formato JSON com as chaves 'enunciado' e 'solver':
{{
  "enunciado": "Texto contextualizado da questão com comando final inequívoco...",
  "solver": "def resolver():\\n    # código com variáveis com os números do enunciado\\n    return {{'correta': ..., 'distratores': [d1, d2, d3, d4]}}"
}}
"""
    return prompt


def build_justificativa_prompt(
    enunciado: str,
    alternativas: Dict[str, str],
    gabarito: str,
    solver_code: Optional[str] = None
) -> str:
    """
    Constrói prompt para a Fase 2 da geração PoT:
    O modelo redige a justificativa pedagógica passo a passo com alternativas e gabarito já fixados por código.
    """
    alts_formatted = "\n".join([f"  {k}) {v}" for k, v in sorted(alternativas.items())])
    correta_valor = alternativas.get(gabarito, "")

    codigo_sec = ""
    if solver_code:
        codigo_sec = f"\nCódigo de Resolução Validado:\n```python\n{solver_code}\n```\n"

    prompt = f"""Você é um Professor Especialista em Avaliação Educacional e Matemática do ENEM.
Sua missão é redigir a JUSTIFICATIVA PEDAGÓGICA de uma questão cujo gabarito oficial já foi matematicamente calculado e comprovado por código.

============================================================
DADOS DA QUESTÃO:
============================================================
Enunciado:
{enunciado}

Alternativas:
{alts_formatted}

Gabarito Oficial Confirmado: Alternativa {gabarito} ({correta_valor})
{codigo_sec}
============================================================
SUA TAREFA:
============================================================
Escreva a justificativa didática demonstrando:
1. A resolução matemática passo a passo que comprova por que a alternativa {gabarito} ({correta_valor}) é a correta;
2. Breve explicação do porquê os distratores representam erros ou passos parciais comuns de estudantes.

Responda EXCLUSIVAMENTE com um JSON no seguinte schema:
{{
  "justificativa": "Texto da resolução passo a passo provando a alternativa {gabarito}..."
}}
"""
    return prompt


