"""
Serviço de geração e gerenciamento de Questões Inéditas de Matemática para o ENEM.
Implementa o fluxo de 4 etapas previsto na Seção 8 do pré-projeto / AGENTS.md:
1. Entrada: Habilidade-alvo da Matriz de Referência do ENEM.
2. Retrieval: Resgate determinístico de exemplos históricos no PostgreSQL (questoes_enem).
3. Geração: Prompt estruturado com CoT, few-shot e formato JSON estrito no LLM local.
4. Validação Estrutural Automática: Unicidade das alternativas, formato e gabarito (RN-Q01, RN-Q02).
"""

import time
import logging
import uuid
from typing import List, Dict, Any, Optional, Callable
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.models.habilidade import HabilidadeEnem
from app.db.models.questao_enem import QuestaoEnem
from app.db.models.questao_inedita import QuestaoInedita
from app.services.llm_client import LLMClient
from app.services.question_validator import validate_questao_inedita
from app.core.prompts import build_question_generation_prompt
from app.schemas.question import (
    BatchPopulationSummary,
    BatchPopulationItemResult
)

logger = logging.getLogger(__name__)


class QuestionService:
    """
    Serviço orquestrador para geração, validação e persistência de itens inéditos.
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()

    def retrieve_few_shot_examples(
        self,
        db: Session,
        habilidade_codigo: str,
        k: int = 2
    ) -> List[QuestaoEnem]:
        """
        Recupera determinística ou aleatoriamente itens reais do acervo histórico (questoes_enem)
        da mesma habilidade oficial para servirem de contexto few-shot.
        Atende à Seção 3.3 (Decisão de Engenharia: Questões no PostgreSQL).
        """
        clean_hab = habilidade_codigo.strip().upper()
        # Seleciona k questões aleatórias do banco relacional com a mesma habilidade
        exemplos = (
            db.query(QuestaoEnem)
            .filter(QuestaoEnem.habilidade_codigo == clean_hab)
            .order_by(func.random())
            .limit(k)
            .all()
        )
        return exemplos

    def generate_single_questao_inedita(
        self,
        db: Session,
        habilidade_codigo: str,
        num_few_shot: int = 2,
        max_attempts: int = 3,
        temperature: float = 0.7,
        top_p: float = 0.9
    ) -> QuestaoInedita:
        """
        Executa o pipeline completo de geração de uma questão inédita:
        1. Validação da habilidade.
        2. Retrieval relacional no PostgreSQL.
        3. Geração de item via Ollama local (format='json').
        4. Validação estrutural rigorosa (RN-Q01, RN-Q02) com política de re-tentativa.
        5. Persistência no PostgreSQL na tabela questoes_ineditas.
        """
        clean_hab = habilidade_codigo.strip().upper()

        # 1. Valida se a habilidade existe na Matriz oficial
        habilidade = db.get(HabilidadeEnem, clean_hab)
        if not habilidade:
            raise ValueError(f"Habilidade '{clean_hab}' não encontrada na Matriz de Referência do ENEM.")

        # 2. Retrieval determinístico de exemplos históricos no PostgreSQL
        few_shot_itens = self.retrieve_few_shot_examples(db, clean_hab, k=num_few_shot)
        few_shot_dicts = [
            {
                "ano": item.ano,
                "enunciado": item.enunciado,
                "alternativas": item.alternativas,
                "gabarito": item.gabarito
            }
            for item in few_shot_itens
        ]

        logger.info(
            f"Gerando questão inédita para {clean_hab} "
            f"({len(few_shot_dicts)} exemplos few-shot recuperados do PostgreSQL)..."
        )

        # 3. Montagem do prompt estruturado
        prompt = build_question_generation_prompt(
            habilidade_codigo=habilidade.codigo,
            habilidade_descricao=habilidade.descricao,
            competencia=habilidade.competencia,
            eixo_tematico=habilidade.eixo_tematico,
            few_shot_exemplos=few_shot_dicts
        )

        last_error = None
        for attempt in range(1, max_attempts + 1):
            logger.info(f"Tentativa {attempt}/{max_attempts} de geração para {clean_hab}...")

            # 4. Inferência via LLM com formato JSON estrito
            raw_output = self.llm_client.generate(
                prompt=prompt,
                max_tokens=1024,
                temperature=temperature,
                top_p=top_p,
                format="json"
            )

            # 5. Validação estrutural automática (RN-Q01, RN-Q02)
            is_valid, error_msg, validated_item = validate_questao_inedita(
                raw_output=raw_output,
                few_shot_exemplos=few_shot_dicts
            )

            if is_valid and validated_item:
                logger.info(f"Item para {clean_hab} gerado e validado com sucesso na tentativa {attempt}!")

                # 6. Persistência no PostgreSQL
                nova_questao = QuestaoInedita(
                    id=uuid.uuid4(),
                    habilidade_codigo=habilidade.codigo,
                    enunciado=validated_item.enunciado,
                    alternativas=validated_item.alternativas,
                    gabarito=validated_item.gabarito,
                    justificativa=validated_item.justificativa,
                    thought_scratchpad=validated_item.thought_scratchpad,
                    is_validated=True
                )

                db.add(nova_questao)
                db.commit()
                db.refresh(nova_questao)
                return nova_questao
            else:
                last_error = error_msg
                logger.warning(
                    f"Falha na validação do item para {clean_hab} (tentativa {attempt}/{max_attempts}): {error_msg}"
                )

        raise ValueError(
            f"RN-Q01: Não foi possível gerar uma questão inédita válida para {clean_hab} após {max_attempts} tentativas. "
            f"Último erro: {last_error}"
        )

    def generate_batch(
        self,
        db: Session,
        habilidades: Optional[List[str]] = None,
        count_per_habilidade: int = 1,
        num_few_shot: int = 2,
        on_progress: Optional[Callable[[str, int, int, bool, Optional[str]], None]] = None
    ) -> BatchPopulationSummary:
        """
        Executa a geração em lote de questões inéditas para uma lista de habilidades
        ou para todas as 30 habilidades cadastradas no ENEM.
        """
        start_time = time.time()

        # Se não especificou, busca todas as habilidades cadastradas na Matriz
        if not habilidades:
            all_habs = db.query(HabilidadeEnem).order_by(HabilidadeEnem.codigo).all()
            target_codes = [h.codigo for h in all_habs]
        else:
            target_codes = [h.strip().upper() for h in habilidades]

        results: List[BatchPopulationItemResult] = []
        total_success = 0
        total_failures = 0
        total_operations = len(target_codes) * count_per_habilidade
        current_op = 0

        for hab_code in target_codes:
            for item_idx in range(1, count_per_habilidade + 1):
                current_op += 1
                op_start = time.time()
                try:
                    questao = self.generate_single_questao_inedita(
                        db=db,
                        habilidade_codigo=hab_code,
                        num_few_shot=num_few_shot,
                        max_attempts=3
                    )
                    elapsed = round(time.time() - op_start, 2)
                    total_success += 1
                    result_item = BatchPopulationItemResult(
                        habilidade_codigo=hab_code,
                        questao_id=questao.id,
                        success=True,
                        attempts=1,
                        elapsed_seconds=elapsed
                    )
                    results.append(result_item)
                    if on_progress:
                        on_progress(hab_code, current_op, total_operations, True, None)

                except Exception as e:
                    elapsed = round(time.time() - op_start, 2)
                    total_failures += 1
                    err_msg = str(e)
                    result_item = BatchPopulationItemResult(
                        habilidade_codigo=hab_code,
                        questao_id=None,
                        success=False,
                        attempts=3,
                        error=err_msg,
                        elapsed_seconds=elapsed
                    )
                    results.append(result_item)
                    if on_progress:
                        on_progress(hab_code, current_op, total_operations, False, err_msg)

        total_elapsed = round(time.time() - start_time, 2)
        return BatchPopulationSummary(
            total_habilidades_processadas=len(target_codes),
            total_sucesso=total_success,
            total_falhas=total_failures,
            tempo_total_segundos=total_elapsed,
            itens=results
        )

    def list_questoes_ineditas(
        self,
        db: Session,
        habilidade_codigo: Optional[str] = None,
        skip: int = 0,
        limit: int = 50
    ) -> List[QuestaoInedita]:
        """Consulta questões inéditas geradas com paginação e filtro por habilidade."""
        query = db.query(QuestaoInedita)
        if habilidade_codigo:
            query = query.filter(QuestaoInedita.habilidade_codigo == habilidade_codigo.strip().upper())
        return query.order_by(QuestaoInedita.created_at.desc()).offset(skip).limit(limit).all()

    def get_questao_inedita_by_id(
        self,
        db: Session,
        questao_id: uuid.UUID
    ) -> Optional[QuestaoInedita]:
        """Recupera uma questão inédita específica pelo UUID."""
        return db.get(QuestaoInedita, questao_id)
