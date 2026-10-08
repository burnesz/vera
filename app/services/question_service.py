"""
Serviço de geração e gerenciamento de Questões Inéditas de Matemática para o ENEM.
Implementa o fluxo RAG de 4 etapas previsto na Seção 8 do pré-projeto / AGENTS.md:
1. Entrada: Habilidade-alvo da Matriz de Referência do ENEM.
2. Retrieval RAG: Resgate semântico dos Top-3 itens históricos no Pinecone (namespace questoes_enem)
   ancorado nas queries otimizadas pelo Claude.
3. Geração: Prompt estruturado com CoT, three-shot e formato JSON estrito no LLM local (Ollama).
4. Validação Estrutural Automática: Unicidade das alternativas, formato e gabarito (RN-Q01, RN-Q02).
"""

import os
import json
import time
import logging
import uuid
from typing import List, Dict, Any, Optional, Callable
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.config import settings
from app.db.models.habilidade import HabilidadeEnem
from app.db.models.questao_enem import QuestaoEnem
from app.db.models.questao_inedita import QuestaoInedita
from app.services.llm_client import LLMClient
from app.services.vectorstore import PineconeVectorStore
from app.services.question_validator import (
    validate_questao_inedita,
    check_table_markdown_structure,
    extract_json_from_text,
    sanitize_latex_json_text,
    sanitize_parsed_dict_values
)
from app.services.code_executor import (
    execute_solver_code,
    validate_solver_consistency,
    assemble_alternatives_and_gabarito
)
from app.core.prompts import (
    build_question_generation_prompt,
    build_enunciado_solver_prompt,
    build_justificativa_prompt
)
from app.schemas.question import (
    QuestaoEnunciadoSolverOutput,
    QuestaoJustificativaOutput,
    BatchPopulationSummary,
    BatchPopulationItemResult
)
from pydantic import ValidationError

logger = logging.getLogger(__name__)


