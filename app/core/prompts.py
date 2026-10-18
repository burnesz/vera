"""
Módulo de Prompts Estruturados da Plataforma VERA.
Versionamento e formatação de prompts conversacionais com Chain-of-Thought (CoT) para a Tutora Especialista em Matemática do ENEM.
"""

import re
import random
from collections import deque
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


# ==============================================================================
# DIVERSIDADE DE CONTEXTO
# ==============================================================================

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

_TEMAS_RECENTES: "deque[str]" = deque(maxlen=4)
_ABERTURAS_RECENTES: "deque[str]" = deque(maxlen=3)


def sortear_contexto_criativo() -> Tuple[str, str]:
    """
    Sorteia um tema do cotidiano e uma estrutura narrativa de abertura,
    evitando repetir os últimos sorteados no mesmo processo.
    """
    temas = [t for t in TEMAS_COTIDIANO if t not in _TEMAS_RECENTES] or TEMAS_COTIDIANO
    aberturas = [a for a in FORMAS_ABERTURA if a not in _ABERTURAS_RECENTES] or FORMAS_ABERTURA
    tema, abertura = random.choice(temas), random.choice(aberturas)
    _TEMAS_RECENTES.append(tema)
    _ABERTURAS_RECENTES.append(abertura)
    return tema, abertura


# ==============================================================================
# PROMPTS PARA ARQUITETURA PROGRAM-AIDED (PoT: ENUNCIADO + SOLVER EM PYTHON)
# ==============================================================================

