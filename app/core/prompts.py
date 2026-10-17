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
1. ENUNCIADO E ALINHAMENTO À HABILIDADE:
   - Crie uma situação-problema realista com comando final claro e objetivo, avaliando diretamente os conceitos matemáticos da Habilidade Alvo (ex: Geometria, Escala, Funções, Estatística, Grandezas).
   - SEJA CRIATIVO NO CONTEXTO. NUNCA comece as questões sempre com a mesma estrutura sintática. Varie a narrativa e o sujeito!
   - NUNCA use palavras como "solver", "python", "algoritmo", "código", "distrator" ou "gabarito" no enunciado!
2. DADOS TABULARES (OPCIONAL — USE `"tabela_dados": null` POR PADRÃO):
   - Por padrão, defina `"tabela_dados": null` e apresente os dados no texto do enunciado.
   - Use `"tabela_dados"` (entre 2 e 6 linhas no máximo) APENAS quando a questão exigir comparação ou leitura de dados tabulares.
   - Se usar `"tabela_dados"`, NÃO repita os dados da tabela no texto do `enunciado` e garanta que TODAS as colunas numéricas da tabela sejam necessárias no cálculo da resposta `correta` (nunca crie tabelas ou colunas inúteis/decorativas).
3. COMPLEXIDADE, UNICIDADE E EXATIDÃO PADRÃO ENEM:
   - A resolução deve exigir pelo menos 2 etapas de raciocínio encadeadas (evite questões triviais de uma única multiplicação/divisão direta).
   - Se a questão comparar opções ou propostas (ex: "qual o mais econômico"), escolha valores numéricos que NÃO gerem empate entre duas opções.
   - Escolha valores compatíveis para que o resultado final seja inteiro ou decimal exato de até 2 casas. Se usar aproximação de π (ex: considere π = 3 ou π = 3,14), informe isso no enunciado.
4. SOLVER (Python puro):
   - Escreva a função `def resolver():` declarando as variáveis com os mesmos números do enunciado/tabela e calculando passo a passo a resposta final na mesma unidade/escala pedida (ex: se pedir porcentagem, retorne 24 e não 0.24).
   - Calcule 4 distratores plausíveis, positivos e estritamente distintos entre si e distintos de `correta` (representando erros comuns de raciocínio, como parar em uma etapa intermediária).
   - Retorna: return {'correta': <numero>, 'distratores': [<d1>, <d2>, <d3>, <d4>]}
5. NEXO E COMPLETUDE NUMÉRICA:
   - Escreva os dados numéricos em algarismos no `enunciado` ou na `tabela_dados`.
   - Todo número usado no cálculo de `correta` no solver deve constar no `enunciado` ou na `tabela_dados`.
6. COERÊNCIA E INTEGRIDADE FACTUAL:
   - O problema deve ter lógica física e dimensional no mundo real. NUNCA atribua dados inventados a órgãos oficiais reais (como IBGE, OMS, ministérios); use cenários locais ou levantamentos hipotéticos bem definidos.
