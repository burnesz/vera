import os
import sys
import csv
import logging
import argparse
from typing import Dict, Any, List, Optional

# Garante inclusão do diretório raiz no PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from sqlalchemy import select, create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import settings
import app.db.models  # Garante registro de todos os modelos no Base.metadata
from app.db.base import Base
from app.db.models.habilidade import HabilidadeEnem
from app.db.models.questao_enem import QuestaoEnem
from scripts.seed_habilidades import seed_habilidades, HABILIDADES_MAT

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("vera.seed_questoes")


def parse_csv_rows(csv_path: str) -> List[Dict[str, Any]]:
    """
    Lê e valida o arquivo CSV de itens enriquecidos do ENEM.
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Arquivo CSV não encontrado no caminho: {csv_path}")

    items = []
    with open(csv_path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        for line_num, row in enumerate(reader, start=2):
            try:
                co_item = int(row["CO_ITEM"].strip())
                ano = int(row["ANO_APLICACAO"].strip())
                hab_num = int(row["CO_HABILIDADE"].strip())
                hab_code = f"H{hab_num:02d}"
                gabarito = row["TX_GABARITO"].strip().upper()
                enunciado = row["DESC_ENUNCIADO"].strip()

                alternativas = {
                    "A": row["DESC_ALTER_A"].strip(),
                    "B": row["DESC_ALTER_B"].strip(),
                    "C": row["DESC_ALTER_C"].strip(),
                    "D": row["DESC_ALTER_D"].strip(),
                    "E": row["DESC_ALTER_E"].strip(),
                }

                # Parse de parâmetros da TRI com suporte a vírgula ou ponto
                def parse_float(val: Optional[str]) -> Optional[float]:
                    if not val or val.strip() == "":
                        return None
                    try:
                        return float(val.strip().replace(",", "."))
                    except ValueError:
                        return None

                metadados = {
                    "co_posicao": int(row["CO_POSICAO"].strip()) if row.get("CO_POSICAO", "").strip().isdigit() else None,
                    "co_prova": int(row["CO_PROVA"].strip()) if row.get("CO_PROVA", "").strip().isdigit() else None,
                    "tx_cor": row.get("TX_COR", "").strip(),
                    "tp_aplicacao": row.get("TP_APLICACAO", "").strip(),
                    "ref_arquivo_pdf": row.get("REF_ARQUIVO_PDF", "").strip(),
                    "tri": {
                        "param_a": parse_float(row.get("NU_PARAM_A")),
                        "param_b": parse_float(row.get("NU_PARAM_B")),
                        "param_c": parse_float(row.get("NU_PARAM_C")),
                    },
                    "in_item_adaptado": row.get("IN_ITEM_ADAPTADO", "").strip() or None,
                    "in_item_imagem": int(row.get("IN_ITEM_IMAGEM", "0").strip()) if row.get("IN_ITEM_IMAGEM", "").strip().isdigit() else 0,
                }

                items.append({
                    "co_item": co_item,
                    "ano": ano,
                    "habilidade_codigo": hab_code,
                    "enunciado": enunciado,
                    "alternativas": alternativas,
                    "gabarito": gabarito,
                    "metadados": metadados,
                })

            except Exception as e:
                logger.warning(f"Erro na linha {line_num} (CO_ITEM={row.get('CO_ITEM')}): {e}")

    return items


def seed_questoes(
    csv_path: str = "data/itens_prova_2009_2024_enriquecido.csv",
    db_url: Optional[str] = None,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Popula a tabela questoes_enem a partir do CSV enriquecido de forma idempotente.
    """
    logger.info(f"Iniciando leitura do CSV: {csv_path}")
    items = parse_csv_rows(csv_path)
    total_parsed = len(items)
    logger.info(f"Total de questões lidas e validadas: {total_parsed}")

    logger.info(f"Total de questões disponíveis para simulados e treino: {total_parsed} itens (2009-2024)")

    if dry_run:
        logger.info("[DRY-RUN] Nenhuma alteração persistida no banco de dados.")
        return {
            "total_parsed": total_parsed,
            "inserted": 0,
            "updated": 0,
        }

    target_url = db_url or settings.DATABASE_URL
    engine = create_engine(target_url)

    # 1. Garante que todas as tabelas do sistema existam (auto-healing para banco novo)
    Base.metadata.create_all(bind=engine)
    logger.info("Estrutura de tabelas verificada/criada com sucesso.")

    SessionMaker = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session: Session = SessionMaker()

    try:
        # 2. Garantir que as habilidades existam
        habilidades_existentes = set(session.scalars(select(HabilidadeEnem.codigo)).all())
        if len(habilidades_existentes) < len(HABILIDADES_MAT):
            logger.info("Populando habilidades da Matriz de Referência no banco...")
            for hab in HABILIDADES_MAT:
                if hab["codigo"] not in habilidades_existentes:
                    session.add(HabilidadeEnem(
                        codigo=hab["codigo"],
                        competencia=hab["competencia"],
                        descricao=hab["descricao"],
                        eixo_tematico=hab["eixo_tematico"]
                    ))
            session.commit()
            logger.info("Habilidades populadas com sucesso.")

        # 2. Carga idempotente das questões
        inserted_count = 0
        updated_count = 0

        # Para compatibilidade com SQLite (testes) e PostgreSQL (produção)
        is_postgres = "postgresql" in target_url

        for item in items:
            if is_postgres:
                stmt = pg_insert(QuestaoEnem).values(
                    co_item=item["co_item"],
                    ano=item["ano"],
                    habilidade_codigo=item["habilidade_codigo"],
                    enunciado=item["enunciado"],
                    alternativas=item["alternativas"],
                    gabarito=item["gabarito"],
                    metadados=item["metadados"],
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=["co_item"],
                    set_={
                        "ano": stmt.excluded.ano,
                        "habilidade_codigo": stmt.excluded.habilidade_codigo,
                        "enunciado": stmt.excluded.enunciado,
                        "alternativas": stmt.excluded.alternativas,
                        "gabarito": stmt.excluded.gabarito,
                        "metadados": stmt.excluded.metadados,
                    }
                )
                session.execute(stmt)
                inserted_count += 1
            else:
                existing = session.query(QuestaoEnem).filter_by(co_item=item["co_item"]).first()
                if existing:
                    existing.ano = item["ano"]
                    existing.habilidade_codigo = item["habilidade_codigo"]
                    existing.enunciado = item["enunciado"]
                    existing.alternativas = item["alternativas"]
                    existing.gabarito = item["gabarito"]
                    existing.metadados = item["metadados"]
                    updated_count += 1
                else:
                    new_q = QuestaoEnem(
                        co_item=item["co_item"],
                        ano=item["ano"],
                        habilidade_codigo=item["habilidade_codigo"],
                        enunciado=item["enunciado"],
                        alternativas=item["alternativas"],
                        gabarito=item["gabarito"],
                        metadados=item["metadados"],
                    )
                    session.add(new_q)
                    inserted_count += 1

        session.commit()
        logger.info(f"Carga concluída com sucesso! Processados: {inserted_count + updated_count} itens.")
        return {
            "total_parsed": total_parsed,
            "inserted": inserted_count,
            "updated": updated_count,
        }

    except OperationalError as e:
        logger.error(f"Não foi possível conectar ao banco de dados em '{target_url}'.")
        logger.error("Certifique-se de que o PostgreSQL está rodando (ex: 'docker compose up -d postgres' ou 'sudo service postgresql start').")
        logger.error(f"Detalhe do erro: {e}")
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"Falha na carga de questões: {e}", exc_info=True)
        raise
    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Popula a tabela questoes_enem com itens enriquecidos do ENEM.")
    parser.add_argument("--csv", default="data/itens_prova_2009_2024_enriquecido.csv", help="Caminho do arquivo CSV")
    parser.add_argument("--db-url", default=None, help="DATABASE_URL alternativa (opcional)")
    parser.add_argument("--dry-run", action="store_true", help="Apenas valida o CSV sem persistir no banco")
    args = parser.parse_args()

    seed_questoes(csv_path=args.csv, db_url=args.db_url, dry_run=args.dry_run)