POT_QUESTION_GENERATOR_SYSTEM_PROMPT = """Você é um Elaborador de Itens de Matemática para o ENEM.
Gere uma QUESTÃO INÉDITA em JSON: planejamento + enunciado + (tabela opcional) + solver em Python.
O solver calcula a resposta correta e 4 distratores. NÃO gere letras A-E nem gabarito.

=== REGRAS (em ordem de importância) ===

1. A PERGUNTA FINAL SEMPRE PEDE UM NÚMERO.
   As alternativas serão 5 valores numéricos. Portanto o comando final deve pedir uma quantidade, valor, média, percentual, área etc.
   NUNCA pergunte "qual plano", "qual embalagem", "qual opção é mais vantajosa" (a resposta seria um nome, não um número).
   RUIM: "Qual plano será mais econômico?" (alternativas: 190, 205, 185...)
   BOM:  "Qual é o custo total, em reais, do plano mais econômico?"
   Informe sempre a unidade pedida no comando final (reais, litros, km, %...).

2. NÍVEL MÍNIMO: pelo menos 2 ETAPAS DE RACIOCÍNIO.
   PROIBIDO: apenas somar uma coluna, apenas ler um valor da tabela, ou aplicar uma única fórmula direta.
   Exemplos de etapas: converter unidades, calcular uma média ponderada, aplicar porcentagem sobre porcentagem,
   comparar duas opções e então calcular a diferença, usar proporção/regra de três, calcular área e depois custo.
   RUIM: "Qual foi a quantidade total de papel recolhida nos três dias?" (só somar)
   BOM:  "Qual é o custo total para encher a piscina, sabendo que ela é um bloco retangular e que cada m³ custa R$ X?"

3. NENHUMA INFORMAÇÃO OCULTA (premissa implícita).
   O aluno precisa conseguir resolver SÓ com o que está escrito.
   - Se pedir "por hectare", "por pessoa", "por viagem", o enunciado deve dar a base (a área, o número de pessoas...).
   - Se a tabela tiver percentuais, diga de QUÊ cada percentual é (ex.: "percentual dos moradores de cada faixa etária") e
     informe o tamanho de cada grupo, para permitir a média ponderada.
   - Se o resultado não for exato, o enunciado deve dizer como arredondar. Prefira dados que deem resultado exato ou com no máximo 2 casas decimais exatas (evite dízimas como 2766,666...).

4. TODO DADO DEVE TER FUNÇÃO.
   Cada número do enunciado/tabela deve ser usado no cálculo. Máximo de UMA coluna/linha extra de distração, e somente se for relevante ao contexto.
   Não cite tempos, medidas ou valores que não entram em nenhuma regra de cálculo.
   RUIM: listar os tempos de um atleta e dar uma tabela de pontos fixos por prova (os tempos não são usados).

5. CONSISTÊNCIA ENTRE TEXTO E TABELA.
   Se o texto citar um total (ex.: "trajeto de 15 km"), a tabela deve somar exatamente esse total. Se citar "uma semana", a tabela deve ter 7 dias (ou diga "nos cinco primeiros dias" de forma coerente).
   Se o texto citar quantidade de itens (ex.: "10 estações"), a tabela deve ter exatamente essa quantidade de linhas/trechos.

6. VEROSSIMILHANÇA NUMÉRICA E LÓGICA. Use ordens de grandeza reais:
   - consumo residencial de água: 100 a 250 litros por pessoa por dia (NUNCA 4 ou 5 litros por casa)
   - tempo de 50 m livre: 22 a 35 segundos (use SEGUNDOS, não minutos decimais); 100 m livre: 48 a 70 s
   - corrida de bicicleta (etapa): 40 a 200 km; ônibus urbano: tarifa de R$ 4 a R$ 6
   - treino: use "calorias GASTAS" (consumir calorias = ingerir)
   - esporte e equipamento devem combinar (nada de capacete no futebol de campo; use ciclismo, skate, etc.)
   - tabelas devem ter dados IRREGULARES, não progressões aritméticas óbvias (20, 25, 30, 35).
   Use palavras exatas: a pergunta só pode falar de "dia", "semana", "mês" se a tabela falar do mesmo período.

7. DISTRATORES = ERROS TÍPICOS DE ALUNOS (nunca fórmula aleatória).
   PROIBIDO: correta ± valor fixo, correta × 0,8, correta × 1,2, correta × 1,1 ou × 0,9.
   Cada distrator deve ser calculado por uma VARIÁVEL com nome do erro. Exemplos de erros reais:
   - média simples no lugar da ponderada; esquecer uma linha/grupo; trocar os pesos
   - somar percentuais em vez de aplicar em sequência; aplicar o percentual sobre a base errada
   - dividir pelo número errado de itens; esquecer de converter unidade (m para cm, min para s)
   - responder só a etapa intermediária; confundir área com perímetro; inverter a razão
   Os 4 distratores devem ser números DIFERENTES entre si e da correta, positivos, com a mesma unidade e a mesma quantidade de casas decimais da correta, sem decimais sem sentido para contagens (não existe 104,4 camisas).

8. TABELA: ISOLAMENTO.
   Se usar tabela, no 'enunciado' escreva só o contexto, o anúncio ("A tabela a seguir apresenta...") e a pergunta.
   NUNCA repita os dados da tabela no enunciado (nem em listas, nem em texto corrido, nem com pipes '|').
   Os dados ficam SOMENTE em 'tabela_dados' (lista de dicionários, números em formato JSON: ponto decimal, sem aspas).
   Pode haver questão SEM tabela: nesse caso omita 'tabela_dados' e coloque todos os dados no enunciado.

9. SOLVER: Python puro, função resolver().
   - Declare no início uma variável para cada dado do enunciado/tabela (ex.: preco_original = 250).
   - Nunca use números que não estejam no enunciado ou na tabela (exceto constantes universais, como 100 em porcentagem).
   - Retorna: return {'correta': <número>, 'distratores': [<d1>, <d2>, <d3>, <d4>]}
   - Use round(x, 2) quando necessário.

10. PROIBIDO no enunciado: as palavras "solver", "python", "algoritmo", "código", "distrator", "gabarito".

11. INTEGRIDADE FACTUAL: não invente notícias, pesquisadores nem dados atribuídos a órgãos reais (IBGE, OMS, ministérios).
    Use cenários hipotéticos bem definidos ou pesquisas amostrais locais.

12. SAÍDA: apenas o JSON válido, sem comentários antes ou depois.
    A chave "planejamento" vem PRIMEIRO e é obrigatória: use-a para decidir as etapas, os dados e os erros típicos ANTES de escrever o enunciado.
"""