7. EXCLUSIVIDADE: Gere APENAS o JSON válido, sem comentários antes ou depois.
"""

POT_FEW_SHOT_EXAMPLE = """--- [EXEMPLO DE SAÍDA ESPERADA (FORMATO E NÍVEL DE EXIGÊNCIA)] ---
{
  "enunciado": "Uma cooperativa de reciclagem comercializou, na última semana, 250 kg de alumínio prensado a R$ 6,00 por quilograma e 500 kg de plástico a R$ 3,00 por quilograma. Do valor bruto total arrecadado com a venda desses dois materiais, 20% foram destinados ao pagamento dos custos operacionais de transporte, e o valor líquido restante foi dividido igualmente entre os 8 cooperados da equipe. Qual foi a quantia, em reais, recebida por cada cooperado nessa semana?",
  "tabela_dados": null,
  "solver": "def resolver():\\n    kg_aluminio, preco_aluminio = 250, 6\\n    kg_plastico, preco_plastico = 500, 3\\n    percentual_custo = 20\\n    cooperados = 8\\n    receita_total = kg_aluminio * preco_aluminio + kg_plastico * preco_plastico\\n    valor_liquido = receita_total * (100 - percentual_custo) / 100\\n    valor_por_cooperado = valor_liquido / cooperados\\n    # Distratores baseados em erros comuns\\n    d1 = receita_total / cooperados\\n    d2 = (receita_total * percentual_custo / 100) / cooperados\\n    d3 = valor_liquido\\n    d4 = (kg_aluminio * preco_aluminio) / cooperados\\n    return {'correta': valor_por_cooperado, 'distratores': [d1, d2, d3, d4]}"
}
"""


def build_enunciado_solver_prompt(
    habilidade_codigo: str,
    habilidade_descricao: str,
    competencia: int,
    eixo_tematico: Optional[str] = None,
    exemplos_referencia: Optional[List[Dict[str, Any]]] = None,
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
            gab = str(ex.get("gabarito") or "").strip().upper()
            alts = ex.get("alternativas") if isinstance(ex.get("alternativas"), dict) else {}
            valor_correto = str(alts.get(gab) or alts.get(gab.lower()) or "").strip() if gab else ""

            bloco = (
                f"--- [Questão Histórica do ENEM {idx} para Ancoragem Isomórfica (ENEM {ano})] ---\n"
                f"Enunciado Real: {enun}"
            )
            if valor_correto:
                bloco += f"\nResposta Correta Oficial: {valor_correto}"
            blocos.append(bloco)
        
        ref_text = "\n\n".join(blocos) + "\n\n(Crie uma questão inédita ISOMÓRFICA: com mesma lógica matemática e nível de complexidade das questões acima, porém com um novo contexto do cotidiano e novos dados numéricos)."
    else:
        ref_text = "(Siga estritamente os conceitos pedagógicos da habilidade alvo, respeitando o nível de exigência do ENEM)."

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
(O exemplo acima ilustra apenas o formato JSON esperado: NÃO reutilize seu contexto, seus dados ou sua estrutura narrativa.)

============================================================
SUA TAREFA:
============================================================
Gere agora uma QUESTÃO INÉDITA para a habilidade {habilidade_codigo}.{diretriz_criativa}
Responda EXCLUSIVAMENTE em formato JSON com as chaves 'enunciado', 'tabela_dados' (null por padrão, ou lista de dicts se houver tabela) e 'solver':
{{
  "enunciado": "Texto contextualizado da questão com comando final inequívoco...",
  "tabela_dados": null,
  "solver": "def resolver():\\n    # código com variáveis usando os números do enunciado\\n    return {{'correta': ..., 'distratores': [d1, d2, d3, d4]}}"
}}
"""
    return prompt


def build_blind_solving_prompt(enunciado: str) -> str:
    """
    Constrói prompt para a Chamada 1 da Fase de Validação: Resolução Cega Pura.
    O LLM recebe exclusivamente o enunciado (sem alternativas e sem gabarito)
    e deve resolver o problema passo a passo com rigor conceitual e formal.
    """
    prompt = f"""Você é um especialista resolvendo uma questão de Matemática do ENEM.
Leia atentamente a questão abaixo e resolva-a passo a passo a partir exclusivamente do enunciado.

============================================================
ENUNCIADO DA QUESTÃO:
============================================================
{enunciado}

============================================================
SUA TAREFA:
============================================================
1. Resolva a questão passo a passo de forma clara, direta e objetiva em 'resolucao_passo_a_passo'.
2. Declare em 'resultado_obtido' APENAS o valor final único que responde diretamente à pergunta do comando final:
   - Se a resposta for numérica, retorne APENAS o número final (int ou float, ex: 35.0, 30, 1350), sem unidades de medida, sem texto extra e NUNCA como dicionário de múltiplos grupos.
   - Retorne string apenas quando a pergunta pedir explicitamente um nome, categoria ou horário (ex: "10h00", "Setor A").

Responda EXCLUSIVAMENTE em formato JSON com o schema abaixo:
{{
  "resolucao_passo_a_passo": "Sua resolução passo a passo objetiva deduzindo o resultado...",
  "resultado_obtido": 0
}}
"""
    return prompt


