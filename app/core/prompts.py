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


QUERY_REWRITE_SYSTEM_PROMPT = """Você é um especialista em recuperação de informação (RAG) de Matemática para o ENEM.
Sua única tarefa é reescrever a última mensagem do estudante em uma consulta de busca independente, autocontida e otimizada para busca vetorial em materiais didáticos de Matemática.

Diretrizes obrigatórias:
1. Resolva pronomes, elipses e referências ao histórico (ex.: "ele", "essa fórmula", "e se dobrar o raio" -> explicite o conceito ou objeto matemático).
2. Se a mensagem já for independente e autocontida, preserve o conceito matemático central.
3. Se a mensagem for puramente social ou sem conteúdo matemático (ex.: "olá", "obrigado", "tchau"), retorne a própria mensagem.
4. NÃO responda à pergunta do estudante.
5. Retorne EXCLUSIVAMENTE a consulta de busca em uma única linha, sem aspas, explicações, saudações ou prefixos como "Consulta:" ou "Query:"."""


def clean_rewritten_query(raw_text: str, fallback: str) -> str:
    """
    Higieniza a saída do LLM para a consulta reescrita:
    - Remove tags de CoT (<pensamento>, <think>, <resposta>) caso emitidas.
    - Remove prefixos como 'Consulta de busca:', 'Query:', 'Busca:', etc.
    - Remove aspas e quebras de linha excedentes.
    - Garante fallback caso o LLM retorne vazio.
    """
    if not raw_text or not raw_text.strip():
        return fallback.strip()

    text = raw_text.strip()
    text = re.sub(r"<(?:pensamento|think)>.*?(?:</(?:pensamento|think)>|$)", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
    text = re.sub(r"</?(?:resposta|pensamento|think)>", "", text, flags=re.IGNORECASE).strip()

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return fallback.strip()

    first_line = lines[0]
    first_line = re.sub(
        r"^(?:consulta(?: de busca)?|query|busca|reescrita|pergunta reescrita)\s*:\s*",
        "",
        first_line,
        flags=re.IGNORECASE
    ).strip()
    first_line = first_line.strip("\"'`")

    return first_line if first_line else fallback.strip()


def build_query_rewrite_prompt(
    user_message: str,
    history_messages: Optional[List[Dict[str, Any]]] = None,
    max_history_turns: int = 4,
    max_history_chars: int = 250
) -> str:
    """
    Constrói prompt enxuto e objetivo para reescrita de query com resolução de anáforas (Query Rewriting).
    """
    history_lines = []
    if history_messages:
        for msg in history_messages[-max_history_turns:]:
            role = "Estudante" if msg.get("role") == "user" else "Tutora VERA"
            content = str(msg.get("content", "")).strip()
            trimmed = content[:max_history_chars] + ("..." if len(content) > max_history_chars else "")
            history_lines.append(f"{role}: {trimmed}")

    history_str = "\n".join(history_lines) if history_lines else "(Sem histórico prévio)"

    return f"""{QUERY_REWRITE_SYSTEM_PROMPT}

Histórico recente:
{history_str}

Última mensagem do estudante:
{user_message.strip()}

Consulta de busca reescrita:"""


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



TEMAS_COTIDIANO: List[str] = [
    "Saúde pública, medicina ou nutrição",
    "Práticas esportivas, atletas ou competições",
    "Mobilidade urbana, transporte coletivo ou trânsito",
    "Energia renovável, consumo elétrico ou sustentabilidade",
    "Economia doméstica, planejamento financeiro ou compras",
    "Recursos hídricos, meio ambiente ou meteorologia",
    "Agropecuária, produção de alimentos ou cultivo",
    "Tecnologia da informação, telecomunicações ou dados",
    "Comércio, varejo ou gestão de estoque",
    "Planejamento urbano, saneamento ou habitação",
]

FORMAS_ABERTURA: List[str] = [
    "Inicie apresentando o resultado de uma pesquisa amostral ou levantamento local (ex: 'Em uma pesquisa com 400 clientes...', 'Um levantamento sobre o consumo de água em um condomínio revelou...')",
    "Inicie contextualizando o cenário territorial ou comunitário (ex: 'Em um município...', 'Para interligar dois distritos agrícolas...', 'Uma cooperativa local...')",
    "Inicie descrevendo um processo técnico, produtivo ou logístico (ex: 'Uma linha de envase industrial...', 'Um centro de distribuição organiza o transporte...')",
    "Inicie com uma situação prática de tomada de decisão financeira ou orçamento (ex: 'Um consumidor compara duas opções de parcelamento...', 'Para o orçamento de uma reforma...')",
    "Inicie apresentando um ensaio técnico, medição laboratorial ou monitoramento periódico (ex: 'Durante o monitoramento da vazão de um reservatório...', 'Em um teste de rendimento térmico...')",
    "Inicie relatando o regulamento de uma competição, sistema de pontuação ou evento recreativo (ex: 'Em um torneio escolar...', 'Uma gincana comunitária...')",
    "Inicie com o dimensionamento de um projeto de arquitetura, embalagem ou armazenamento (ex: 'Uma fábrica projeta uma embalagem cilíndrica...', 'O projeto de um galpão de armazenamento...')",
]


def sortear_contexto_criativo() -> Tuple[str, str]:
    """
    Sorteia aleatoriamente um tema do cotidiano e uma estrutura narrativa de abertura
    para diversificar os enunciados e quebrar vícios sintáticos na LLM.
    """
    import random
    return random.choice(TEMAS_COTIDIANO), random.choice(FORMAS_ABERTURA)



# ==============================================================================
# PROMPTS PARA ARQUITETURA PROGRAM-AIDED (PoT: ENUNCIADO + SOLVER EM PYTHON)
# ==============================================================================

POT_QUESTION_GENERATOR_SYSTEM_PROMPT = """Você é um Elaborador de Itens de Matemática para o ENEM.
Gere uma QUESTÃO INÉDITA estruturada em JSON (enunciado + solver em Python).
O solver calculará a resposta correta e 4 distratores; NÃO gere gabarito ou letras A-E.

REGRAS ESTRITAS:
1. ENUNCIADO: Situação-problema realista com comando final claro.
   - SEJA CRIATIVO NO CONTEXTO. NUNCA comece as questões sempre com a mesma estrutura sintática. Varie a narrativa e o sujeito!
   - NUNCA use palavras como "solver", "python", "algoritmo", "código", "distrator" ou "gabarito" no enunciado!
2. FORMATAÇÃO DE TABELAS:
   - Se o problema envolver dados tabulares ou anunciar uma tabela ("tabela a seguir", "quadro abaixo", etc.), NUNCA tente formatá-la em Markdown no enunciado.
   - Em vez disso, coloque APENAS os dados estruturados no campo JSON 'tabela_dados' (lista de dicionários). O sistema desenhará a tabela para você.
3. SOLVER (Python puro): 
   - Modela os cálculos da grandeza solicitada no enunciado.
   - Retorna: return {'correta': <numero>, 'distratores': [<d1>, <d2>, <d3>, <d4>]}
4. NEXO E COMPLETUDE: Todo dado ou número usado no solver (exceto constantes universais) DEVE estar visível no texto do enunciado ou na tabela_dados.
5. COERÊNCIA FÍSICA E MATEMÁTICA: O problema deve ser factível e ter lógica no mundo real.
6. INTEGRIDADE FACTUAL: NUNCA invente notícias de veículos de imprensa, nomes de pesquisadores ou dados atribuídos falsamente a órgãos oficiais reais (como IBGE, OMS, ministérios). Quando o problema envolver dados percentuais ou estatísticos, contextualize-os como cenários hipotéticos bem definidos ou pesquisas amostrais locais (ex: 'Uma pesquisa de satisfação em uma loja com 400 clientes...', 'Um levantamento sobre o consumo elétrico em um condomínio...').
7. EXCLUSIVIDADE: Gere APENAS o JSON válido, sem comentários antes ou depois.
"""

POT_FEW_SHOT_EXAMPLE = """--- [EXEMPLO DE SAÍDA ESPERADA (FORMATO OBRIGATÓRIO)] ---
{
  "enunciado": "Seu texto contextualizado aqui terminando com uma pergunta clara...",
  "tabela_dados": [
    {"Produto": "A", "Preço": 10.00},
    {"Produto": "B", "Preço": 20.00}
  ],
  "solver": "def resolver():\\n    # cálculos baseados nos dados numéricos do enunciado\\n    # ...\\n    return {'correta': valor_correto, 'distratores': [d1, d2, d3, d4]}"
}
"""


def build_enunciado_solver_prompt(
    habilidade_codigo: str,
    habilidade_descricao: str,
    competencia: int,
    eixo_tematico: Optional[str] = None,
    exemplos_referencia: Optional[List[Dict[str, Any]]] = None,
    feedback_erro: Optional[str] = None,
    tema: Optional[str] = None,
    abertura: Optional[str] = None
) -> str:
    """
    Constrói prompt estruturado para a Fase 1 da geração PoT (Enunciado + Solver em Python).
    """
    ref_text = ""
    if exemplos_referencia:
        blocos = []
        for idx, ex in enumerate(exemplos_referencia, 1):
            ano = ex.get("ano", "ENEM")
            enun = ex.get("enunciado", "").strip()
            gab = ex.get("gabarito", "")
            bloco = (
                f"--- [Questão Histórica do ENEM {idx} para Ancoragem Isomórfica (ENEM {ano})] ---\n"
                f"Enunciado Real: {enun}\n"
                f"Gabarito Oficial: {gab}"
            )
            blocos.append(bloco)
        
        ref_text = "\n\n".join(blocos) + "\n\n(Crie uma questão inédita ISOMÓRFICA: com mesma lógica matemática e nível de complexidade das questões acima, porém com um novo contexto do cotidiano e novos dados numéricos)."
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

    diretriz_criativa = ""
    if tema or abertura:
        linhas_criativas = []
        if tema:
            linhas_criativas.append(f"- Contexto temático sugerido: {tema}.")
        if abertura:
            linhas_criativas.append(f"- Abertura narrativa: {abertura}. (Evite começar com 'Um [profissional] está...').")
        diretriz_criativa = "\n" + "\n".join(linhas_criativas)

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
Gere agora uma QUESTÃO INÉDITA para a habilidade {habilidade_codigo}.{diretriz_criativa}
Responda EXCLUSIVAMENTE em formato JSON com as chaves 'enunciado', 'tabela_dados' (opcional) e 'solver':
{{
  "enunciado": "Texto contextualizado da questão com comando final inequívoco...",
  "tabela_dados": [{{"Coluna1": "A", "Coluna2": 10}}],
  "solver": "def resolver():\\n    # código com variáveis com os números do enunciado\\n    return {{'correta': ..., 'distratores': [d1, d2, d3, d4]}}"
}}
"""
    return prompt


def build_auto_validation_prompt(
    enunciado: str,
    alternativas: Dict[str, str],
    gabarito: str
) -> str:
    """
    Constrói prompt para a Fase de Auto-Validação da Geração PoT.
    A LLM deve resolver a questão gerada (sem saber que foi ela mesma quem gerou)
    para atestar a qualidade e apontar qualquer falha (ambiguidade, erro).
    """
    alts_formatted = "\n".join([f"  {k}) {v}" for k, v in sorted(alternativas.items())])
    
    prompt = f"""Você é um Revisor Técnico e Pedagógico Oficial do INEP para questões do ENEM.
Uma questão foi submetida e precisa ser rigidamente avaliada antes de ir para os alunos.

============================================================
QUESTÃO SUBMETIDA:
============================================================
Enunciado:
{enunciado}

Alternativas Disponíveis:
{alts_formatted}

Gabarito Pretendido pela Banca: {gabarito}

============================================================
SUA TAREFA DE AVALIAÇÃO:
============================================================
Analise a questão criticamente e resolva-a passo a passo na sua justificativa_resolucao.
Você DEVE verificar rigorosamente:
1. Faz sentido semanticamente e tem coerência matemática/lógica?
2. O texto está livre de qualquer ambiguidade ou comando duplo?
3. Há informações suficientes para resolver ou falta algum dado numérico?
4. O texto está livre de erros de português e livre de "vazamentos de prompt" (palavras absurdas para um aluno como: solver, python, código, distratores, gerar)?
5. Ao você resolver passo a passo, a resposta exata se encontra nas alternativas, e corresponde ao gabarito pretendido?

Se houver QUALQUER erro, seja implacável. Marque 'aprovada' como false e escreva em 'feedback_correcao' exatamente o que quem elaborou a questão precisa consertar no enunciado ou na lógica.

Responda EXCLUSIVAMENTE em formato JSON contendo exatamente as chaves do schema abaixo. Não coloque nenhum texto fora do JSON.
Schema esperado:
{{
  "faz_sentido_semanticamente": bool,
  "sem_ambiguidade": bool,
  "informacao_suficiente": bool,
  "sem_erros_vazamentos": bool,
  "resposta_nas_alternativas": bool,
  "justificativa_resolucao": "Sua resolução passo a passo detalhada",
  "feedback_correcao": "O que corrigir (se houver erro), senao null",
  "aprovada": bool
}}
"""
    return prompt


def build_correction_prompt(
    habilidade_codigo: str,
    habilidade_descricao: str,
    enunciado_anterior: str,
    solver_anterior: str,
    feedback_erro: str
) -> str:
    """
    Constrói prompt de Correção (Stateful Correction).
    Em vez de recriar do zero, pede para a LLM consertar o que deu errado com base no feedback.
    """
    prompt = f"""Você é um Elaborador de Itens de Matemática para o ENEM.
Você produziu uma QUESTÃO INÉDITA estruturada em JSON (enunciado + solver em Python).
No entanto, a sua questão foi rejeitada na revisão rigorosa.

============================================================
ESPECIFICAÇÃO DA HABILIDADE ALVO:
============================================================
- Código: {habilidade_codigo}
- Descrição: {habilidade_descricao}

============================================================
O QUE VOCÊ PRODUZIU ANTERIORMENTE:
============================================================
ENUNCIADO:
{enunciado_anterior}

SOLVER PYTHON:
{solver_anterior}

============================================================
FEEDBACK DA REVISÃO (ERRO ENCONTRADO):
============================================================
{feedback_erro}

============================================================
SUA TAREFA DE CORREÇÃO:
============================================================
Modifique o ENUNCIADO e/ou o SOLVER APENAS O SUFICIENTE para corrigir o problema apontado na revisão.
Mantenha o mesmo contexto original o máximo possível. Lembre-se que o solver calcula e retorna {{'correta': ..., 'distratores': [...]}}.

Responda EXCLUSIVAMENTE em formato JSON com as chaves 'enunciado', 'tabela_dados' (opcional) e 'solver':
{{
  "enunciado": "Novo texto contextualizado já corrigido...",
  "tabela_dados": [{{"Coluna1": "A", "Coluna2": 10}}],
  "solver": "def resolver():\\n    # lógica em python corrigida\\n    return {{'correta': ..., 'distratores': [d1, d2, d3, d4]}}"
}}
"""
    return prompt