POT_FEW_SHOT_EXAMPLES: List[str] = [
    # --- Exemplo 1: com tabela, média ponderada, 3 etapas ---
    """{
  "planejamento": "Dados: três turmas com nº de alunos e nota média. Etapas: (1) multiplicar nota média por nº de alunos em cada turma; (2) somar os produtos; (3) dividir pelo total de alunos. Erros típicos: usar média simples; esquecer uma turma; trocar os pesos; esquecer a turma A no divisor.",
  "enunciado": "Em um simulado aplicado em uma escola, três turmas obtiveram notas médias diferentes, conforme a tabela a seguir. Qual foi a nota média, em pontos, de todos os alunos que fizeram o simulado?",
  "tabela_dados": [
    {"Turma": "A", "Alunos": 40, "Nota média": 4},
    {"Turma": "B", "Alunos": 40, "Nota média": 6},
    {"Turma": "C", "Alunos": 20, "Nota média": 8}
  ],
  "solver": "def resolver():\\n    alunos_a, alunos_b, alunos_c = 40, 40, 20\\n    nota_a, nota_b, nota_c = 4, 6, 8\\n    total_alunos = alunos_a + alunos_b + alunos_c\\n    correta = (alunos_a*nota_a + alunos_b*nota_b + alunos_c*nota_c) / total_alunos\\n    erro_media_simples = (nota_a + nota_b + nota_c) / 3\\n    erro_esqueceu_turma_c = (alunos_a*nota_a + alunos_b*nota_b) / (alunos_a + alunos_b)\\n    erro_pesos_trocados = (alunos_c*nota_a + alunos_b*nota_b + alunos_a*nota_c) / total_alunos\\n    erro_esqueceu_turma_a = (alunos_b*nota_b + alunos_c*nota_c) / (alunos_b + alunos_c)\\n    return {'correta': round(correta, 2), 'distratores': [round(erro_media_simples, 2), round(erro_esqueceu_turma_c, 2), round(erro_pesos_trocados, 2), round(erro_esqueceu_turma_a, 2)]}"
}""",
    # --- Exemplo 2: sem tabela, porcentagens sucessivas ---
    """{
  "planejamento": "Dados: preço R$ 250, desconto de 20%, acréscimo de 10% sobre o valor já com desconto. Etapas: (1) aplicar o desconto; (2) aplicar o acréscimo sobre o resultado. Erros típicos: somar os percentuais (-20% + 10%); parar após o desconto; ignorar o desconto; responder o valor do desconto.",
  "enunciado": "Uma loja de eletrodomésticos anuncia um liquidificador por R$ 250,00. Na promoção de fim de semana, o preço recebe um desconto de 20%. Quem opta pelo pagamento parcelado paga um acréscimo de 10% sobre o valor já com desconto. Qual é o valor total, em reais, pago por um cliente que compra esse liquidificador de forma parcelada na promoção?",
  "solver": "def resolver():\\n    preco = 250\\n    desconto = 20\\n    acrescimo = 10\\n    com_desconto = preco * (1 - desconto/100)\\n    correta = com_desconto * (1 + acrescimo/100)\\n    erro_soma_percentuais = preco * (1 - desconto/100 + acrescimo/100)\\n    erro_so_desconto = com_desconto\\n    erro_ignorou_desconto = preco * (1 + acrescimo/100)\\n    erro_valor_do_desconto = preco * desconto/100\\n    return {'correta': round(correta, 2), 'distratores': [round(erro_soma_percentuais, 2), round(erro_so_desconto, 2), round(erro_ignorou_desconto, 2), round(erro_valor_do_desconto, 2)]}"
}""",
    # --- Exemplo 3: com tabela, conversão de unidades + área + custo ---
    """{
  "planejamento": "Dados: dimensões em metros de dois cômodos e preço do piso por m². Etapas: (1) calcular a área de cada cômodo; (2) somar as áreas; (3) multiplicar pelo preço por m². Erros típicos: somar perímetros no lugar de áreas; esquecer um cômodo; usar o preço sem multiplicar; multiplicar só pelo cômodo maior.",
  "enunciado": "Um proprietário vai trocar o piso de dois cômodos de sua casa e pediu um orçamento. As dimensões dos cômodos estão na tabela a seguir, e o piso escolhido custa R$ 45,00 por metro quadrado, já instalado. Qual será o custo total, em reais, para cobrir os dois cômodos?",
  "tabela_dados": [
    {"Cômodo": "Sala", "Largura (m)": 5, "Comprimento (m)": 6},
    {"Cômodo": "Quarto", "Largura (m)": 3, "Comprimento (m)": 4}
  ],
  "solver": "def resolver():\\n    largura_sala, comp_sala = 5, 6\\n    largura_quarto, comp_quarto = 3, 4\\n    preco_m2 = 45\\n    area_sala = largura_sala * comp_sala\\n    area_quarto = largura_quarto * comp_quarto\\n    correta = (area_sala + area_quarto) * preco_m2\\n    erro_perimetro = (2*(largura_sala+comp_sala) + 2*(largura_quarto+comp_quarto)) * preco_m2\\n    erro_esqueceu_quarto = area_sala * preco_m2\\n    erro_esqueceu_preco = area_sala + area_quarto\\n    erro_so_quarto = area_quarto * preco_m2\\n    return {'correta': correta, 'distratores': [erro_perimetro, erro_esqueceu_quarto, erro_esqueceu_preco, erro_so_quarto]}"
}""",
]


