import pytest
import uuid
import json
from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.models
from app.db.base import Base
from app.db.models.habilidade import HabilidadeEnem
from app.db.models.questao_enem import QuestaoEnem
from app.db.models.questao_inedita import QuestaoInedita
from app.services.llm_client import LLMClient
from app.services.vectorstore import PineconeVectorStore
from app.services.question_service import QuestionService

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
Base.metadata.create_all(bind=test_engine)


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    db = TestingSessionLocal()
    try:
        hab = HabilidadeEnem(
            codigo="H01",
            competencia=1,
            descricao="Reconhecer, no contexto social, diferentes significados e representações dos números e operações.",
            eixo_tematico="Números e Operações"
        )
        db.merge(hab)

        q1 = QuestaoEnem(
            id=uuid.uuid4(),
            ano=2021,
            habilidade_codigo="H01",
            enunciado="Enunciado da questão histórica 1 sobre leitura de medidores...",
            alternativas={"A": "10", "B": "20", "C": "30", "D": "40", "E": "50"},
            gabarito="B"
        )
        q2 = QuestaoEnem(
            id=uuid.uuid4(),
            ano=2022,
            habilidade_codigo="H01",
            enunciado="Enunciado da questão histórica 2 sobre operações básicas...",
            alternativas={"A": "100", "B": "200", "C": "300", "D": "400", "E": "500"},
            gabarito="D"
        )
        db.add(q1)
        db.add(q2)
        db.commit()
    finally:
        db.close()


def test_retrieve_few_shot_examples():
    db = TestingSessionLocal()
    try:
        mock_vs = MagicMock(spec=PineconeVectorStore)
        service = QuestionService(vector_store=mock_vs)
        exemplos = service.retrieve_few_shot_examples(db, "H01", k=2)
        assert len(exemplos) == 2
        for ex in exemplos:
            assert ex.habilidade_codigo == "H01"
            assert ex.gabarito in ["A", "B", "C", "D", "E"]
    finally:
        db.close()


def test_generate_single_questao_inedita_pot_success():
    """Valida o pipeline PoT completo com 3 etapas de validação (Resolução Cega, Equivalência, Auditoria)."""
    db = TestingSessionLocal()
    try:
        mock_llm = MagicMock(spec=LLMClient)
        mock_vs = MagicMock(spec=PineconeVectorStore)
        mock_vs.search.return_value = []

        # Fase 1: Enunciado e Solver
        resp_fase1 = json.dumps({
            "enunciado": "Um reservatório com capacidade de 1.200 litros é abastecido a 40 litros por minuto com saída simultânea de 10 litros por minuto. Qual o tempo em minutos para enchê-lo?",
            "solver": "def resolver():\n    capacidade = 1200\n    entrada = 40\n    saida = 10\n    taxa = entrada - saida\n    tempo = capacidade / taxa\n    return {'correta': tempo, 'distratores': [30, 50, 60, 80]}"
        })

        # Validação Etapa 1: Resolução Cega
        resp_blind = json.dumps({
            "resolucao_passo_a_passo": "A taxa líquida é 40 - 10 = 30 L/min. Dividindo 1200 por 30, obtemos 40 minutos.",
            "resultado_obtido": "40 minutos"
        })

        # Validação Etapa 2: Confronto de Equivalência
        resp_equiv = json.dumps({
            "equivalentes": True,
            "explicacao_equivalencia": "40 e 40 minutos são matematicamente equivalentes."
        })

        # Validação Etapa 3: Auditoria Semântica
        resp_audit = json.dumps({
            "possui_incoerencia": False,
            "possui_ambiguidade": False,
            "deficit_informacoes": False,
            "erros_ou_vazamentos": False,
            "duplicacao_tabelas": False
        })

        mock_llm.generate.side_effect = [resp_fase1, resp_blind, resp_equiv, resp_audit]

        service = QuestionService(llm_client=mock_llm, vector_store=mock_vs)
        questao = service.generate_single_questao_inedita(
            db=db,
            habilidade_codigo="H01",
            num_few_shot=2,
            max_attempts=2
        )

        assert questao is not None
        assert questao.habilidade_codigo == "H01"
        assert questao.is_validated is True
        assert len(questao.alternativas) == 5
        # O gabarito matemático comprovado é 40
        assert questao.alternativas[questao.gabarito] == "40"
        assert "def resolver" in questao.thought_scratchpad
        assert "taxa líquida" in questao.justificativa
        assert mock_llm.generate.call_count == 4
    finally:
        db.close()