class QuestionService:
    """
    Serviço orquestrador para geração, validação e persistência de itens inéditos via RAG.
    """

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        vector_store: Optional[PineconeVectorStore] = None,
        queries_path: str = "data/habilidades_queries.json"
    ):
        self.llm_client = llm_client or LLMClient()
        self.vector_store = vector_store or PineconeVectorStore()
        self.queries_path = queries_path
        self._habilidades_queries = self._load_habilidades_queries()

    def _load_habilidades_queries(self) -> Dict[str, Dict[str, Any]]:
        """
        Carrega as queries semânticas expandidas das 30 habilidades do ENEM geradas pelo Claude.
        """
        mapping = {}
        if os.path.exists(self.queries_path):
            try:
                with open(self.queries_path, "r", encoding="utf-8") as f:
                    items = json.load(f)
                for item in items:
                    hab_cod = item.get("habilidade_codigo") or item.get("habilidade", "")
                    clean = hab_cod.strip().upper()
                    mapping[clean] = item
                    if clean.startswith("H"):
                        num_part = clean[1:]
                        if num_part.isdigit():
                            alt_key = f"H{int(num_part)}"
                            alt_key_padded = f"H{int(num_part):02d}"
                            mapping[alt_key] = item
                            mapping[alt_key_padded] = item
            except Exception as e:
                logger.warning(f"Erro ao carregar queries semânticas de '{self.queries_path}': {e}")
        return mapping

    def retrieve_few_shot_examples(
        self,
        db: Session,
        habilidade_codigo: str,
        k: int = 3
    ) -> List[QuestaoEnem]:
        """
        Recupera determinística ou aleatoriamente itens reais do acervo relacional (questoes_enem)
        da mesma habilidade oficial para servirem de fallback.
        """
        clean_hab = habilidade_codigo.strip().upper()
        if clean_hab.startswith("H") and clean_hab[1:].isdigit():
            clean_hab = f"H{int(clean_hab[1:]):02d}"

        exemplos = (
            db.query(QuestaoEnem)
            .filter(QuestaoEnem.habilidade_codigo == clean_hab)
            .order_by(func.random())
            .limit(k)
            .all()
        )
        return exemplos

    def retrieve_rag_few_shot_examples(
        self,
        habilidade_codigo: str,
        k: int = 3,
        db: Optional[Session] = None
    ) -> List[Dict[str, Any]]:
        """
        Recupera as Top-k questões históricas do ENEM mais similares semanticamente no Pinecone
        (namespace 'questoes_enem') utilizando a query expandida da habilidade.
        """
        clean_hab = habilidade_codigo.strip().upper()
        if clean_hab.startswith("H") and clean_hab[1:].isdigit():
            clean_hab = f"H{int(clean_hab[1:]):02d}"

        hab_data = self._habilidades_queries.get(clean_hab)
        if hab_data and hab_data.get("query"):
            query_text = hab_data["query"]
        else:
            query_text = f"Questão de matemática do ENEM avaliando a habilidade {clean_hab}."

        try:
            results = self.vector_store.search(
                query=query_text,
                namespace=settings.NAMESPACE_QUESTOES_ENEM,
                top_k=k
            )

            few_shot_dicts = []
            for r in results:
                meta = r.get("metadata", {})
                enunciado = meta.get("text") or r.get("text", "")
                alternativas = {
                    "A": meta.get("alt_a", ""),
                    "B": meta.get("alt_b", ""),
                    "C": meta.get("alt_c", ""),
                    "D": meta.get("alt_d", ""),
                    "E": meta.get("alt_e", "")
                }
                few_shot_dicts.append({
                    "co_item": meta.get("co_item"),
                    "ano": meta.get("ano", "ENEM"),
                    "habilidade_origem": meta.get("habilidade_codigo"),
                    "enunciado": enunciado,
                    "alternativas": alternativas,
                    "gabarito": meta.get("gabarito", ""),
                    "score": r.get("score", 0.0)
                })

            if few_shot_dicts:
                scores_str = ", ".join([f"{x['score']:.3f}" for x in few_shot_dicts])
                logger.info(
                    f"RAG: {len(few_shot_dicts)} exemplos resgatados no Pinecone para {clean_hab} (scores: [{scores_str}])."
                )
                return few_shot_dicts

        except Exception as e:
            logger.warning(f"Falha na recuperação RAG via Pinecone para {clean_hab}: {e}. Acionando fallback relacional...")

        # Fallback relacional no PostgreSQL caso Pinecone falhe ou não retorne resultados
        if db:
            itens_db = self.retrieve_few_shot_examples(db, clean_hab, k=k)
            return [
                {
                    "ano": item.ano,
                    "enunciado": item.enunciado,
                    "alternativas": item.alternativas,
                    "gabarito": item.gabarito,
                    "score": 1.0
                }
                for item in itens_db
            ]

        return []

    def generate_single_questao_inedita(
        self,
        db: Session,
        habilidade_codigo: str,
        num_few_shot: int = 3,
        max_attempts: int = 3,
        temperature: float = 0.2,
        top_p: float = 0.9,
        use_pot: bool = True
    ) -> QuestaoInedita:
        """
        Executa o pipeline RAG de geração de uma questão inédita:
        1. Validação da habilidade na Matriz oficial do ENEM.
        2. Retrieval RAG semântico dos Top-k exemplos no namespace 'questoes_enem' do Pinecone.
        3. Geração via Program-Aided Generation (PoT):
           - Fase 1: LLM gera situação-problema e def resolver() em Python.
           - Execução isolada em subprocess com timeout e verificação de AST de segurança.
           - Validação de nexo numérico (groundedness) e unicidade estrita das 5 alternativas.
           - Embaralhamento programático das alternativas e definição determinística do gabarito.
           - Fase 2: LLM redige justificativa pedagógica com gabarito comprovado.
        4. Fallback/Modo comparativo: Caso use_pot=False, executa geração clássica de 1 fase com CoT e validação.
        5. Persistência na tabela questoes_ineditas no PostgreSQL.
        """
        clean_hab = habilidade_codigo.strip().upper()
        if clean_hab.startswith("H") and clean_hab[1:].isdigit():
            clean_hab = f"H{int(clean_hab[1:]):02d}"

        # 1. Valida se a habilidade existe na Matriz oficial
        habilidade = db.get(HabilidadeEnem, clean_hab)
        if not habilidade:
            raise ValueError(f"Habilidade '{clean_hab}' não encontrada na Matriz de Referência do ENEM.")

        # 2. Retrieval RAG semântico no Pinecone (Top-k exemplos mais similares)
        few_shot_dicts = self.retrieve_rag_few_shot_examples(
            habilidade_codigo=clean_hab,
            k=num_few_shot,
            db=db
        )

        if use_pot:
            return self._generate_pot_item(
                db=db,
                habilidade=habilidade,
                few_shot_dicts=few_shot_dicts,
                max_attempts=max_attempts,
                temperature=temperature,
                top_p=top_p
            )
        else:
            return self._generate_traditional_item(
                db=db,
                habilidade=habilidade,
                few_shot_dicts=few_shot_dicts,
                max_attempts=max_attempts,
                temperature=temperature if temperature != 0.2 else 0.7,
                top_p=top_p
            )

    def _generate_pot_item(
        self,
        db: Session,
        habilidade: HabilidadeEnem,
        few_shot_dicts: List[Dict[str, Any]],
        max_attempts: int = 3,
        temperature: float = 0.2,
        top_p: float = 0.9
    ) -> QuestaoInedita:
        """
        Geração Program-Aided (PoT) com execução de código, checagem de nexo numérico
        e montagem algorítmica de alternativas/gabarito.
        """
        clean_hab = habilidade.codigo
        logger.info(
            f"Gerando questão inédita via PoT para {clean_hab} "
            f"({len(few_shot_dicts)} exemplos RAG para ancoragem)..."
        )

        last_error: Optional[str] = None
        referencia_enem = few_shot_dicts[0] if few_shot_dicts else None

        for attempt in range(1, max_attempts + 1):
            logger.info(f"PoT: Tentativa {attempt}/{max_attempts} para {clean_hab}...")

            # --- FASE 1: LLM GERA ENUNCIADO E SOLVER ---
            prompt_pot = build_enunciado_solver_prompt(
                habilidade_codigo=habilidade.codigo,
                habilidade_descricao=habilidade.descricao,
                competencia=habilidade.competencia,
                eixo_tematico=habilidade.eixo_tematico,
                exemplo_referencia=referencia_enem,
                feedback_erro=last_error
            )

            try:
                raw_pot_output = self.llm_client.generate(
                    prompt=prompt_pot,
                    max_tokens=1024,
                    temperature=temperature,
                    top_p=top_p,
                    format="json"
                )
            except Exception as e:
                last_error = f"Falha na chamada ao LLM (Fase 1 PoT): {e}"
                logger.warning(f"Tentativa {attempt}/{max_attempts} falhou na inferência: {e}")
                continue

            # Parsing e decodificação JSON com sanitização de LaTeX
            try:
                json_str = extract_json_from_text(raw_pot_output)
                sanitized_json = sanitize_latex_json_text(json_str)
                parsed_data = json.loads(sanitized_json, strict=False)
                parsed_data = sanitize_parsed_dict_values(parsed_data)
            except Exception as e:
                last_error = f"Erro ao decodificar JSON gerado pelo LLM: {e}"
                logger.warning(f"Tentativa {attempt}/{max_attempts} falhou no JSON: {e}")
                continue

            # Suporte resiliente a modelos ou mocks legados que retornaram formato tradicional
            if "solver" not in parsed_data and "alternativas" in parsed_data and "gabarito" in parsed_data:
                logger.info("Detectado formato com alternativas prontas (sem solver). Validando via RN-Q01/Q02...")
                is_valid, err_msg, validated_item = validate_questao_inedita(
                    raw_output=raw_pot_output,
                    few_shot_exemplos=few_shot_dicts
                )
                if is_valid and validated_item:
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
                    last_error = err_msg
                    continue

            # Validação do Schema Pydantic da Fase 1
            try:
                pot_output = QuestaoEnunciadoSolverOutput(**parsed_data)
            except ValidationError as e:
                last_error = f"Erro no schema do solver: {e.errors()}"
                logger.warning(f"Tentativa {attempt}/{max_attempts} falhou no schema Pydantic: {e}")
                continue

            # Validação estrutural de formatação de tabela Markdown (se anunciada)
            is_table_valid, table_err = check_table_markdown_structure(pot_output.enunciado)
            if not is_table_valid:
                last_error = table_err
                logger.warning(f"Tentativa {attempt}/{max_attempts} falhou na formatação da tabela: {table_err}")
                continue

            # --- EXECUÇÃO DO SOLVER EM SUBPROCESS ISOLADO ---
            try:
                solver_result = execute_solver_code(pot_output.solver, timeout=5)
            except Exception as e:
                last_error = f"Erro na execução da função resolver(): {e}"
                logger.warning(f"Tentativa {attempt}/{max_attempts} falhou na execução do código: {e}")
                continue

            # --- CHECAGEM DE CONSISTÊNCIA E NEXO NUMÉRICO (GROUNDEDNESS) ---
            try:
                formatted_values = validate_solver_consistency(
                    enunciado=pot_output.enunciado,
                    code=pot_output.solver,
                    result=solver_result
                )
            except Exception as e:
                last_error = f"Erro de consistência matemática ou nexo numérico: {e}"
                logger.warning(f"Tentativa {attempt}/{max_attempts} falhou na checagem de nexo: {e}")
                continue

            # --- MONTAGEM ALGORÍTMICA DE ALTERNATIVAS E GABARITO ---
            alternativas, gabarito = assemble_alternatives_and_gabarito(formatted_values)

            # --- FASE 2: GERAÇÃO DA JUSTIFICATIVA PEDAGÓGICA ---
            justificativa_texto = self._generate_justificativa_fase2(
                enunciado=pot_output.enunciado,
                alternativas=alternativas,
                gabarito=gabarito,
                solver_code=pot_output.solver
            )

            logger.info(
                f"Item PoT para {clean_hab} gerado e comprovado com sucesso na tentativa {attempt}! "
                f"Gabarito: {gabarito} ({alternativas[gabarito]})."
            )

            # --- PERSISTÊNCIA NO POSTGRESQL ---
            nova_questao = QuestaoInedita(
                id=uuid.uuid4(),
                habilidade_codigo=habilidade.codigo,
                enunciado=pot_output.enunciado,
                alternativas=alternativas,
                gabarito=gabarito,
                justificativa=justificativa_texto,
                thought_scratchpad=f"# Solver Python validado via PoT:\n{pot_output.solver}",
                is_validated=True
            )
            db.add(nova_questao)
            db.commit()
            db.refresh(nova_questao)
            return nova_questao

        raise ValueError(
            f"RN-Q01 (PoT): Não foi possível gerar uma questão inédita válida para {clean_hab} após {max_attempts} tentativas. "
            f"Último erro: {last_error}"
        )

    def _generate_justificativa_fase2(
        self,
        enunciado: str,
        alternativas: Dict[str, str],
        gabarito: str,
        solver_code: str
    ) -> str:
        """
        Fase 2 do PoT: Redige a justificativa pedagógica com gabarito comprovado por código.
        """
        prompt_just = build_justificativa_prompt(
            enunciado=enunciado,
            alternativas=alternativas,
            gabarito=gabarito,
            solver_code=solver_code
        )

        try:
            raw_just = self.llm_client.generate(
                prompt=prompt_just,
                max_tokens=600,
                temperature=0.3,
                top_p=0.9,
                format="json"
            )
            json_str = extract_json_from_text(raw_just)
            sanitized = sanitize_latex_json_text(json_str)
            parsed = json.loads(sanitized, strict=False)
            parsed = sanitize_parsed_dict_values(parsed)
            just_obj = QuestaoJustificativaOutput(**parsed)
            return just_obj.justificativa
        except Exception as e:
            logger.warning(f"Aviso ao gerar justificativa estruturada na Fase 2: {e}. Usando fallback formatado.")
            correta_val = alternativas.get(gabarito, "")
            return (
                f"A alternativa correta é a {gabarito} ({correta_val}), "
                f"conforme resolução matemática comprovada pelo solver da questão."
            )

    def _generate_traditional_item(
        self,
        db: Session,
        habilidade: HabilidadeEnem,
        few_shot_dicts: List[Dict[str, Any]],
        max_attempts: int = 3,
        temperature: float = 0.7,
        top_p: float = 0.9
    ) -> QuestaoInedita:
        """
        Geração clássica de 1 fase com CoT e validação via validate_questao_inedita.
        """
        clean_hab = habilidade.codigo
        logger.info(
            f"Gerando questão inédita (modo tradicional) para {clean_hab} "
            f"({len(few_shot_dicts)} exemplos RAG three-shot)..."
        )

        prompt = build_question_generation_prompt(
            habilidade_codigo=habilidade.codigo,
            habilidade_descricao=habilidade.descricao,
            competencia=habilidade.competencia,
            eixo_tematico=habilidade.eixo_tematico,
            few_shot_exemplos=few_shot_dicts
        )

        last_error = None
        for attempt in range(1, max_attempts + 1):
            logger.info(f"Tentativa tradicional {attempt}/{max_attempts} de geração para {clean_hab}...")

            raw_output = self.llm_client.generate(
                prompt=prompt,
                max_tokens=1024,
                temperature=temperature,
                top_p=top_p,
                format="json"
            )

            is_valid, error_msg, validated_item = validate_questao_inedita(
                raw_output=raw_output,
                few_shot_exemplos=few_shot_dicts
            )

            if is_valid and validated_item:
                logger.info(f"Item para {clean_hab} gerado e validado com sucesso na tentativa {attempt}!")
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
        num_few_shot: int = 3,
        use_pot: bool = True,
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
                        max_attempts=3,
                        use_pot=use_pot
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