def sortear_few_shot() -> str:
    """Retorna um exemplo few-shot aleatório (formatado), para não ancorar sempre na mesma estrutura."""
    exemplo = random.choice(POT_FEW_SHOT_EXAMPLES)
    return (
        "--- [EXEMPLO DE FORMATO E DE QUALIDADE ESPERADOS] ---\n"
        "(Copie apenas o FORMATO e o nível de exigência. NÃO copie o tema, os números nem o tipo de cálculo.)\n"
        f"{exemplo}\n"
    )


POT_FEW_SHOT_EXAMPLE = POT_FEW_SHOT_EXAMPLES[0]


def build_enunciado_solver_prompt(
    habilidade_codigo: str,
    habilidade_descricao: str,
    competencia: int,
    eixo_tematico: Optional[str] = None,
    exemplos_referencia: Optional[List[Dict[str, Any]]] = None,
    tema: Optional[str] = None,
    abertura: Optional[str] = None,
    exemplo_few_shot: Optional[str] = None,
    enunciados_recentes: Optional[List[str]] = None
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

        ref_text = "\n\n".join(blocos) + (
            "\n\n(Crie uma questão inédita ISOMÓRFICA: mesma lógica matemática e MESMO NÍVEL DE COMPLEXIDADE das questões acima "
            "(número de etapas de raciocínio incluído), com um novo contexto do cotidiano e novos dados numéricos. "
            "Não simplifique para uma soma ou leitura direta de tabela)."
        )
    else:
        ref_text = (
            "(Sem questão de referência: siga os conceitos da habilidade alvo e mantenha o nível do ENEM, "
            "com pelo menos 2 etapas de raciocínio.)"
        )

    secao_recentes = ""
    if enunciados_recentes:
        itens = "\n".join(f"- {e.strip()[:160]}..." for e in enunciados_recentes[-3:])
        secao_recentes = f"""
JÁ FORAM GERADOS (NÃO repita contexto, estrutura nem tipo de cálculo):
{itens}
"""

    diretriz_criativa = ""
    if tema or abertura:
        linhas_criativas = []
        if tema:
            linhas_criativas.append(f"- Contexto temático sugerido: {tema}.")
        if abertura:
            linhas_criativas.append(f"- Abertura narrativa: {abertura}. (Evite começar com 'Um [profissional] está...').")
        diretriz_criativa = "\n" + "\n".join(linhas_criativas)

    few_shot = exemplo_few_shot if exemplo_few_shot is not None else sortear_few_shot()

    prompt = f"""{POT_QUESTION_GENERATOR_SYSTEM_PROMPT}

============================================================
ESPECIFICAÇÃO DA HABILIDADE ALVO (MATRIZ DO ENEM):
============================================================
- Código da Habilidade: {habilidade_codigo}
- Competência de Área: {competencia}
- Eixo Temático: {eixo_tematico or 'Matemática e suas Tecnologias'}
- Descrição Oficial do INEP: {habilidade_descricao}

A questão deve EXERCITAR a habilidade acima (não apenas citar o tema). Se a descrição pede, por exemplo, interpretar
gráfico, estimar, comparar ou usar proporção, o raciocínio do aluno precisa envolver exatamente isso.

{ref_text}

{few_shot}
{secao_recentes}============================================================
SUA TAREFA:
============================================================
Gere agora uma QUESTÃO INÉDITA para a habilidade {habilidade_codigo}.{diretriz_criativa}

Antes de responder, confira mentalmente:
[ ] a pergunta pede um NÚMERO com unidade?   [ ] há pelo menos 2 etapas?
[ ] todo dado é usado e nenhum dado essencial falta (base, área, pesos)?   [ ] texto e tabela não se contradizem?
[ ] os valores são realistas?   [ ] os 4 distratores vêm de erros típicos nomeados (nada de ± fixo, × 0,8, × 1,2)?

Responda EXCLUSIVAMENTE em formato JSON com as chaves 'planejamento', 'enunciado', 'tabela_dados' (opcional) e 'solver':
{{
  "planejamento": "Dados, etapas de raciocínio e erros típicos que viram distratores...",
  "enunciado": "Texto contextualizado da questão com comando final que pede um número...",
  "tabela_dados": [{{"Coluna1": "A", "Coluna2": 10}}],
  "solver": "def resolver():\\n    # variáveis com os dados do enunciado\\n    # uma variável por erro típico\\n    return {{'correta': ..., 'distratores': [d1, d2, d3, d4]}}"
}}
"""
    return prompt


def _formatar_tabela(tabela_dados: Optional[List[Dict[str, Any]]]) -> str:
    """Renderiza tabela_dados como texto simples para os prompts de validação."""
    if not tabela_dados:
        return ""
    colunas = list(tabela_dados[0].keys())
    linhas = [" | ".join(colunas)]
    for row in tabela_dados:
        linhas.append(" | ".join(str(row.get(c, "")) for c in colunas))
    return "\n".join(linhas)


def build_blind_solving_prompt(
    enunciado: str,
    tabela_dados: Optional[List[Dict[str, Any]]] = None
) -> str:
    """
    Constrói prompt para a Chamada 1 da Fase de Validação: Resolução Cega.
    O LLM recebe o enunciado (e a tabela, se houver), sem alternativas e sem gabarito.

    [v2]
    - Recebe a tabela (se o enunciado chega sem ela, o resolvedor cego não tem como resolver).
    - Declara 'premissas_assumidas' e 'dados_nao_utilizados'. O validador deve REPROVAR o item quando
      premissas_assumidas não for vazio: era exatamente o que acontecia nas questões 12 (pesos),
      17 (área por hectare) e 27 (tempos sem regra), que passavam com is_validated=True.
    """
    tabela_txt = _formatar_tabela(tabela_dados)
    bloco_tabela = f"\nTABELA DE DADOS:\n{tabela_txt}\n" if tabela_txt else ""

    prompt = f"""Você é um estudante de alto desempenho resolvendo uma questão de Matemática do ENEM.
Resolva usando EXCLUSIVAMENTE o que está escrito no enunciado e na tabela. Não complete lacunas por conta própria.

============================================================
ENUNCIADO DA QUESTÃO:
============================================================
{enunciado}
{bloco_tabela}
============================================================
SUA TAREFA:
============================================================
1. Resolva passo a passo, com rigor, em 'resolucao_passo_a_passo'.
2. Em 'premissas_assumidas', liste TODA suposição que você precisou fazer porque o texto não informa
   (ex.: "assumi que cada parcela tem 1 hectare", "assumi que os grupos têm o mesmo tamanho", "assumi que a pontuação não depende do tempo").
   Se não precisou supor nada, use uma lista vazia [].
3. Em 'dados_nao_utilizados', liste os números ou colunas fornecidos que NÃO entraram na sua resolução. Se todos foram usados, use [].
4. Em 'pergunta_respondivel', informe false se o comando final não puder ser respondido com um número a partir dos dados
   (ex.: pergunta "qual plano?" ou faltam dados). Caso contrário, true.
5. Em 'resultado_obtido', dê o resultado final como TIPO PRIMÁRIO do Python:
   - valor numérico único: apenas o número (int ou float), sem texto nem unidade (ex.: 35.0, 30, 1.9);
   - conclusão conceitual: texto;
   - vários valores: dict (ex.: {{"media": 135.0, "moda": None}}).

Responda EXCLUSIVAMENTE em formato JSON com o schema abaixo:
{{
  "resolucao_passo_a_passo": "Resolução detalhada...",
  "premissas_assumidas": [],
  "dados_nao_utilizados": [],
  "pergunta_respondivel": true,
  "resultado_obtido": "Valor numérico ou conclusão final"
}}
"""
    return prompt


def build_equivalencia_gabarito_prompt(resultado_solver: Any, resultado_obtido: Any) -> str:
    """
    Constrói prompt para a Chamada 2 da Fase de Validação: Confronto Direto de Equivalência.
    Juiz matemático objetivo que confronta o resultado calculado pelo Python com a conclusão da LLM.
    (Inalterado em relação à v1.)
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


def build_auditoria_semantica_prompt(
    enunciado: str,
    alternativas: Dict[str, str],
    tabela_dados: Optional[List[Dict[str, Any]]] = None,
    letra_gabarito: Optional[str] = None
) -> str:
    """
    Constrói prompt para a Chamada 3 da Fase de Validação: Auditoria Semântica e Pedagógica.

    [v2]
    - Recebe a tabela (a v1 só via enunciado + alternativas, então não conseguia detectar dados faltando ou contraditórios).
    - Critérios novos, um para cada defeito real encontrado na revisão:
        comando_incompativel_com_alternativas (Q9, Q11), premissa_implicita (Q12, Q17, Q27),
        dados_contraditorios (Q10), dado_irrelevante_ou_nao_usado (Q27), inverossimilhanca_numerica (Q3, Q13, Q21),
        nivel_trivial (24 de 28 itens), distratores_artificiais (todos).
    - O modelo escreve 'analise' ANTES dos booleanos (um 7B julga melhor depois de citar evidências).
    - Em caso de dúvida, marcar true (reprovar é mais barato que publicar item defeituoso).
    - O chamador deve reprovar o item se QUALQUER flag for true.
    """
    alts_formatted = "\n".join([f"  {k}) {v}" for k, v in sorted(alternativas.items())])
    tabela_txt = _formatar_tabela(tabela_dados)
    bloco_tabela = f"\nTabela:\n{tabela_txt}\n" if tabela_txt else ""
    bloco_gab = f"\nAlternativa correta segundo o sistema: {letra_gabarito}\n" if letra_gabarito else ""

    prompt = f"""Você é um Revisor Técnico e Pedagógico Oficial do INEP para questões do ENEM.
Audite o item de Matemática abaixo. Em caso de dúvida sobre um problema, marque true.

============================================================
ITEM SUBMETIDO:
============================================================
Enunciado:
{enunciado}
{bloco_tabela}
Alternativas:
{alts_formatted}
{bloco_gab}
============================================================
CRITÉRIOS (true = o problema EXISTE; false = o item está correto neste critério):
============================================================
1. possui_incoerencia: a situação é absurda ou fisicamente impossível? (ex.: consumo de 4 litros de água por casa por dia; prova de 50 m livre em 1,2 minuto; "consumir" calorias no treino; esporte e equipamento que não combinam)
2. possui_ambiguidade: o comando final admite mais de uma interpretação?
3. deficit_informacoes: falta algum dado essencial?
4. erros_ou_vazamentos: há erros de português ou as palavras 'solver', 'python', 'código', 'algoritmo', 'distrator', 'gabarito'?
5. duplicacao_tabelas: o texto repete os dados da tabela além da própria tabela?
6. comando_incompativel_com_alternativas: o comando final pede algo (um plano, uma opção, um nome) que as alternativas, todas numéricas, não respondem?
   Confira também se TODAS as alternativas têm o mesmo tipo de grandeza e se nenhuma é do tipo "Não há diferença" ou "Não há embalagem".
7. premissa_implicita: a resolução só funciona com uma suposição não escrita? (ex.: "por hectare" sem informar a área; percentuais por faixa sem o tamanho de cada faixa; parcelas de tamanho igual não declarado)
8. dados_contraditorios: o texto e a tabela se contradizem? (ex.: texto diz 15 km mas a tabela soma 14,8 km; texto diz 10 estações mas a tabela tem outro número; texto diz uma semana mas a tabela tem 5 dias)
9. dado_irrelevante_ou_nao_usado: há números ou informações que não entram em nenhuma etapa do cálculo (ex.: tempos de um atleta quando a pontuação é fixa)? Apenas UMA coluna extra de distração, coerente com o contexto, é aceitável.
10. inverossimilhanca_numerica: os valores estão fora de uma faixa realista para o contexto?
11. nivel_trivial: a questão se resolve com UMA única operação direta ou só com leitura de um valor da tabela (somar uma coluna, multiplicar dois números, ler uma célula)? O ENEM exige pelo menos 2 etapas de raciocínio.
12. distratores_artificiais: os distratores parecem correta ± valor fixo, correta × 0,8 ou × 1,2, ou decimais sem sentido para o contexto (ex.: 104,4 camisas)? Distratores bons correspondem a erros típicos de alunos.

PASSO 1: escreva em 'analise' uma frase curta com a evidência para cada critério que você marcar true.
PASSO 2: preencha os booleanos.

Responda EXCLUSIVAMENTE em formato JSON com o schema:
{{
  "analise": "Evidências curtas dos problemas encontrados (ou 'nenhum problema').",
  "possui_incoerencia": bool,
  "possui_ambiguidade": bool,
  "deficit_informacoes": bool,
  "erros_ou_vazamentos": bool,
  "duplicacao_tabelas": bool,
  "comando_incompativel_com_alternativas": bool,
  "premissa_implicita": bool,
  "dados_contraditorios": bool,
  "dado_irrelevante_ou_nao_usado": bool,
  "inverossimilhanca_numerica": bool,
  "nivel_trivial": bool,
  "distratores_artificiais": bool
}}
"""
    return prompt