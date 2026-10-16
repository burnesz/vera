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
2. DADOS TABULARES E ISOLAMENTO DE TABELA:
   - Se a questão envolver dados tabulares ou anunciar uma tabela ("A tabela a seguir apresenta...", "O quadro abaixo ilustra..."), no campo 'enunciado' escreva APENAS a contextualização anunciando a tabela e a pergunta final.
   - NUNCA liste os dados da tabela no corpo do 'enunciado' (seja em tópicos '-', listas numeradas, parágrafos ou pipes '|'). O texto NÃO deve conter os dados repetidos.
   - Os dados tabulares devem residir EXCLUSIVAMENTE no campo JSON 'tabela_dados' (lista de dicionários). O sistema desenhará e renderizará a tabela para o aluno no ponto adequado.
3. COMPLEXIDADE PADRÃO ENEM (OBRIGATÓRIO):
   - A resolução deve exigir NO MÍNIMO 2 etapas de raciocínio encadeadas, em que o resultado de uma etapa alimenta a seguinte.
   - Mobilize pelo menos 2 conceitos matemáticos articulados (ex: proporcionalidade + conversão de unidades; porcentagem + comparação de opções; área + custo; média + variação percentual).
   - O aluno deve INTERPRETAR o texto e/ou a tabela para selecionar e relacionar os dados relevantes; a operação necessária NÃO pode estar entregue literalmente no comando.
   - PROIBIDO: questões resolvidas com uma única operação direta (ex: apenas somar os valores de uma coluna, aplicar uma única porcentagem, ler um valor da tabela).
4. PREMISSAS EXPLÍCITAS E ARREDONDAMENTO (NENHUMA SUPOSIÇÃO IMPLÍCITA):
   - Toda convenção, valor de referência ou hipótese necessária ao cálculo DEVE estar escrita no enunciado, preferencialmente em uma frase iniciada por "Considere que...".
   - Declare SEMPRE, quando usados: quantidade de dias do mês ou do ano, semanas por mês, dias úteis ou jornada de trabalho, regime de juros (simples ou composto), critério de arredondamento, valor aproximado de π, equivalência entre litro e metro cúbico, densidades, e a constância de taxas, vazões ou velocidades.
   - EXATIDÃO NUMÉRICA E CASAS DECIMAIS: Priorize escolher valores numéricos múltiplos e compatíveis para que as divisões resultem em números inteiros ou decimais exatos de até 2 casas (evitando dízimas periódicas). Caso o cálculo não seja exato ou o solver utilize arredondamento (`round`, `math.ceil`, `math.floor`), o comando final do enunciado DEVE especificar explicitamente quantas casas decimais ou qual critério usar (ex: "Considere o resultado arredondado para duas casas decimais" ou "aproxime para uma casa decimal"). NUNCA arredonde no solver sem declarar o número exato de casas decimais no enunciado.
   - Termos de periodicidade ("mensal", "semanal", "anual", "diário") NUNCA podem ser convertidos no cálculo sem que a conversão esteja declarada (ex: escreva "Considere que o mês tem 30 dias").
   - Apenas conversões universais e inequívocas dispensam declaração: 1 h = 60 min, 1 min = 60 s, 1 dia = 24 h, 1 ano = 12 meses e prefixos métricos (1 m = 100 cm, 1 kg = 1.000 g).
5. SOLVER (Python puro — PROIBIDO PULAR PASSOS):
   - Inicie `def resolver():` declarando variáveis de entrada atribuídas EXATAMENTE aos números brutos que aparecem no enunciado ou na `tabela_dados`.
   - NUNCA faça pré-cálculos de cabeça ao escrever o código (ex: se o enunciado informa diâmetro 40, escreva `diametro = 40` e `raio = diametro / 2`, NUNCA escreva direto `raio = 20`; se o enunciado informa 80%, escreva `percentual = 80` e `complementar = (100 - percentual) / 100`, NUNCA escreva direto `20` ou `0.2`). Toda operação intermediária deve estar explícita no Python.
   - Modela, passo a passo e com variáveis intermediárias nomeadas, os cálculos da grandeza solicitada no enunciado.
   - Os 4 distratores devem modelar ERROS TÍPICOS de raciocínio do aluno (parar em uma etapa intermediária, esquecer uma conversão, usar apenas parte dos dados, inverter uma operação). NÃO use variações arbitrárias como "+50" ou "*1.2".
   - Retorna: return {'correta': <numero>, 'distratores': [<d1>, <d2>, <d3>, <d4>]}