def test_generate_single_questao_inedita_pot_retry_on_solver_error():
    """Valida se o pipeline PoT captura o erro de execução do solver e re-tenta com feedback."""
    db = TestingSessionLocal()
    try:
        mock_llm = MagicMock(spec=LLMClient)
        mock_vs = MagicMock(spec=PineconeVectorStore)
        mock_vs.search.return_value = []

        # 1ª tentativa Fase 1: Solver com divisão por zero
        resp_fase1_erro = json.dumps({
            "enunciado": "Um motorista calcula a velocidade em uma viagem de 100 km com tempo 0 horas.",
            "solver": "def resolver():\n    dist = 100\n    t = 0\n    v = dist / t\n    return {'correta': v, 'distratores': [10, 20, 30, 40]}"
        })

        # 2ª tentativa Fase 1: Solver corrigido
        resp_fase1_ok = json.dumps({
            "enunciado": "Um motorista calcula a velocidade em uma viagem de 100 km com tempo de 2 horas. Qual a velocidade média em km/h?",
            "solver": "def resolver():\n    dist = 100\n    t = 2\n    v = dist / t\n    return {'correta': v, 'distratores': [30, 40, 60, 70]}"
        })

        # Validação 2ª tentativa
        resp_blind = json.dumps({
            "resolucao_passo_a_passo": "A velocidade média é 100 / 2 = 50 km/h.",
            "resultado_obtido": "50 km/h"
        })
        resp_equiv = json.dumps({
            "equivalentes": True,
            "explicacao_equivalencia": "50 e 50 km/h são equivalentes."
        })
        resp_audit = json.dumps({
            "possui_incoerencia": False,
            "possui_ambiguidade": False,
            "deficit_informacoes": False,
            "erros_ou_vazamentos": False,
            "duplicacao_tabelas": False
        })

        mock_llm.generate.side_effect = [resp_fase1_erro, resp_fase1_ok, resp_blind, resp_equiv, resp_audit]

        service = QuestionService(llm_client=mock_llm, vector_store=mock_vs)
        questao = service.generate_single_questao_inedita(
            db=db,
            habilidade_codigo="H01",
            max_attempts=3
        )

        assert questao is not None
        assert questao.alternativas[questao.gabarito] == "50"
        assert mock_llm.generate.call_count == 5
        # Progressão de temperatura da Fase 1: 0.0 na 1ª tentativa -> 0.1 na 2ª tentativa
        assert mock_llm.generate.call_args_list[0].kwargs["temperature"] == pytest.approx(0.0)
        assert mock_llm.generate.call_args_list[1].kwargs["temperature"] == pytest.approx(0.1)
    finally:
        db.close()


def test_generate_single_questao_inedita_rejects_missing_solver():
    """Valida que o pipeline PoT rejeita estritamente retornos sem solver Python."""
    db = TestingSessionLocal()
    try:
        mock_llm = MagicMock(spec=LLMClient)
        mock_vs = MagicMock(spec=PineconeVectorStore)
        mock_vs.search.return_value = []

        # Formato tradicional legado (sem solver)
        mock_output = {
            "thought_scratchpad": "Passo a passo.",
            "enunciado": "Em uma loja de informática, o preço de um computador sofreu um desconto de 15%...",
            "alternativas": {
                "A": "R$ 1.980,00.",
                "B": "R$ 2.040,00.",
                "C": "R$ 2.100,00.",
                "D": "R$ 2.160,00.",
                "E": "R$ 2.240,00."
            },
            "gabarito": "B",
            "justificativa": "15% de 2400 é 360..."
        }
        mock_llm.generate.return_value = json.dumps(mock_output)

        service = QuestionService(llm_client=mock_llm, vector_store=mock_vs)
        with pytest.raises(ValueError, match=r"RN-Q01 \(PoT\)"):
            service.generate_single_questao_inedita(
                db=db,
                habilidade_codigo="H01",
                num_few_shot=2,
                max_attempts=2
            )
    finally:
        db.close()


