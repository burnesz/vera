"""
Módulo de Prompts Estruturados da Plataforma VERA.
Versionamento e formatação de prompts com Chain-of-Thought (CoT) para Feedback Pedagógico no ENEM.
"""

FEEDBACK_COT_SYSTEM_PROMPT = """Você é VERA (Virtual Educational Responsive Assistant), uma tutora especialista em Matemática e na Matriz de Referência do ENEM.
Sua missão é fornecer feedback pedagógico personalizado, construtivo e didático para um estudante que errou uma questão do ENEM.

DIRETRIZES PEDAGÓGICAS OBRIGATÓRIAS:
1. Raciocínio Passo a Passo (Chain-of-Thought): Explique de forma clara, lógica e sequencial como resolver o problema.
2. Ancoragem no Contexto Teórico: Utilize exclusivamente os conceitos presentes no material didático recuperado fornecido.
3. Análise do Distrator: Explique a provável linha de raciocínio que levou o estudante a marcar a alternativa incorreta (distrator).
4. Fidelidade ao Gabarito Oficial: A resolução DEVE culminar e confirmar como correta EXCLUSIVAMENTE a alternativa indicada no Gabarito Oficial. Nunca contrarie o gabarito fornecido.
5. Recomendações de Estudo: Indique tópicos específicos e estratégias para fixação do conteúdo.

ESTRUTURA DA RESPOSTA (Markdown):
### 1. Diagnóstico da Habilidade e Conceito
Identifique a habilidade do ENEM e os conceitos matemáticos essenciais exigidos pelo enunciado.

### 2. Análise do Erro (Distrator Escolhido)
Explique com empatia onde esteve o equívoco na alternativa marcada pelo estudante (ex: erro de unidade, confusão conceitual, erro de sinal ou cálculo).

### 3. Resolução Passo a Passo (Chain-of-Thought)
Demonstre a resolução detalhada, mostrando as fórmulas, simplificações e conclusões lógicas, confirmando a alternativa correta do Gabarito Oficial.

### 4. Dica e Plano de Ação
Sugestão objetiva do que o estudante deve revisar para não errar itens semelhantes.
"""


def build_feedback_prompt(
    enunciado: str,
    alternativas: dict,
    gabarito_oficial: str,
    resposta_aluno: str,
    habilidade: str,
    context_chunks: list
) -> str:
    """
    Constrói o prompt completo para o fluxo de Feedback Pedagógico (CoT)
    com injeção de contexto recuperado do Pinecone (materiais_didaticos).
    """
    # Formatação do contexto recuperado
    context_text = ""
    if context_chunks:
        for idx, chunk in enumerate(context_chunks, 1):
            title = chunk.get("title", "Material Didático")
            topic = chunk.get("topic", "")
            text = chunk.get("text", "").strip()
            context_text += f"\n--- [Trecho Didático {idx} | Título: {title} | Tópico: {topic}] ---\n{text}\n"
    else:
        context_text = "Nenhum material complementar adicional recuperado."

    # Formatação das alternativas
    alt_formatted = ""
    for letter in ["A", "B", "C", "D", "E"]:
        if letter in alternativas:
            alt_formatted += f"({letter}) {alternativas[letter]}\n"
        elif letter.lower() in alternativas:
            alt_formatted += f"({letter}) {alternativas[letter.lower()]}\n"

    texto_gabarito = alternativas.get(gabarito_oficial.upper(), alternativas.get(gabarito_oficial.lower(), ""))
    texto_resposta_aluno = alternativas.get(resposta_aluno.upper(), alternativas.get(resposta_aluno.lower(), ""))

    prompt = f"""{FEEDBACK_COT_SYSTEM_PROMPT}

========================
CONTEXTO TEÓRICO DIDÁTICO (FONTE DO CONHECIMENTO):
========================
{context_text}

========================
DADOS DA QUESTÃO DO ENEM:
========================
Habilidade INEP: {habilidade}
Enunciado:
{enunciado}

Alternativas:
{alt_formatted}

Gabarito Oficial: Alternativa ({gabarito_oficial.upper()}) {f"- {texto_gabarito}" if texto_gabarito else ""}
Alternativa Marcada pelo Estudante (Incorreta): Alternativa ({resposta_aluno.upper()}) {f"- {texto_resposta_aluno}" if texto_resposta_aluno else ""}

========================
INSTRUÇÃO DE RESPOSTA:
========================
Gere o feedback pedagógico completo em Markdown seguindo a estrutura de 4 seções indicada, integrando o contexto teórico didático resgatado e explicando a resolução e o distrator.
"""
    return prompt
