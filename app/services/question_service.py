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
import random
from typing import List, Dict, Any, Optional, Callable, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.config import settings
from app.db.models.habilidade import HabilidadeEnem
from app.db.models.questao_enem import QuestaoEnem
from app.db.models.questao_inedita import QuestaoInedita
from app.services.llm_client import LLMClient
from app.services.vectorstore import PineconeVectorStore
from app.services.question_validator import (
    extract_json_from_text,
    sanitize_latex_json_text,
    sanitize_parsed_dict_values,
    format_enunciado_with_table
)
from app.services.code_executor import (
    execute_solver_code,
    validate_solver_consistency,
    assemble_alternatives_and_gabarito
)
from app.core.prompts import (
    build_enunciado_solver_prompt,
    build_blind_solving_prompt,
    build_equivalencia_gabarito_prompt,
    build_auditoria_semantica_prompt,
    sortear_contexto_criativo,
    TEMAS_COTIDIANO,
    FORMAS_ABERTURA
)
from app.schemas.question import (
    QuestaoEnunciadoSolverOutput,
    QuestaoBlindSolvingOutput,
    QuestaoEquivalenciaOutput,
    QuestaoAuditoriaSemanticaOutput,
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
        k: int = 2,
        top_candidates: int = 10,
        db: Optional[Session] = None
    ) -> List[Dict[str, Any]]:
        """
        Recupera os Top-candidates (padrão 10) itens históricos do ENEM mais similares
        semanticamente no Pinecone (namespace 'questoes_enem') e sorteia k exemplos (padrão 2)
        para compor o contexto few-shot, maximizando a diversidade e relevância.
        """
        clean_hab = habilidade_codigo.strip().upper()
        if clean_hab.startswith("H") and clean_hab[1:].isdigit():
            clean_hab = f"H{int(clean_hab[1:]):02d}"

        hab_data = self._habilidades_queries.get(clean_hab)
        if hab_data and hab_data.get("query"):
            query_text = hab_data["query"]
        else:
            query_text = f"Questão de matemática do ENEM avaliando a habilidade {clean_hab}."

        fetch_limit = max(top_candidates, k)

        try:
            results = self.vector_store.search(
                query=query_text,
                namespace=settings.NAMESPACE_QUESTOES_ENEM,
                top_k=fetch_limit
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
                total_encontrados = len(few_shot_dicts)
                if total_encontrados > k:
                    few_shot_dicts = random.sample(few_shot_dicts, k=k)
                    few_shot_dicts.sort(key=lambda x: x.get("score", 0.0), reverse=True)

                scores_str = ", ".join([f"{x['score']:.3f}" for x in few_shot_dicts])
                logger.info(
                    f"RAG: {len(few_shot_dicts)} exemplos sorteados dentre os Top-{total_encontrados} "
                    f"do Pinecone para {clean_hab} (scores: [{scores_str}])."
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
        num_few_shot: int = 2,
        max_attempts: int = 4,
        temperature: float = 0.0,
        top_p: float = 0.9,
        tema: Optional[str] = None,
        abertura: Optional[str] = None
    ) -> QuestaoInedita:
        """
        Executa o pipeline RAG de geração de uma questão inédita via Program-Aided Generation (PoT):
        1. Validação da habilidade na Matriz oficial do ENEM.
        2. Retrieval RAG semântico dos Top-k exemplos no namespace 'questoes_enem' do Pinecone.
        3. Geração via Program-Aided Generation (PoT):
           - Fase 1: LLM gera situação-problema e def resolver() em Python.
           - Execução isolada em subprocess com timeout e verificação de AST de segurança.
           - Validação de nexo numérico (groundedness) e unicidade estrita das 5 alternativas.
           - Embaralhamento programático das alternativas e definição determinística do gabarito.
           - Fase 2: LLM redige justificativa pedagógica com gabarito comprovado.
        4. Persistência na tabela questoes_ineditas no PostgreSQL.
        """
        clean_hab = habilidade_codigo.strip().upper()
        if clean_hab.startswith("H") and clean_hab[1:].isdigit():
            clean_hab = f"H{int(clean_hab[1:]):02d}"

        # 1. Valida se a habilidade existe na Matriz oficial
        habilidade = db.get(HabilidadeEnem, clean_hab)
        if not habilidade:
            raise ValueError(f"Habilidade '{clean_hab}' não encontrada na Matriz de Referência do ENEM.")

        # 2. Sorteia contexto criativo caso não tenha sido fixado
        if not tema and not abertura:
            tema, abertura = sortear_contexto_criativo()

        # 3. Retrieval RAG semântico no Pinecone (Top-k exemplos mais similares)
        few_shot_dicts = self.retrieve_rag_few_shot_examples(
            habilidade_codigo=clean_hab,
            k=num_few_shot,
            db=db
        )

        return self._generate_pot_item(
            db=db,
            habilidade=habilidade,
            few_shot_dicts=few_shot_dicts,
            max_attempts=max_attempts,
            temperature=temperature,
            top_p=top_p,
            tema=tema,
            abertura=abertura
        )

    def _generate_pot_item(
        self,
        db: Session,
        habilidade: HabilidadeEnem,
        few_shot_dicts: List[Dict[str, Any]],
        max_attempts: int = 4,
        temperature: float = 0.0,
        top_p: float = 0.9,
        tema: Optional[str] = None,
        abertura: Optional[str] = None
    ) -> QuestaoInedita:
        """
        Geração Program-Aided (PoT) com execução de código, checagem de nexo numérico
        e montagem algorítmica de alternativas/gabarito.
        """
        clean_hab = habilidade.codigo
        if not tema and not abertura:
            tema, abertura = sortear_contexto_criativo()

        logger.info(
            f"Gerando questão inédita via PoT para {clean_hab} "
            f"(Tema: '{tema}' | Abertura: '{abertura}' | {len(few_shot_dicts)} exemplos RAG para ancoragem)..."
        )

        last_error: Optional[str] = None
        enunciado_anterior: Optional[str] = None
        solver_anterior: Optional[str] = None

        for attempt in range(1, max_attempts + 1):
            # Se for retry após falha estrutural, aplica amostragem independente (Stateless Retry)
            if attempt > 1:
                curr_tema, curr_abertura = sortear_contexto_criativo()
                curr_few_shot = self.retrieve_rag_few_shot_examples(
                    habilidade_codigo=clean_hab,
                    k=len(few_shot_dicts) or 2,
                    db=db
                )
                curr_temp = min(temperature + 0.1 * (attempt - 1), 0.6)
                logger.info(
                    f"PoT Stateless Retry: Tentativa limpa {attempt}/{max_attempts} para {clean_hab} "
                    f"(Novo tema: '{curr_tema}' | Temp: {curr_temp:.1f})..."
                )
            else:
                curr_tema = tema
                curr_abertura = abertura
                curr_few_shot = few_shot_dicts
                curr_temp = temperature
                logger.info(f"PoT: Tentativa {attempt}/{max_attempts} para {clean_hab}...")

            # Geração limpa sem poluição de contexto ou ancoragem em erros anteriores (Stateless)
            prompt_pot = build_enunciado_solver_prompt(
                habilidade_codigo=habilidade.codigo,
                habilidade_descricao=habilidade.descricao,
                competencia=habilidade.competencia,
                eixo_tematico=habilidade.eixo_tematico,
                exemplos_referencia=curr_few_shot,
                feedback_erro=None,
                tema=curr_tema,
                abertura=curr_abertura
            )

            try:
                raw_pot_output = self.llm_client.generate(
                    prompt=prompt_pot,
                    max_tokens=1536,
                    temperature=curr_temp,
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

            # Validação do Schema Pydantic da Fase 1 (exige solver em Python)
            try:
                pot_output = QuestaoEnunciadoSolverOutput(**parsed_data)
                
                # Conversão e higienização da tabela nativa para Markdown (se existir)
                if pot_output.tabela_dados:
                    try:
                        pot_output.enunciado = format_enunciado_with_table(
                            enunciado=pot_output.enunciado,
                            tabela_dados=pot_output.tabela_dados
                        )
                    except Exception as e:
                        logger.warning(f"Aviso ao formatar tabela_dados para Markdown: {e}")
                
                enunciado_anterior = pot_output.enunciado
                solver_anterior = pot_output.solver
            except ValidationError as e:
                last_error = f"Erro no schema do solver: {e.errors()}"
                logger.warning(f"Tentativa {attempt}/{max_attempts} falhou no schema Pydantic: {e}")
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

            # --- VALIDAÇÃO ETAPA 1: RESOLUÇÃO CEGA PURA (Zero Alternativas) ---
            try:
                blind_sol = self._run_blind_solving(enunciado=pot_output.enunciado)
            except Exception as e:
                last_error = f"Falha na resolução cega da LLM: {e}"
                logger.warning(f"Tentativa {attempt}/{max_attempts} falhou na resolução cega: {e}")
                continue

            # --- VALIDAÇÃO ETAPA 2: CONFRONTO DIRETO DE EQUIVALÊNCIA (com Early Exit) ---
            try:
                equiv = self._run_equivalence_check(
                    resultado_solver=solver_result["correta"],
                    resultado_obtido=blind_sol.resultado_obtido,
                    enunciado=pot_output.enunciado
                )
            except Exception as e:
                last_error = f"Falha no confronto de equivalência: {e}"
                logger.warning(f"Tentativa {attempt}/{max_attempts} falhou na equivalência: {e}")
                continue

            if not equiv.equivalentes:
                motivo = equiv.explicacao_equivalencia or "Divergência conceitual ou numérica entre o solver e a resolução cega."
                last_error = f"Divergência matemática no confronto: {motivo}"
                logger.warning(
                    f"Tentativa {attempt}/{max_attempts} descartada por divergência (Early Exit): "
                    f"Solver='{solver_result['correta']}' vs LLM='{blind_sol.resultado_obtido}' | Motivo: {motivo}"
                )
                continue

            # --- VALIDAÇÃO ETAPA 3: AUDITORIA SEMÂNTICA E PEDAGÓGICA ---
            try:
                audit = self._run_semantic_audit(
                    enunciado=pot_output.enunciado,
                    alternativas=alternativas
                )
            except Exception as e:
                last_error = f"Falha na auditoria semântica: {e}"
                logger.warning(f"Tentativa {attempt}/{max_attempts} falhou na auditoria semântica: {e}")
                continue

            if not audit.aprovada:
                last_error = f"Rejeição semântica: {audit.motivo_rejeicao}"
                logger.warning(f"Tentativa {attempt}/{max_attempts} falhou na auditoria semântica: {audit.motivo_rejeicao}")
                continue

            logger.info(
                f"Item PoT para {clean_hab} gerado, comprovado e validado nas 3 etapas com sucesso na tentativa {attempt}! "
                f"Gabarito: {gabarito} ({alternativas[gabarito]})."
            )

            # --- PERSISTÊNCIA NO POSTGRESQL ---
            nova_questao = QuestaoInedita(
                id=uuid.uuid4(),
                habilidade_codigo=habilidade.codigo,
                enunciado=pot_output.enunciado,
                alternativas=alternativas,
                gabarito=gabarito,
                justificativa=blind_sol.resolucao_passo_a_passo,
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

    def _run_blind_solving(self, enunciado: str) -> QuestaoBlindSolvingOutput:
        """
        Etapa 1 da Validação: Resolução Cega Pura.
        A LLM recebe exclusivamente o enunciado e deduz a resolução e o resultado obtido.
        """
        prompt = build_blind_solving_prompt(enunciado=enunciado)
        raw = self.llm_client.generate(
            prompt=prompt,
            max_tokens=1536,
            temperature=0.0,
            top_p=0.9,
            format="json"
        )
        json_str = extract_json_from_text(raw)
        sanitized = sanitize_latex_json_text(json_str)
        parsed = json.loads(sanitized, strict=False)
        parsed = sanitize_parsed_dict_values(parsed)

        if isinstance(parsed, dict):
            if "resolucao_passo_a_passo" not in parsed:
                parsed["resolucao_passo_a_passo"] = parsed.get("resolucao") or parsed.get("justificativa") or "Resolução detalhada."
            if "resultado_obtido" not in parsed:
                parsed["resultado_obtido"] = parsed.get("resultado", parsed.get("correta", ""))

        return QuestaoBlindSolvingOutput(**parsed)

    @staticmethod
    def _check_deterministic_equivalence(resultado_solver: Any, resultado_obtido: Any) -> bool:
        """
        Verifica equivalência numérica direta em Python (incluindo quando resultado_obtido
        é um dicionário com múltiplos grupos contendo o valor exato de resultado_solver).
        """
        try:
            solver_num = float(resultado_solver)
        except (ValueError, TypeError):
            return False

        candidates: List[Any] = []
        if isinstance(resultado_obtido, dict):
            candidates.extend(resultado_obtido.values())
        elif isinstance(resultado_obtido, (list, tuple)):
            candidates.extend(resultado_obtido)
        else:
            candidates.append(resultado_obtido)

        for cand in candidates:
            try:
                cand_num = float(cand)
                if abs(solver_num - cand_num) <= 1e-2:
                    return True
            except (ValueError, TypeError):
                continue
        return False

    def _run_equivalence_check(
        self,
        resultado_solver: Any,
        resultado_obtido: Any,
        enunciado: Optional[str] = None
    ) -> QuestaoEquivalenciaOutput:
        """
        Etapa 2 da Validação: Confronto Direto de Equivalência Matemática.
        Avalia se a resposta calculada pelo solver e o resultado deduzido pela LLM são equivalentes.
        """
        prompt = build_equivalencia_gabarito_prompt(
            resultado_solver=resultado_solver,
            resultado_obtido=resultado_obtido,
            enunciado=enunciado
        )
        raw = self.llm_client.generate(
            prompt=prompt,
            max_tokens=300,
            temperature=0.0,
            top_p=0.9,
            format="json"
        )
        json_str = extract_json_from_text(raw)
        sanitized = sanitize_latex_json_text(json_str)
        parsed = json.loads(sanitized, strict=False)
        parsed = sanitize_parsed_dict_values(parsed)

        if isinstance(parsed, dict):
            if "equivalentes" not in parsed:
                # Suporte a variações semânticas se o modelo responder "sao_equivalentes"
                parsed["equivalentes"] = bool(parsed.get("sao_equivalentes", True))

        equiv_out = QuestaoEquivalenciaOutput(**parsed)

        # Se o LLM retornou um dicionário na resolução cega contendo o valor exato do solver
        # e o juiz se confundiu com o formato dict, recupera deterministicamente
        if not equiv_out.equivalentes and isinstance(resultado_obtido, (dict, list)):
            if self._check_deterministic_equivalence(resultado_solver, resultado_obtido):
                equiv_out.equivalentes = True
                equiv_out.explicacao_equivalencia = (
                    f"Equivalência numérica confirmada deterministicamente: {resultado_solver} está contido em {resultado_obtido}."
                )

        return equiv_out

    def _run_semantic_audit(self, enunciado: str, alternativas: Dict[str, str]) -> QuestaoAuditoriaSemanticaOutput:
        """
        Etapa 3 da Validação: Auditoria Semântica e Pedagógica.
        Avalia o item do ENEM quanto à presença de incoerência, ambiguidade, déficit de dados ou erros.
        """
        prompt = build_auditoria_semantica_prompt(
            enunciado=enunciado,
            alternativas=alternativas
        )
        raw = self.llm_client.generate(
            prompt=prompt,
            max_tokens=300,
            temperature=0.0,
            top_p=0.9,
            format="json"
        )
        json_str = extract_json_from_text(raw)
        sanitized = sanitize_latex_json_text(json_str)
        parsed = json.loads(sanitized, strict=False)
        parsed = sanitize_parsed_dict_values(parsed)

        return QuestaoAuditoriaSemanticaOutput(**parsed)

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
        failed_habilidades = []

        for hab_code in target_codes:
            for item_idx in range(1, count_per_habilidade + 1):
                current_op += 1
                op_start = time.time()
                try:
                    questao = self.generate_single_questao_inedita(
                        db=db,
                        habilidade_codigo=hab_code,
                        num_few_shot=num_few_shot,
                        max_attempts=4
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
                    if hab_code not in failed_habilidades:
                        failed_habilidades.append(hab_code)
                    result_item = BatchPopulationItemResult(
                        habilidade_codigo=hab_code,
                        questao_id=None,
                        success=False,
                        attempts=4,
                        error=err_msg,
                        elapsed_seconds=elapsed
                    )
                    results.append(result_item)
                    if on_progress:
                        on_progress(hab_code, current_op, total_operations, False, err_msg)

        if failed_habilidades:
            logger.warning(f"Resumo do Lote - Habilidades que falharam após todas tentativas: {failed_habilidades}")

        total_elapsed = round(time.time() - start_time, 2)
        return BatchPopulationSummary(
            total_habilidades_processadas=len(target_codes),
            total_sucesso=total_success,
            total_falhas=total_failures,
            tempo_total_segundos=total_elapsed,
            habilidades_com_erro=failed_habilidades,
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