def test_generate_batch_success():
    db = TestingSessionLocal()
    try:
        mock_llm = MagicMock(spec=LLMClient)
        mock_vs = MagicMock(spec=PineconeVectorStore)
        mock_vs.search.return_value = []

        resp_pot = json.dumps({
            "enunciado": "Um investidor aplicou um capital de 5000 reais a uma taxa mensal de 2% durante 6 meses sob juros simples. Qual o montante final em reais?",
            "solver": "def resolver():\n    c = 5000\n    i = 0.02\n    t = 6\n    j = c * i * t\n    m = c + j\n    return {'correta': m, 'distratores': [5200, 5400, 5800, 6000]}"
        })
        resp_blind = json.dumps({
            "resolucao_passo_a_passo": "Juros = 5000 * 0.02 * 6 = 600. Montante = 5000 + 600 = 5600 reais.",
            "resultado_obtido": "5600"
        })
        resp_equiv = json.dumps({
            "equivalentes": True,
            "explicacao_equivalencia": "5600 coincide exatamente."
        })
        resp_audit = json.dumps({
            "possui_incoerencia": False,
            "possui_ambiguidade": False,
            "deficit_informacoes": False,
            "erros_ou_vazamentos": False,
            "duplicacao_tabelas": False
        })
        mock_llm.generate.side_effect = [resp_pot, resp_blind, resp_equiv, resp_audit]

        service = QuestionService(llm_client=mock_llm, vector_store=mock_vs)
        summary = service.generate_batch(
            db=db,
            habilidades=["H01"],
            count_per_habilidade=1
        )

        assert summary.total_habilidades_processadas == 1
        assert summary.total_sucesso == 1
        assert summary.total_falhas == 0
        assert len(summary.itens) == 1
        assert summary.itens[0].success is True
    finally:
        db.close()


def test_generate_pot_item_with_tabela_dados_clean_markdown():
    """Valida se o pipeline converte tabela_dados em Markdown sem duplicações."""
    db = TestingSessionLocal()
    try:
        mock_llm = MagicMock(spec=LLMClient)
        mock_vs = MagicMock(spec=PineconeVectorStore)
        mock_vs.search.return_value = []

        resp_pot = json.dumps({
            "enunciado": "A tabela a seguir apresenta os dados de consumo de água em metros cúbicos em uma residência. Qual o consumo total no período?",
            "tabela_dados": [
                {"Mês": "Janeiro", "Consumo": 15},
                {"Mês": "Fevereiro", "Consumo": 20}
            ],
            "solver": "def resolver():\n    total = 15 + 20\n    return {'correta': total, 'distratores': [25, 30, 40, 50]}"
        })
        resp_blind = json.dumps({
            "resolucao_passo_a_passo": "O total é 15 + 20 = 35 m³.",
            "resultado_obtido": "35 m³"
        })
        resp_equiv = json.dumps({
            "equivalentes": True,
            "explicacao_equivalencia": "35 e 35 m³ são equivalentes."
        })
        resp_audit = json.dumps({
            "possui_incoerencia": False,
            "possui_ambiguidade": False,
            "deficit_informacoes": False,
            "erros_ou_vazamentos": False,
            "duplicacao_tabelas": False
        })
        mock_llm.generate.side_effect = [resp_pot, resp_blind, resp_equiv, resp_audit]

        service = QuestionService(llm_client=mock_llm, vector_store=mock_vs)
        questao = service.generate_single_questao_inedita(
            db=db,
            habilidade_codigo="H01",
            max_attempts=1
        )

        assert questao is not None
        assert "| Mês | Consumo |" in questao.enunciado
        assert "| Janeiro | 15 |" in questao.enunciado
        # Exatamente uma ocorrência do cabeçalho
        assert questao.enunciado.count("| Mês | Consumo |") == 1
    finally:
        db.close()