6. NEXO E COMPLETUDE NUMÉRICA:
   - No `enunciado`, escreva todos os dados numéricos em ALGARISMOS ARÁBICOS (ex: `20`, `40`, `30`), nunca apenas por extenso ("vinte", "quarenta").
   - Todo número literal usado no cálculo de `correta` no solver (exceto as conversões universais da regra 4) DEVE constar identicamente no texto do `enunciado` ou na `tabela_dados`, inclusive os valores das premissas (ex: o `30` de "mês com 30 dias"). Os números contidos em `tabela_dados` são considerados 100% visíveis e válidos pelo validador de nexo numérico.
7. COERÊNCIA FÍSICA E MATEMÁTICA: O problema deve ser factível e ter lógica no mundo real.
8. INTEGRIDADE FACTUAL: NUNCA invente notícias de veículos de imprensa, nomes de pesquisadores ou dados atribuídos falsamente a órgãos oficiais reais (como IBGE, OMS, ministérios). Quando o problema envolver dados percentuais ou estatísticos, contextualize-os como cenários hipotéticos bem definidos ou pesquisas amostrais locais (ex: 'Uma pesquisa de satisfação em uma loja com 400 clientes...', 'Um levantamento sobre o consumo elétrico em um condomínio...').
9. EXCLUSIVIDADE: Gere APENAS o JSON válido, sem comentários antes ou depois.
"""

POT_FEW_SHOT_EXAMPLE = """--- [EXEMPLO DE SAÍDA ESPERADA (FORMATO E NÍVEL DE EXIGÊNCIA OBRIGATÓRIOS)] ---
(Observe: declaração explícita dos dados brutos do enunciado sem pular passos, 3 etapas encadeadas — vazão total, volume mensal com conversão de unidade, custo —, premissas declaradas com "Considere que..." e distratores que modelam erros típicos.)
{
  "enunciado": "Uma cooperativa de agricultura familiar irriga sua estufa com um sistema de gotejamento dividido em dois setores. A tabela a seguir apresenta a quantidade de gotejadores de cada setor e a vazão de cada gotejador. O sistema funciona 3 horas por dia, todos os dias, e a companhia de abastecimento cobra R$ 4,50 por metro cúbico de água consumido. Considere que o mês tem 30 dias, que 1 metro cúbico corresponde a 1.000 litros e que a vazão dos gotejadores permanece constante. Qual será o gasto mensal, em reais, da cooperativa com a água utilizada na irrigação?",
  "tabela_dados": [
    {"Setor": "A", "Quantidade de gotejadores": 200, "Vazão por gotejador (L/h)": 2},
    {"Setor": "B", "Quantidade de gotejadores": 150, "Vazão por gotejador (L/h)": 4}
  ],
  "solver": "def resolver():\\n    # Dados brutos do enunciado e da tabela (sem pular etapas)\\n    gotejadores_a, vazao_a = 200, 2\\n    gotejadores_b, vazao_b = 150, 4\\n    horas_por_dia = 3\\n    dias_mes = 30\\n    litros_por_m3 = 1000\\n    tarifa_m3 = 4.5\\n    # Etapas de calculo encadeadas\\n    vazao_total_l_h = gotejadores_a * vazao_a + gotejadores_b * vazao_b\\n    volume_diario_l = vazao_total_l_h * horas_por_dia\\n    volume_mensal_l = volume_diario_l * dias_mes\\n    custo_mensal = (volume_mensal_l / litros_por_m3) * tarifa_m3\\n    # Erro 1: calcula apenas o custo diario (esquece o fator mensal)\\n    d1 = (volume_diario_l / litros_por_m3) * tarifa_m3\\n    # Erro 2: considera apenas o setor A\\n    d2 = (gotejadores_a * vazao_a * horas_por_dia * dias_mes / litros_por_m3) * tarifa_m3\\n    # Erro 3: esquece as horas de funcionamento diario\\n    d3 = (vazao_total_l_h * dias_mes / litros_por_m3) * tarifa_m3\\n    # Erro 4: nao converte litros para metros cubicos\\n    d4 = volume_mensal_l * tarifa_m3\\n    return {'correta': custo_mensal, 'distratores': [d1, d2, d3, d4]}"
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
        
        ref_text = "\n\n".join(blocos) + "\n\n(Crie uma questão inédita ISOMÓRFICA: com mesma lógica matemática e nível de complexidade das questões acima, porém com um novo contexto do cotidiano e novos dados numéricos. NUNCA simplifique: a questão inédita deve exigir tantas etapas e tanta interpretação quanto as de referência)."
    else:
        ref_text = "(Siga estritamente os conceitos pedagógicos da habilidade alvo, respeitando o nível de exigência do ENEM)."

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
(O exemplo acima ilustra apenas formato e nível de exigência: NÃO reutilize seu contexto, seus dados ou sua estrutura narrativa.)
{secao_feedback}
============================================================
SUA TAREFA:
============================================================
Gere agora uma QUESTÃO INÉDITA para a habilidade {habilidade_codigo}.{diretriz_criativa}
Antes de responder, confira mentalmente:
- [Complexidade] A resolução exige pelo menos 2 etapas encadeadas e 2 conceitos? Se bastar uma única operação, torne a situação mais rica.
- [Premissas] Cada convenção usada no solver (dias do mês/ano, regime de juros, arredondamento, π, litro/m³, constância de taxas) está escrita no enunciado com "Considere que..."?
- [Nexo sem Pulo de Passos] Todos os números do solver foram declarados a partir dos algarismos exatos do enunciado/tabela, sem fazer contas de cabeça (como metade, complemento percentual ou conversão prévia)?
Responda EXCLUSIVAMENTE em formato JSON com as chaves 'enunciado', 'tabela_dados' (opcional) e 'solver':
{{
  "enunciado": "Texto contextualizado da questão, com as premissas declaradas e comando final inequívoco...",
  "tabela_dados": [{{"Coluna1": "A", "Coluna2": 10}}],
  "solver": "def resolver():\\n    # 1. Declare variáveis com os números brutos do enunciado/tabela (sem pular passos)\\n    # 2. Calcule as etapas intermediárias explicitamente\\n    return {{'correta': ..., 'distratores': [d1, d2, d3, d4]}}"
}}
"""
    return prompt


def build_blind_solving_prompt(enunciado: str) -> str:
    """
    Constrói prompt para a Chamada 1 da Fase de Validação: Resolução Cega Pura.
    O LLM recebe exclusivamente o enunciado (sem alternativas e sem gabarito)
    e deve resolver o problema passo a passo com rigor conceitual e formal.
    """
    prompt = f"""Você é um estudante de alto desempenho resolvendo uma questão de Matemática do ENEM.
Leia atentamente a questão abaixo e resolva-a de forma autônoma, passo a passo, a partir exclusivamente do enunciado.

============================================================
ENUNCIADO DA QUESTÃO:
============================================================
{enunciado}

============================================================
SUA TAREFA:
============================================================
1. Resolva a questão passo a passo com rigor lógico e matemático formal.
2. Apresente toda a resolução didática detalhada em 'resolucao_passo_a_passo'.
3. Liste em 'premissas_assumidas' TODA suposição, convenção ou valor que você precisou adotar e que NÃO está escrito explicitamente no enunciado. Exemplos:
   - "Assumi que o mês tem 30 dias" (quando o enunciado diz apenas "mensal").
   - "Assumi que o ano tem 365 dias", "Assumi 4 semanas por mês", "Assumi juros compostos", "Assumi π = 3,14", "Assumi que 1 m³ = 1.000 L", "Assumi arredondamento para cima".
   - NÃO liste conversões universais e inequívocas: 1 h = 60 min, 1 min = 60 s, 1 dia = 24 h, 1 ano = 12 meses e prefixos métricos (1 m = 100 cm, 1 kg = 1.000 g).
   - NÃO liste informações que estão escritas no enunciado.
   - Se não precisou assumir nada, retorne uma lista vazia [].
4. Deduza e declare o resultado final em 'resultado_obtido' no formato de um TIPO PRIMÁRIO DO PYTHON:
   - Se for um valor numérico único, retorne apenas o número (int ou float, ex: 35.0, 30, 1.9), sem texto ou unidades de medida.
   - Se for uma conclusão conceitual, retorne em texto.
   - Se forem múltiplos valores, retorne como dict (ex: {{"media": 135.0, "moda": None}}).

Responda EXCLUSIVAMENTE em formato JSON com o schema abaixo:
{{
  "resolucao_passo_a_passo": "Sua resolução didática e detalhada passo a passo deduzindo o resultado...",
  "premissas_assumidas": ["Cada suposição não declarada no enunciado, ou lista vazia"],
  "resultado_obtido": "Valor numérico ou conclusão final obtida no tipo primário do Python"
}}
"""
    return prompt


def build_equivalencia_gabarito_prompt(resultado_solver: Any, resultado_obtido: Any) -> str:
    """
    Constrói prompt para a Chamada 2 da Fase de Validação: Confronto Direto de Equivalência.
    Juiz matemático objetivo que confronta o resultado calculado pelo Python com a conclusão da LLM.
    """
    prompt = f"""Você é um Juiz de Equivalência Matemática e Conceitual.
Sua única função é comparar objetivamente os dois resultados abaixo e determinar se eles expressam a mesma resposta matemática/conceitual.

============================================================
RESULTADOS A COMPARAR:
============================================================
- Resultado A (Cálculo do Solver): {resultado_solver}
- Resultado B (Resolução Dedutiva): {resultado_obtido}

============================================================
DIRETRIZES DE EQUIVALÊNCIA:
============================================================
1. Antes de comparar, normalize os valores, as representações matemáticas e as unidades de medida.
2. Considere equivalentes diferenças de formatação, notação, frações, decimais e unidades conversíveis.
3. A ausência de unidade em um resultado não implica divergência, desde que o valor e o contexto sejam compatíveis.
4. Considere o enunciado para verificar a grandeza esperada. Não invente informações nem converta grandezas incompatíveis.
5. Retorne `false` apenas quando houver divergência matemática ou conceitual real. Se as informações forem insuficientes, explique a limitação objetivamente e decida com base nas evidências disponíveis.

Responda EXCLUSIVAMENTE em formato JSON com o schema:
{{
  "equivalentes": bool,
  "explicacao_equivalencia": "Explicação objetiva comprovando a equivalência ou apontando a discrepância encontrada"
}}
"""
    return prompt


def build_auditoria_semantica_prompt(enunciado: str, alternativas: Dict[str, str]) -> str:
    """
    Constrói prompt para a Chamada 3 da Fase de Validação: Auditoria Semântica e Pedagógica.
    Avalia a qualidade do item do ENEM (enunciado + alternativas) identificando eventuais problemas ou defeitos.
    """
    alts_formatted = "\n".join([f"  {k}) {v}" for k, v in sorted(alternativas.items())])
    
    prompt = f"""Você é um Revisor Técnico e Pedagógico Oficial do INEP para questões do ENEM.
Audite o item de Matemática abaixo avaliando rigorosamente a presença de eventuais problemas pedagógicos ou textuais.

============================================================
ITEM SUBMETIDO:
============================================================
Enunciado:
{enunciado}

Alternativas:
{alts_formatted}

============================================================
CRITÉRIOS DE AUDITORIA (IDENTIFICAÇÃO DE PROBLEMAS):
============================================================
Avalie se o item apresenta algum dos seguintes problemas (marque true se o problema existir, false se o item estiver perfeito):

1. possui_incoerencia: A situação-problema é absurda, incoerente com o mundo real ou tem erro conceitual grave?
2. possui_ambiguidade: O comando final é dúbio, confuso ou possui dupla interpretação?
3. deficit_informacoes: Faltam informações, dados numéricos essenciais ou contexto indispensável para resolver a questão? Marque true também se a resolução depender de alguma CONVENÇÃO NÃO DECLARADA no enunciado (ex: tratar "mensal" como 30 dias, "anual" como 365 dias, supor juros simples ou compostos, adotar um valor de π, um critério de arredondamento ou a relação litro/m³ sem que estejam escritos). Conversões universais (1 h = 60 min, 1 dia = 24 h, 1 ano = 12 meses, prefixos métricos) NÃO precisam ser declaradas.
4. erros_ou_vazamentos: O texto contém erros de português ou palavras proibidas de bastidor ('solver', 'python', 'código', 'algoritmo', 'distrator')?
5. duplicacao_tabelas: O texto repete desnecessariamente dados de tabelas em tópicos/texto corrido além da própria tabela formatada?

Responda EXCLUSIVAMENTE em formato JSON com o schema:
{{
  "possui_incoerencia": bool,
  "possui_ambiguidade": bool,
  "deficit_informacoes": bool,
  "erros_ou_vazamentos": bool,
  "duplicacao_tabelas": bool
}}
"""
    return prompt



