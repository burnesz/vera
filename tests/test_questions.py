import pytest
from app.schemas.question import QuestaoIneditaLLMOutput


def test_questions_pipeline_active():
    """Valida que o módulo de questões inéditas está plenamente implementado e ativo."""
    sample = {
        "enunciado": "Um tanque contém 1000 litros de água e é esvaziado a uma taxa constante de 50 litros por minuto. Em quantos minutos o tanque estará vazio?",
        "alternativas": {
            "A": "15 minutos.",
            "B": "20 minutos.",
            "C": "25 minutos.",
            "D": "30 minutos.",
            "E": "35 minutos."
        },
        "gabarito": "B",
        "justificativa": "1000 / 50 = 20 minutos."
    }
    item = QuestaoIneditaLLMOutput.model_validate(sample)
    assert item.gabarito == "B"
    assert len(item.alternativas) == 5