def test_generate_pot_item_sanitizes_duplicate_inline_pseudo_table():
    """Valida se o backend remove blocos redundantes de pseudo-tabelas gerados pelo LLM."""
    db = TestingSessionLocal()
    try:
        mock_llm = MagicMock(spec=LLMClient)
        mock_vs = MagicMock(spec=PineconeVectorStore)
        mock_vs.search.return_value = []

        resp_pot = json.dumps({
            "enunciado": (
                "Em um experimento de monitoramento, foram coletados dados sobre custos por megabyte baixado. "
                "Qual horário apresenta o menor custo?\n\n"
                "Tabela de dados:\n"
                "Horário | Custo por MB\n"
                "10h00 | 0.002\n"
                "14h00 | 0.003"
            ),
            "tabela_dados": [
                {"Horário": "10h00", "Custo por MB": 0.002},
                {"Horário": "14h00", "Custo por MB": 0.003}
            ],
            "solver": "def resolver():\n    return {'correta': '10h00', 'distratores': ['14h00', '18h00', '22h00', '23h00']}"
        })
        resp_blind = json.dumps({
            "resolucao_passo_a_passo": "O menor custo é 0.002 às 10h00.",
            "resultado_obtido": "10h00"
        })
        resp_equiv = json.dumps({
            "equivalentes": True,
            "explicacao_equivalencia": "Ambos 10h00."
        })
        resp_audit = json.dumps({
            "possui_incoerencia": False,
            "possui_ambiguidade": False,
            "deficit_informacoes": False,
            "erros_ou_vazamentos": False,
            "duplicacao_tabelas": False
        })
        mock_llm.generate.side_effect = [resp_pot, resp_blind, resp_equiv, resp_audit]

        service = QuestionService(llm_client=mock_llm, vector_store=mock_vs)
        questao = service.generate_single_questao_inedita(
            db=db,
            habilidade_codigo="H01",
            max_attempts=1
        )

        assert questao is not None
        # O cabeçalho formatado em Markdown com pipes deve existir exatamente uma vez
        assert questao.enunciado.count("| Horário | Custo por MB |") == 1
        # A pseudo-tabela de texto duplicada deve ter sido removida
        assert "Tabela de dados:\nHorário | Custo por MB" not in questao.enunciado
    finally:
        db.close()


def test_generate_pot_item_sanitizes_duplicate_bullet_list():
    """Valida se o backend remove listas de tópicos redundantes em 'Tabela ...:'."""
    db = TestingSessionLocal()
    try:
        mock_llm = MagicMock(spec=LLMClient)
        mock_vs = MagicMock(spec=PineconeVectorStore)
        mock_vs.search.return_value = []

        resp_pot = json.dumps({
            "enunciado": (
                "Um centro de distribuição planeja a ração diária por faixa etária. "
                "Qual será a quantidade total de ração necessária?\n\n"
                "Tabela de consumo de ração por cães:\n"
                "- Jovens (0-2 anos): 0.5 kg/dia\n"
                "- Adultos (3-10 anos): 0.3 kg/dia"
            ),
            "tabela_dados": [
                {"Faixa": "Jovens", "Consumo": 0.5},
                {"Faixa": "Adultos", "Consumo": 0.3}
            ],
            "solver": "def resolver():\n    total = 0.5 + 0.3\n    return {'correta': total, 'distratores': [1.0, 1.2, 1.5, 2.0]}"
        })
        resp_blind = json.dumps({
            "resolucao_passo_a_passo": "Total é 0.8.",
            "resultado_obtido": "0.8"
        })
        resp_equiv = json.dumps({
            "equivalentes": True,
            "explicacao_equivalencia": "Ambos 0.8."
        })
        resp_audit = json.dumps({
            "possui_incoerencia": False,
            "possui_ambiguidade": False,
            "deficit_informacoes": False,
            "erros_ou_vazamentos": False,
            "duplicacao_tabelas": False
        })
        mock_llm.generate.side_effect = [resp_pot, resp_blind, resp_equiv, resp_audit]

        service = QuestionService(llm_client=mock_llm, vector_store=mock_vs)
        questao = service.generate_single_questao_inedita(
            db=db,
            habilidade_codigo="H01",
            max_attempts=1
        )

        assert questao is not None
        assert "| Faixa | Consumo |" in questao.enunciado
        assert questao.enunciado.count("| Faixa | Consumo |") == 1
        assert "- Jovens" not in questao.enunciado
    finally:
        db.close()