def build_equivalencia_gabarito_prompt(
    resultado_solver: Any,
    resultado_obtido: Any,
    enunciado: Optional[str] = None
) -> str:
    """
    Constrói prompt para a Chamada 2 da Fase de Validação: Confronto Direto de Equivalência.
    Juiz matemático objetivo que confronta o resultado calculado pelo Python com a conclusão da LLM.
    """
    contexto_bloco = ""
    if enunciado:
        contexto_bloco = f"""============================================================
ENUNCIADO DA QUESTÃO (PARA CONTEXTO DA GRANDEZA PEDIDA):
============================================================
{enunciado}

"""

    prompt = f"""Você é um Juiz de Equivalência Matemática e Conceitual.
Sua única função é comparar objetivamente os dois resultados abaixo e determinar se eles expressam a mesma resposta para a pergunta da questão.

{contexto_bloco}============================================================
RESULTADOS A COMPARAR:
============================================================
- Resultado A (Cálculo Oficial do Solver): {resultado_solver}
- Resultado B (Resolução Dedutiva): {resultado_obtido}

============================================================
DIRETRIZES DE EQUIVALÊNCIA:
============================================================
1. Normalize valores numéricos, frações, decimais, porcentagens, arredondamentos próximos e unidades de medida conversíveis (ex: 1350 e 1350.0, 0.5 e "50%", 2500 e "R$ 2.500,00").
2. Se o Resultado B contiver múltiplos valores ou um dicionário (ex: {{'Grupo A': 1350.0, 'Grupo B': 1150.0}}), considere EQUIVALENTE (`true`) caso o valor correspondente ao que foi perguntado no enunciado coincida com o Resultado A.
3. A ausência de unidade de medida em um dos resultados NÃO implica divergência.
4. Retorne `false` apenas quando houver divergência matemática ou conceitual real entre os valores finais.

Responda EXCLUSIVAMENTE em formato JSON com o schema:
{{
  "equivalentes": bool,
  "explicacao_equivalencia": "Explicação objetiva comprovando a equivalência ou apontando a discrepância encontrada"
}}
"""
    return prompt


def build_auditoria_semantica_prompt(
    enunciado: str,
    alternativas: Dict[str, str],
    resolucao_passo_a_passo: Optional[str] = None,
    habilidade_descricao: Optional[str] = None
) -> str:
    """
    Constrói prompt para a Chamada 3 da Fase de Validação: Auditoria Semântica e Pedagógica.
    Avalia a qualidade do item do ENEM (enunciado + resolução + alternativas) identificando eventuais defeitos.
    """
    alts_formatted = "\n".join([f"  {k}) {v}" for k, v in sorted(alternativas.items())])
    
    bloco_hab = ""
    if habilidade_descricao:
        bloco_hab = f"\nHabilidade Avaliada:\n{habilidade_descricao}\n"

    bloco_resolucao = ""
    if resolucao_passo_a_passo:
        bloco_resolucao = f"\nResolução Deduzida (Etapa 1):\n{resolucao_passo_a_passo}\n"

    prompt = f"""Você é um Revisor Técnico e Pedagógico Oficial do INEP para questões do ENEM.
Audite o item de Matemática abaixo avaliando o enunciado, a resolução deduzida e as alternativas.

============================================================
ITEM SUBMETIDO:
============================================================{bloco_hab}
Enunciado:
{enunciado}
{bloco_resolucao}
Alternativas:
{alts_formatted}

============================================================
CRITÉRIOS DE AUDITORIA (IDENTIFICAÇÃO DE PROBLEMAS):
============================================================
Primeiro redija uma breve `analise_critica` verificando se a resolução deduzida e o enunciado fazem sentido, e depois marque `true` APENAS se algum dos defeitos graves abaixo existir claramente (caso contrário, marque `false`):

1. possui_incoerencia: A situação-problema ou o cálculo apresenta erro conceitual/dimensional grave (ex: multiplicar grandezas incompatíveis como lux por horas, dividir custo por dose pelo número de doses por frasco, ou apresentar uma tabela inteira cujos dados são ignorados pela pergunta final)?
2. possui_ambiguidade: O comando final é dúbio OU há empate entre duas opções quando a pergunta pede "o maior / o menor / o mais econômico" (ex: duas opções da tabela empatam com o mesmo custo mínimo)?
3. deficit_informacoes: Falta algum dado numérico indispensável no enunciado (ex: a própria resolução confessa que precisou inventar que a área de uma casa é 1 m² por falta de dados)? (Nota: conversões métricas padrão como 1 m³ = 1.000 L e mês = 30 dias / ano = 12 meses são normais e NÃO são déficit).
4. erros_ou_vazamentos: O texto contém palavras proibidas de bastidor ('solver', 'python', 'código', 'algoritmo', 'distrator')?
5. duplicacao_tabelas: O texto repete integralmente a mesma tabela duas vezes?

Responda EXCLUSIVAMENTE em formato JSON com o schema:
{{
  "analise_critica": "Análise técnica concisa verificando coerência física, ausência de empates e uso dos dados...",
  "possui_incoerencia": bool,
  "possui_ambiguidade": bool,
  "deficit_informacoes": bool,
  "erros_ou_vazamentos": bool,
  "duplicacao_tabelas": bool
}}
"""
    return prompt




