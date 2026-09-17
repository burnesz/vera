#!/usr/bin/env python3
"""
Script CLI para Povoamento da Tabela questoes_ineditas no PostgreSQL.
Executa o pipeline RAG/few-shot determinístico utilizando o LLM local (Ollama Qwen 2.5),
conforme Seção 8 do pré-projeto VERA / AGENTS.md.

Uso:
    # Gerar 1 questão para cada uma das 30 habilidades oficiais (H01 a H30):
    python scripts/populate_questoes_ineditas.py --habilidades all

    # Gerar para habilidades específicas:
    python scripts/populate_questoes_ineditas.py --habilidades H01,H02,H03

    # Modo simulação/mock para testes instantâneos:
    python scripts/populate_questoes_ineditas.py --habilidades H01 --mock
"""

import sys
import os
import time
import argparse
import logging

# Adiciona o diretório raiz ao PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.session import SessionLocal
from app.db.models.questao_inedita import QuestaoInedita
from app.services.llm_client import LLMClient
from app.services.question_service import QuestionService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("vera.populate")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Povoamento da tabela questoes_ineditas usando o LLM local via Ollama."
    )
    parser.add_argument(
        "--habilidades",
        type=str,
        default="all",
        help="Códigos das habilidades separados por vírgula (ex: 'H01,H02,H03') ou 'all' para todas as 30."
    )
    parser.add_argument(
        "--count",
        type=int,
        default=1,
        help="Quantidade de questões inéditas a gerar por habilidade (padrão: 1)."
    )
    parser.add_argument(
        "--few-shot-k",
        type=int,
        default=2,
        help="Quantidade de exemplos históricos reais do ENEM a injetar no prompt (padrão: 2)."
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Executa em modo mock (respostas simuladas pré-formatadas) para testes rápidos."
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Pula habilidades que já possuam a quantidade solicitada de questões no banco."
    )
    return parser.parse_args()


def main():
    args = parse_args()
    print("=" * 80)
    print(" VERA — PIPELINE DE GERAÇÃO E POVOAMENTO DE QUESTÕES INÉDITAS (ENEM)")
    print("=" * 80)

    # 1. Configuração do cliente LLM
    llm_client = LLMClient(mock_mode=args.mock)
    if not args.mock:
        print(f"[*] Verificando disponibilidade do LLM no Ollama ({llm_client.endpoint_url})...")
        health = llm_client.health_check()
        if not health.get("healthy"):
            print(f"[!] ERRO: Servidor Ollama inacessível em {llm_client.endpoint_url}. Inicie o serviço antes de continuar.")
            sys.exit(1)
        if not health.get("model_available"):
            print(f"[!] AVISO: O modelo configurado '{llm_client.model_name}' não foi localizado no catálogo do Ollama.")
            print(f"    Modelos disponíveis: {health.get('available_models')}")
        else:
            print(f"[OK] Ollama ativo. Modelo verificado: '{llm_client.model_name}'")
    else:
        print("[!] Modo MOCK ativado — inferência real do LLM desabilitada.")

    # 2. Resolução das habilidades-alvo
    if args.habilidades.strip().lower() == "all":
        habilidades_list = [f"H{i:02d}" for i in range(1, 31)]
    else:
        habilidades_list = [h.strip().upper() for h in args.habilidades.split(",") if h.strip()]

    print(f"[*] Total de habilidades a processar: {len(habilidades_list)}")
    print(f"[*] Questões por habilidade: {args.count}")
    print(f"[*] Exemplos few-shot por item: {args.few_shot_k}")
    print(f"[*] Total estimado de questões inéditas a gerar: {len(habilidades_list) * args.count}")
    print("-" * 80)

    db = SessionLocal()
    question_service = QuestionService(llm_client=llm_client)

    inicio_geral = time.time()
    sucessos = 0
    falhas = 0

    try:
        for idx, hab_code in enumerate(habilidades_list, 1):
            print(f"\n>>> [{idx}/{len(habilidades_list)}] Processando Habilidade: {hab_code}")
            
            existing_count = db.query(QuestaoInedita).filter(QuestaoInedita.habilidade_codigo == hab_code).count()
            if args.skip_existing and existing_count >= args.count:
                print(f"    [SKIP] Habilidade {hab_code} já possui {existing_count} questão(ões) no banco. Pulando.")
                sucessos += args.count
                continue

            needed = args.count - (existing_count if args.skip_existing else 0)
            for q_idx in range(1, needed + 1):
                t0 = time.time()
                try:
                    questao = question_service.generate_single_questao_inedita(
                        db=db,
                        habilidade_codigo=hab_code,
                        num_few_shot=args.few_shot_k,
                        max_attempts=3
                    )
                    tempo_gasto = time.time() - t0
                    sucessos += 1
                    enunciado_resumo = (questao.enunciado[:90] + "...") if len(questao.enunciado) > 90 else questao.enunciado
                    print(f"    [SUCESSO] Questão {q_idx}/{needed} gerada e validada em {tempo_gasto:.1f}s!")
                    print(f"    - ID: {questao.id}")
                    print(f"    - Gabarito: {questao.gabarito}")
                    print(f"    - Enunciado: {enunciado_resumo}")
                except Exception as e:
                    tempo_gasto = time.time() - t0
                    falhas += 1
                    print(f"    [FALHA] Não foi possível gerar para {hab_code} após {tempo_gasto:.1f}s: {e}")

        # Contagem total consolidada no banco de dados
        total_no_banco = db.query(QuestaoInedita).count()

    finally:
        db.close()

    tempo_total = time.time() - inicio_geral
    print("\n" + "=" * 80)
    print(" RELATÓRIO FINAL DE POVOAMENTO")
    print("=" * 80)
    print(f"Tempo Total de Execução: {tempo_total:.1f} segundos ({tempo_total / 60:.1f} minutos)")
    print(f"Habilidades Processadas: {len(habilidades_list)}")
    print(f"Questões Geradas com Sucesso: {sucessos}")
    print(f"Falhas: {falhas}")
    print(f"Total Acumulado de Questões Inéditas no PostgreSQL: {total_no_banco}")
    print("=" * 80)


if __name__ == "__main__":
    main()