def test_three_stage_validation_mismatch_triggers_early_exit():
    """Valida se divergência de equivalência interrompe o fluxo (Early Exit sem chamar auditoria) e faz retry."""
    db = TestingSessionLocal()
    try:
        mock_llm = MagicMock(spec=LLMClient)
        mock_vs = MagicMock(spec=PineconeVectorStore)
        mock_vs.search.return_value = []

        # 1ª tentativa: Solver calculou 120 (bug de moda), mas LLM cego achou 'não há moda' -> equivalentes=False
        t1_pot = json.dumps({
            "enunciado": "Qual a moda das equipes de lixo?",
            "solver": "def resolver():\n    return {'correta': 120, 'distratores': [130, 140, 150, 160]}"
        })
        t1_blind = json.dumps({
            "resolucao_passo_a_passo": "Todos os valores aparecem 1 vez, logo o conjunto é amodal.",
            "resultado_obtido": "não há moda"
        })
        t1_equiv = json.dumps({
            "equivalentes": False,
            "explicacao_equivalencia": "O solver calculou 120, mas o conjunto é amodal (não há moda)."
        })
        # A auditoria da tentativa 1 NÃO deve ser chamada! (Early Exit)

        # 2ª tentativa: Sucesso pleno
        t2_pot = json.dumps({
            "enunciado": "Qual a média das notas 10 e 20?",
            "solver": "def resolver():\n    return {'correta': 15, 'distratores': [10, 20, 25, 30]}"
        })
        t2_blind = json.dumps({
            "resolucao_passo_a_passo": "(10 + 20) / 2 = 15.",
            "resultado_obtido": "15"
        })
        t2_equiv = json.dumps({
            "equivalentes": True,
            "explicacao_equivalencia": "15 e 15 são equivalentes."
        })
        t2_audit = json.dumps({
            "possui_incoerencia": False,
            "possui_ambiguidade": False,
            "deficit_informacoes": False,
            "erros_ou_vazamentos": False,
            "duplicacao_tabelas": False
        })

        mock_llm.generate.side_effect = [
            t1_pot, t1_blind, t1_equiv,  # 3 chamadas na 1ª tentativa (curto-circuito na equivalência)
            t2_pot, t2_blind, t2_equiv, t2_audit  # 4 chamadas na 2ª tentativa
        ]

        service = QuestionService(llm_client=mock_llm, vector_store=mock_vs)
        questao = service.generate_single_questao_inedita(
            db=db,
            habilidade_codigo="H01",
            max_attempts=2
        )

        assert questao is not None
        assert questao.alternativas[questao.gabarito] == "15"
        assert mock_llm.generate.call_count == 7
    finally:
        db.close()


def test_three_stage_validation_semantic_failure_rejects():
    """Valida se defeito apontado na auditoria semântica rejeita a questão e gera mensagem automática."""
    db = TestingSessionLocal()
    try:
        mock_llm = MagicMock(spec=LLMClient)
        mock_vs = MagicMock(spec=PineconeVectorStore)
        mock_vs.search.return_value = []

        # 1ª tentativa: Equivalência OK, mas Auditoria detecta déficit de informações
        t1_pot = json.dumps({
            "enunciado": "Qual a velocidade média de um carro que percorreu uma distância sem tempo?",
            "solver": "def resolver():\n    return {'correta': 10, 'distratores': [20, 30, 40, 50]}"
        })
        t1_blind = json.dumps({
            "resolucao_passo_a_passo": "Resolução 10.",
            "resultado_obtido": "10"
        })
        t1_equiv = json.dumps({
            "equivalentes": True,
            "explicacao_equivalencia": "Equivalentes."
        })
        t1_audit = json.dumps({
            "possui_incoerencia": False,
            "possui_ambiguidade": False,
            "deficit_informacoes": True,  # Defeito detectado!
            "erros_ou_vazamentos": False,
            "duplicacao_tabelas": False
        })

        # 2ª tentativa: Sucesso pleno
        t2_pot = json.dumps({
            "enunciado": "Enunciado completo sobre velocidade média.",
            "solver": "def resolver():\n    return {'correta': 80, 'distratores': [60, 70, 90, 100]}"
        })
        t2_blind = json.dumps({
            "resolucao_passo_a_passo": "80 km/h.",
            "resultado_obtido": "80"
        })
        t2_equiv = json.dumps({
            "equivalentes": True,
            "explicacao_equivalencia": "Equivalentes."
        })
        t2_audit = json.dumps({
            "possui_incoerencia": False,
            "possui_ambiguidade": False,
            "deficit_informacoes": False,
            "erros_ou_vazamentos": False,
            "duplicacao_tabelas": False
        })

        mock_llm.generate.side_effect = [
            t1_pot, t1_blind, t1_equiv, t1_audit,  # 4 chamadas na 1ª tentativa (rejeitada na auditoria)
            t2_pot, t2_blind, t2_equiv, t2_audit   # 4 chamadas na 2ª tentativa
        ]

        service = QuestionService(llm_client=mock_llm, vector_store=mock_vs)
        questao = service.generate_single_questao_inedita(
            db=db,
            habilidade_codigo="H01",
            max_attempts=2
        )

        assert questao is not None
        assert questao.alternativas[questao.gabarito] == "80"
        assert mock_llm.generate.call_count == 8
    finally:
        db.close()


