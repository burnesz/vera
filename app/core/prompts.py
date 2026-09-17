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
    reply: str = text

    # Procura bloco de pensamento delimitado por <pensamento>...</pensamento>
    thought_match = re.search(r"<pensamento>(.*?)(?:</pensamento>|$)", text, flags=re.DOTALL | re.IGNORECASE)
    if thought_match:
        thought_content = thought_match.group(1).strip()
        if thought_content:
            thought = thought_content

    # Procura bloco de resposta delimitado por <resposta>...</resposta>
    reply_match = re.search(r"<resposta>(.*?)(?:</resposta>|$)", text, flags=re.DOTALL | re.IGNORECASE)
    if reply_match:
        reply_content = reply_match.group(1).strip()
        if reply_content:
            reply = reply_content
    elif thought_match:
        # Se houve <pensamento>, mas não houve tag explícita <resposta>, extrai o texto após </pensamento>
        end_thought = text.find("</pensamento>")
        if end_thought != -1:
            after_thought = text[end_thought + len("</pensamento>"):].strip()
            if after_thought:
                reply = after_thought
        else:
            # Caso anômalo: abriu tag mas não fechou
            reply = text

    # Limpeza residual de tags de resposta caso sobrem
    reply = re.sub(r"</?resposta>", "", reply, flags=re.IGNORECASE).strip()

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
BASE TEÓRICA DIDÁTICA (CONTEÚDO CONFIÁVEL DO PINECONE):
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
2. **Comando Claro:** O parágrafo final do enunciado deve expressar uma pergunta ou comando inequívoco do que o estudante deve calcular ou identificar.
3. **Rigor Matemático e Aritmética Exata:**
   - Realize as contas passo a passo no `thought_scratchpad`.
   - Escolha valores numéricos no enunciado que resultem em cálculos limpos e exatos (sem dízimas periódicas acidentais se as alternativas forem inteiras).
   - O gabarito DEVE ser exatamente o resultado obtido na resolução matemática. A alternativa apontada como correta DEVE conter rigorosamente esse valor.
4. **5 Alternativas (A a E):**
   - Exatamente 1 alternativa correta (gabarito).
   - 4 distratores plausíveis (representando erros de interpretação, equívocos conceituais, inversões de fórmulas ou cálculos parciais comuns a estudantes).
   - As alternativas devem possuir paralelismo sintático e extensão equilibrada.
   - NUNCA repita valores ou textos entre alternativas (unicidade estrita).
5. **Originalidade e Ineditismo:** O item gerado DEVE SER INÉDITO. Não copie nem meramente troque números dos itens de exemplo. Use-os apenas como referência do padrão de complexidade e linguagem.
6. **Formato de Saída (JSON Estrito):**
   Responda EXCLUSIVAMENTE com um objeto JSON válido, sem texto antes ou depois, seguindo o schema:
   {
     "thought_scratchpad": "Passo a passo mental: 1. Planejamento da situação-problema; 2. Cálculos matemáticos detalhados; 3. Construção dos distratores; 4. Checagem de unicidade.",
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

