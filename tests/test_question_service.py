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


def test_implicit_premise_in_blind_solving_rejects_with_early_exit():
    """
    Valida que premissas implícitas reportadas pela Resolução Cega (ex: 'mês = 30 dias')
    reprovam a questão ANTES da equivalência (Early Exit: 2 chamadas na 1ª tentativa).
    """
    db = TestingSessionLocal()
    try:
        mock_llm = MagicMock(spec=LLMClient)
        mock_vs = MagicMock(spec=PineconeVectorStore)
        mock_vs.search.return_value = []

        # 1ª tentativa: "mensal" sem declarar a quantidade de dias (o 30 aparece por coincidência)
        t1_pot = json.dumps({
            "enunciado": "Uma loja com 30 funcionários vende 4 produtos por dia cada. Quantos produtos a loja vende mensalmente?",
            "solver": "def resolver():\n    diario = 30 * 4\n    mensal = diario * 30\n    return {'correta': mensal, 'distratores': [120, 840, 3000, 4800]}"
        })
        t1_blind = json.dumps({
            "resolucao_passo_a_passo": "30 x 4 = 120 por dia; 120 x 30 = 3600 por mês.",
            "premissas_assumidas": ["Assumi que o mês tem 30 dias"],
            "resultado_obtido": 3600
        })

        # 2ª tentativa: premissa declarada explicitamente
        t2_pot = json.dumps({
            "enunciado": "Uma loja com 20 funcionários vende 4 produtos por dia cada. Considere que o mês tem 30 dias. Quantos produtos a loja vende mensalmente?",
            "solver": "def resolver():\n    diario = 20 * 4\n    mensal = diario * 30\n    return {'correta': mensal, 'distratores': [80, 560, 2000, 3200]}"
        })
        t2_blind = json.dumps({
            "resolucao_passo_a_passo": "20 x 4 = 80 por dia; 80 x 30 = 2400 por mês.",
            "premissas_assumidas": [],
            "resultado_obtido": 2400
        })
        t2_equiv = json.dumps({"equivalentes": True, "explicacao_equivalencia": "Equivalentes."})
        t2_audit = json.dumps({
            "possui_incoerencia": False,
            "possui_ambiguidade": False,
            "deficit_informacoes": False,
            "erros_ou_vazamentos": False,
            "duplicacao_tabelas": False
        })

        mock_llm.generate.side_effect = [
            t1_pot, t1_blind,                       # 2 chamadas: Early Exit por premissa implícita
            t2_pot, t2_blind, t2_equiv, t2_audit    # 4 chamadas: sucesso pleno
        ]

        service = QuestionService(llm_client=mock_llm, vector_store=mock_vs)
        questao = service.generate_single_questao_inedita(
            db=db,
            habilidade_codigo="H01",
            max_attempts=2
        )

        assert questao is not None
        assert questao.alternativas[questao.gabarito] == "2400"
        assert mock_llm.generate.call_count == 6
    finally:
        db.close()


def test_blind_solving_schema_normalizes_premissas():
    """Valida a normalização tolerante da lista de premissas retornada pelo LLM 7B."""
    from app.schemas.question import QuestaoBlindSolvingOutput

    # Campo ausente (retrocompatibilidade) -> lista vazia
    assert QuestaoBlindSolvingOutput(resolucao_passo_a_passo="x", resultado_obtido=1).premissas_assumidas == []
    # Marcadores vazios são descartados
    out = QuestaoBlindSolvingOutput(
        resolucao_passo_a_passo="x", resultado_obtido=1, premissas_assumidas=["Nenhuma.", "N/A", "", None]
    )
    assert out.premissas_assumidas == []
    # String única é convertida em lista
    out = QuestaoBlindSolvingOutput(
        resolucao_passo_a_passo="x", resultado_obtido=1, premissas_assumidas="Assumi juros compostos"
    )
    assert out.premissas_assumidas == ["Assumi juros compostos"]


def test_groundedness_rejects_undeclared_365_days():
    """'Ano = 365 dias' é convenção, não constante neutra: deve constar no enunciado."""
    from app.services.code_executor import validate_solver_consistency

    code = "def resolver():\n    total = 8 * 365\n    return {'correta': total, 'distratores': [1, 2, 3, 4]}"
    result = {"correta": 2920, "distratores": [8, 96, 240, 2880]}

    with pytest.raises(ValueError, match="365"):
        validate_solver_consistency(
            enunciado="Uma torneira desperdiça 8 litros por dia. Quantos litros desperdiça em um ano?",
            code=code,
            result=result
        )

    # Com a premissa declarada, o nexo numérico é aceito
    valores = validate_solver_consistency(
        enunciado="Uma torneira desperdiça 8 litros por dia. Considere que o ano tem 365 dias. Quantos litros desperdiça em um ano?",
        code=code,
        result=result
    )
    assert valores[0] == "2920"