def test_equivalence_recovers_when_blind_solving_returns_dict_with_correct_value():
    """
    Valida que quando a Resolução Cega retorna um dict com múltiplos grupos (ex: {'Grupo A': 1350.0, 'Grupo B': 1150.0})
    contendo o valor exato do solver (1350.0), a Etapa 2 aprova deterministicamente sem descartar a questão.
    """
    db = TestingSessionLocal()
    try:
        mock_llm = MagicMock(spec=LLMClient)
        mock_vs = MagicMock(spec=PineconeVectorStore)
        mock_vs.search.return_value = []

        t1_pot = json.dumps({
            "enunciado": "Em uma fazenda, o Grupo A produziu 1350 kg e o Grupo B produziu 1150 kg. Qual a produção do Grupo A?",
            "solver": "def resolver():\n    a = 1350\n    b = 1150\n    return {'correta': a, 'distratores': [b, a + b, a - b, 1000]}"
        })
        t1_blind = json.dumps({
            "resolucao_passo_a_passo": "Grupo A = 1350 e Grupo B = 1150.",
            "resultado_obtido": {"Grupo A": 1350.0, "Grupo B": 1150.0}
        })
        # Mesmo que o juiz LLM retorne False por ver um dict, o backend recupera pois 1350.0 está no dict
        t1_equiv = json.dumps({
            "equivalentes": False,
            "explicacao_equivalencia": "Resultado B contém múltiplos grupos."
        })
        t1_audit = json.dumps({
            "possui_incoerencia": False,
            "possui_ambiguidade": False,
            "deficit_informacoes": False,
            "erros_ou_vazamentos": False,
            "duplicacao_tabelas": False
        })

        mock_llm.generate.side_effect = [t1_pot, t1_blind, t1_equiv, t1_audit]

        service = QuestionService(llm_client=mock_llm, vector_store=mock_vs)
        questao = service.generate_single_questao_inedita(
            db=db,
            habilidade_codigo="H01",
            max_attempts=1
        )

        assert questao is not None
        assert questao.alternativas[questao.gabarito] == "1350"
        assert mock_llm.generate.call_count == 4
    finally:
        db.close()


