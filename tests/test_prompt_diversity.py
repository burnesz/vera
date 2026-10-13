"""
Testes unitários para validação de diversidade temática e estrutural de aberturas
nos prompts e no QuestionService (RN-Q01 / Evolução DSR).
"""

from app.core.prompts import (
    TEMAS_COTIDIANO,
    FORMAS_ABERTURA,
    sortear_contexto_criativo,
    build_enunciado_solver_prompt,
    build_question_generation_prompt,
)


def test_sortear_contexto_criativo():
    """Valida que o sorteio retorna itens válidos das listas pré-definidas."""
    assert len(TEMAS_COTIDIANO) >= 10
    assert len(FORMAS_ABERTURA) >= 6

    for _ in range(20):
        tema, abertura = sortear_contexto_criativo()
        assert tema in TEMAS_COTIDIANO
        assert abertura in FORMAS_ABERTURA


def test_build_enunciado_solver_prompt_com_diretriz_criativa():
    """Valida injeção enxuta de tema e abertura no prompt PoT da Fase 1."""
    tema_teste = "Energia renovável, consumo elétrico ou sustentabilidade"
    abertura_teste = "Inicie apresentando o resultado de uma pesquisa amostral ou levantamento local"

    prompt = build_enunciado_solver_prompt(
        habilidade_codigo="H01",
        habilidade_descricao="Reconhecer padrões numéricos.",
        competencia=1,
        tema=tema_teste,
        abertura=abertura_teste,
    )

    assert "Contexto temático sugerido: Energia renovável" in prompt
    assert "Abertura narrativa: Inicie apresentando o resultado de uma pesquisa amostral" in prompt
    assert "Evite começar com 'Um [profissional] está...'" in prompt
    assert "Gere agora uma QUESTÃO INÉDITA para a habilidade H01." in prompt


def test_build_enunciado_solver_prompt_sem_diretriz_opcional():
    """Valida que o prompt funciona normalmente sem tema ou abertura."""
    prompt = build_enunciado_solver_prompt(
        habilidade_codigo="H02",
        habilidade_descricao="Identificar relações de proporcionalidade.",
        competencia=1,
    )

    assert "Gere agora uma QUESTÃO INÉDITA para a habilidade H02." in prompt
    assert "Contexto temático sugerido" not in prompt


def test_build_question_generation_prompt_com_diretriz():
    """Valida injeção no prompt clássico/tradicional."""
    prompt = build_question_generation_prompt(
        habilidade_codigo="H03",
        habilidade_descricao="Resolver problemas numéricos.",
        competencia=1,
        tema="Saúde pública, medicina ou nutrição",
        abertura="Inicie contextualizando o cenário geográfico",
    )

    assert "Contexto temático sugerido: Saúde pública" in prompt
    assert "Abertura narrativa: Inicie contextualizando o cenário geográfico" in prompt
