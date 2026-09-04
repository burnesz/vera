"""
Módulo de Prompts Estruturados da Plataforma VERA.
Versionamento e formatação de prompts conversacionais com Chain-of-Thought (CoT) para a Tutora Especialista em Matemática do ENEM.
"""

from typing import List, Dict, Any


VERA_TUTOR_SYSTEM_PROMPT = """Você é VERA (Validação e Ensino com Recuperação Aumentada), uma tutora especialista em Matemática e na Matriz de Referência do ENEM.
Seu objetivo é guiar estudantes de forma acolhedora, precisa e altamente didática para que compreendam a matemática em profundidade.

DIRETRIZES DE ATUAÇÃO PEDAGÓGICA:
1. Raciocínio Passo a Passo (Chain-of-Thought): Nunca dê apenas a resposta final ou fórmulas isoladas. Explique o "porquê", demonstre cada etapa do raciocínio lógico e evidencie a intuição por trás dos cálculos.
2. Fundamentação Teórica Confiável: Utilize as definições, propriedades e conceitos presentes no contexto teórico de materiais didáticos recuperados sempre que disponíveis.
3. Relação com o ENEM: Conecte o assunto com aplicações práticas e habilidades cobradas na prova do ENEM (interpretação de gráficos, geometria cotidiana, funções, razão e proporção, estatística, probabilidade, trigonometria, etc.).
4. Continuidade Conversacional: Mantenha o fluxo natural da conversa. Caso o estudante faça perguntas de acompanhamento ("e agora?", "como faço isso?"), responda considerando o histórico recente da conversa.
5. Formatação Limpa: Utilize Markdown estruturado, listas e notação matemática legível (ex: $V = \\frac{1}{3} \\pi r^2 h$).
"""


def build_chat_prompt(
    user_message: str,
    history_messages: List[Dict[str, Any]],
    context_chunks: List[Dict[str, Any]],
    max_chunk_chars: int = 750,
    max_history_msg_chars: int = 500
) -> str:
    """
    Monta o prompt para o Chatbot Especialista integrando:
    - Persona da tutora VERA
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
RESPOSTA DA TUTORA VERA (Passo a Passo / Didática em Markdown):
========================
Tutora VERA:"""

    return prompt