def test_groundedness_accepts_derived_scales_words_and_percentages():
    """
    Valida que o nexo numérico aceita conversões métricas (5 m³ -> 5000 L),
    numerais por extenso ('oito' -> 8, 'mensal' -> 30), raio a partir do diâmetro (40 -> 20)
    e complementos percentuais (20% -> 0.8 ou 80).
    """
    from app.services.code_executor import validate_solver_consistency

    # Caso 1: 5 m³ e 6 m³ convertidos diretamente para 5000 e 6000 no solver
    code_scale = "def resolver():\n    v1 = 5000\n    v2 = 6000\n    return {'correta': v1 + v2, 'distratores': [1, 2, 3, 4]}"
    valores_scale = validate_solver_consistency(
        enunciado="Dois reservatórios comportam 5 m³ e 6 m³ de água. Qual a capacidade total em litros?",
        code=code_scale,
        result={"correta": 11000, "distratores": [5000, 6000, 10000, 12000]}
    )
    assert valores_scale[0] == "11000"

    # Caso 2: numeral por extenso ('oito') + termo temporal ('mensal' -> 30) + complemento de 20% (0.8)
    code_words = "def resolver():\n    total = 8 * 30 * 0.8\n    return {'correta': total, 'distratores': [1, 2, 3, 4]}"
    valores_words = validate_solver_consistency(
        enunciado="Uma máquina opera oito horas por dia com 20% de perda. Qual o tempo útil mensal em horas?",
        code=code_words,
        result={"correta": 192, "distratores": [180, 200, 220, 240]}
    )
    assert valores_words[0] == "192"


def test_groundedness_accepts_numbers_attached_to_units():
    """Garante que números colados a unidades sem espaço (ex: 20m, 40kg) não geram falso positivo no nexo numérico."""
    from app.services.code_executor import validate_solver_consistency

    code = "def resolver():\n    largura = 20\n    comprimento = 40\n    area = largura * comprimento\n    return {'correta': area, 'distratores': [60, 120, 400, 1600]}"
    result = {"correta": 800, "distratores": [60, 120, 400, 1600]}

    valores = validate_solver_consistency(
        enunciado="Um terreno retangular mede 20m de largura por 40m de comprimento. Qual a sua área?",
        code=code,
        result=result
    )
    assert valores[0] == "800"


def test_retrieve_rag_few_shot_filters_by_habilidade_and_clean_ocr():
    """
    Valida que a Etapa 0 (RAG) filtra estritamente por habilidade_codigo no Pinecone
    e descarta exemplos de habilidades divergentes (ex: H19 para H04) ou com OCR quebrado.
    """
    mock_vs = MagicMock(spec=PineconeVectorStore)
    mock_vs.search.return_value = [
        {
            "id": "wrong-hab",
            "score": 0.92,
            "metadata": {
                "habilidade_codigo": "H19",
                "text": "Questão longa da habilidade H19 que não deveria entrar em H04.",
                "gabarito": "A"
            }
        },
        {
            "id": "corrupted-ocr",
            "score": 0.90,
            "metadata": {
                "habilidade_codigo": "H04",
                "text": "Questão com fórmula corrompida ( \\right)( ) (2 3) (Y ) no enunciado.",
                "gabarito": "B"
            }
        },
        {
            "id": "clean-h04",
            "score": 0.85,
            "metadata": {
                "habilidade_codigo": "H04",
                "text": "Questão íntegra da habilidade H04 avaliando razão e proporção entre grandezas.",
                "gabarito": "C"
            }
        }
    ]

    service = QuestionService(vector_store=mock_vs)
    exemplos = service.retrieve_rag_few_shot_examples("H04", k=2)

    mock_vs.search.assert_called_once()
    assert mock_vs.search.call_args.kwargs["filter_dict"] == {"habilidade_codigo": "H04"}
    assert len(exemplos) == 1
    assert exemplos[0]["habilidade_origem"] == "H04"
    assert "íntegra" in exemplos[0]["enunciado"]


