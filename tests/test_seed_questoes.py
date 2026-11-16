import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models.habilidade import HabilidadeEnem
from app.db.models.questao_enem import QuestaoEnem
from scripts.seed_questoes import seed_questoes, parse_csv_rows


def test_parse_csv_rows():
    items = parse_csv_rows("data/itens_prova_2009_2024_llm_texto.csv")
    assert len(items) == 506
    first = items[0]
    assert first["co_item"] == 60227
    assert first["ano"] == 2009
    assert first["habilidade_codigo"] == "H24"
    assert first["gabarito"] == "E"
    assert "490 e 510 milhões" in first["alternativas"]["A"]
    assert first["metadados"]["tri"]["param_a"] is not None
    assert first["metadados"]["tri"]["param_b"] is not None
    assert first["metadados"]["tri"]["param_c"] is not None


def test_seed_questoes_sqlite(tmp_path):
    # Cria um banco sqlite temporário em arquivo
    db_file = tmp_path / "test_seed.db"
    db_url = f"sqlite:///{db_file}"

    engine = create_engine(db_url)
    Base.metadata.create_all(bind=engine)

    # 1ª execução: deve inserir todos os 506 itens e as 30 habilidades
    result1 = seed_questoes(
        csv_path="data/itens_prova_2009_2024_llm_texto.csv",
        db_url=db_url,
        dry_run=False
    )
    assert result1["total_parsed"] == 506
    assert result1["inserted"] == 506
    assert result1["updated"] == 0

    Session = sessionmaker(bind=engine)
    session = Session()

    # Valida contagens no banco
    hab_count = session.query(HabilidadeEnem).count()
    assert hab_count == 30

    q_count = session.query(QuestaoEnem).count()
    assert q_count == 506

    # Valida integridade de um item e relacionamento
    q = session.query(QuestaoEnem).filter_by(co_item=60227).first()
    assert q is not None
    assert q.ano == 2009
    assert q.habilidade_codigo == "H24"
    assert q.habilidade.competencia == 6
    assert q.gabarito == "E"
    assert len(q.alternativas) == 5
    assert q.metadados["tri"]["param_b"] == 2.26159
    session.close()

    # 2ª execução: idempotência (deve atualizar sem duplicar)
    result2 = seed_questoes(
        csv_path="data/itens_prova_2009_2024_llm_texto.csv",
        db_url=db_url,
        dry_run=False
    )
    assert result2["inserted"] == 0
    assert result2["updated"] == 506

    session = Session()
    assert session.query(QuestaoEnem).count() == 506
    session.close()


def test_seed_questoes_remover_ausentes(tmp_path):
    """Com remover_ausentes, as questões que saíram do CSV são apagadas; sem a opção, ficam."""
    import csv
    origem = "data/itens_prova_2009_2024_llm_texto.csv"
    with open(origem, encoding="utf-8-sig") as f:
        leitor = csv.DictReader(f, delimiter=";")
        campos, linhas = leitor.fieldnames, list(leitor)
    reduzido = tmp_path / "reduzido.csv"
    with open(reduzido, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos, delimiter=";")
        w.writeheader()
        w.writerows(linhas[:-3])

    db_url = f"sqlite:///{tmp_path / 'test_remover.db'}"
    seed_questoes(csv_path=origem, db_url=db_url)
    assert seed_questoes(csv_path=str(reduzido), db_url=db_url)["removed"] == 0

    session = sessionmaker(bind=create_engine(db_url))()
    assert session.query(QuestaoEnem).count() == 506
    session.close()

    result = seed_questoes(csv_path=str(reduzido), db_url=db_url, remover_ausentes=True)
    assert result["removed"] == 3
    session = sessionmaker(bind=create_engine(db_url))()
    assert session.query(QuestaoEnem).count() == 503
    assert session.query(QuestaoEnem).filter_by(co_item=int(linhas[-1]["CO_ITEM"])).first() is None
    session.close()