def test_validate_solver_consistency_rejects_dead_table_and_dead_columns():
    """
    Valida que validate_solver_consistency rejeita:
    1. Tabela de coluna única onde apenas 1 valor é usado em correta (caso H09: [30, 70, 50] com 50 * 24).
    2. Tabela com coluna numérica inteira morta/ignorada em correta (caso H15: coluna [10, 8, 6] ignorada).
    3. Tabela com mais de 10 linhas (caso H11: 30 linhas).
    """
    from app.services.code_executor import validate_solver_consistency

    # 1. Caso H09: tabela [30, 70, 50] ignorada, usando apenas 50 * 24
    with pytest.raises(ValueError, match="tornando a tabela desnecessária"):
        validate_solver_consistency(
            enunciado="Luminosidade média é 50 lux em 24 horas. | Hora | Luminosidade |\n| 6h | 30 |\n| 12h | 70 |\n| 18h | 50 |",
            code="def resolver():\n    return {'correta': 50 * 24, 'distratores': [30, 70, 100, 200]}",
            result={"correta": 1200, "distratores": [30, 70, 100, 200]},
            tabela_dados=[
                {"Hora": "6h", "Luminosidade": 30},
                {"Hora": "12h", "Luminosidade": 70},
                {"Hora": "18h", "Luminosidade": 50},
            ]
        )

    # 2. Caso H15: coluna 'Quantidade de Frutas' [10, 8, 6] ignorada no cálculo de correta
    with pytest.raises(ValueError, match="coluna numérica 'Quantidade de Frutas'"):
        validate_solver_consistency(
            enunciado="Venda de 100 pacotes a custo de 1.5 e preços 5, 4 e 3.",
            code="def resolver():\n    lucro = 100 * ((5 - 1.5) + (4 - 1.5) + (3 - 1.5))\n    return {'correta': lucro, 'distratores': [100, 200, 300, 400]}",
            result={"correta": 750.0, "distratores": [100, 200, 300, 400]},
            tabela_dados=[
                {"Pacote": "A", "Preço": 5, "Quantidade de Frutas": 10},
                {"Pacote": "B", "Preço": 4, "Quantidade de Frutas": 8},
                {"Pacote": "C", "Preço": 3, "Quantidade de Frutas": 6},
            ]
        )

    # 3. Caso H11: tabela excessiva com mais de 10 linhas
    with pytest.raises(ValueError, match="máximo permitido: 10"):
        validate_solver_consistency(
            enunciado="Consumo diário de 15 dias.",
            code="def resolver():\n    return {'correta': 15, 'distratores': [1, 2, 3, 4]}",
            result={"correta": 15, "distratores": [1, 2, 3, 4]},
            tabela_dados=[{"Dia": i, "Consumo": 15} for i in range(1, 16)]
        )


def test_equivalence_fast_path_skips_llm_when_numeric_scalars_match():
    """
    Valida que quando o solver e a resolução cega retornam o mesmo número (int/float),
    a Etapa 2 aprova via Fast-Path em 0ms sem chamar o LLM (total de 3 chamadas ao LLM em vez de 4).
    """
    db = TestingSessionLocal()
    try:
        mock_llm = MagicMock(spec=LLMClient)
        mock_vs = MagicMock(spec=PineconeVectorStore)
        mock_vs.search.return_value = []

        resp_pot = json.dumps({
            "enunciado": "Uma cooperativa vendeu 250 kg a 6 reais e 500 kg a 3 reais. Qual a receita total?",
            "tabela_dados": None,
            "solver": "def resolver():\n    total = 250 * 6 + 500 * 3\n    return {'correta': total, 'distratores': [1500, 2000, 2500, 3500]}"
        })
        resp_blind = json.dumps({
            "resolucao_passo_a_passo": "250 * 6 = 1500 e 500 * 3 = 1500. Soma = 3000.",
            "resultado_obtido": 3000.0
        })
        resp_audit = json.dumps({
            "analise_critica": "Enunciado e resolução coerentes e sem empates.",
            "possui_incoerencia": False,
            "possui_ambiguidade": False,
            "deficit_informacoes": False,
            "erros_ou_vazamentos": False,
            "duplicacao_tabelas": False
        })

        # Apenas 3 chamadas ao LLM: Geração PoT, Resolução Cega e Auditoria Semântica!
        mock_llm.generate.side_effect = [resp_pot, resp_blind, resp_audit]

        service = QuestionService(llm_client=mock_llm, vector_store=mock_vs)
        questao = service.generate_single_questao_inedita(
            db=db,
            habilidade_codigo="H01",
            max_attempts=1
        )

        assert questao is not None
        assert questao.alternativas[questao.gabarito] == "3000"
        assert mock_llm.generate.call_count == 3
        # Verifica que a chamada 3 (Auditoria Semântica) recebeu a resolução passo a passo da Etapa 1
        audit_prompt = mock_llm.generate.call_args_list[2].kwargs["prompt"]
        assert "250 * 6 = 1500" in audit_prompt
    finally:
        db.close()



