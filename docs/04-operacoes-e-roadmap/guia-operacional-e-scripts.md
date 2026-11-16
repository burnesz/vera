---
title: "Guia Operacional, Scripts Utilitários e Convenções de Desenvolvimento"
domain: "operacoes"
rules: ["RN-INF04"]
related_code:
  - "scripts/seed_habilidades.py"
  - "scripts/seed_questoes.py"
  - "scripts/seed_questoes_pinecone.py"
  - "scripts/populate_questoes_ineditas.py"
  - "scripts/clean_tiny_chunks.py"
  - "scripts/search_pinecone.py"
  - "scripts/ollama_forwarder.py"
  - "pytest.ini"
  - "docker-compose.yml"
related_notes:
  - "../01-arquitetura-e-dados/visao-arquitetural.md"
  - "../01-arquitetura-e-dados/ingestao-e-vetorizacao.md"
  - "./roadmap-e-status.md"
---

# Guia Operacional, Scripts Utilitários e Convenções de Desenvolvimento

---

## 1. Convenções de Ambiente e Execução (WSL / Linux)

1. **Ambiente Virtual Python Obrigatório**:
   - Todos os comandos Python, scripts e execuções do Pytest **devem** utilizar o ambiente virtual `./.venv` na raiz do repositório:
     ```bash
     ./.venv/bin/python -m pytest
     ./.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
     ```
2. **Comandos Não-Interativos**:
   - No ambiente WSL, sempre executar comandos de terminal de forma não-interativa para garantir encerramento limpo (`EOF`).
3. **Execução da Suíte de Testes (`tests/`)**:
   - A suíte conta com 18 arquivos de teste (166 testes) cobrindo autenticação, modelos relacionais, chunking, extração de fórmulas, `LLMClient`, `CodeExecutor`, `QuestionValidator`, RAG, *query rewriting*, diversidade de prompts, geração PoT, API de questões, seed de questões, simulados, feedback por item e chat:
     ```bash
     ./.venv/bin/pytest -v
     ```

---

## 2. Catálogo de Scripts Operacionais (`scripts/`)

| Script | Finalidade | Comando de Exemplo |
|---|---|---|
| `scripts/seed_habilidades.py` | Popula as 30 habilidades oficiais (`H01`–`H30`) e competências (`C1`–`C7`) na tabela `habilidades_enem`. | `./.venv/bin/python scripts/seed_habilidades.py` |
| `scripts/seed_questoes.py` | Importa o dataset enriquecido (`data/itens_prova_2009_2024_enriquecido.csv`) com as 402 questões históricas para `questoes_enem`. | `./.venv/bin/python scripts/seed_questoes.py` |
| `scripts/seed_questoes_pinecone.py` | Gera embeddings E5-large (1024 dims) das 402 questões históricas e faz upsert no namespace `questoes_enem` do Pinecone. | `./.venv/bin/python scripts/seed_questoes_pinecone.py` |
| `scripts/populate_questoes_ineditas.py` | Executa o pipeline PoT em lote (multi-round com retry) para povoar a tabela `questoes_ineditas`. Flags: `--habilidades` (`all` ou `H01,H02`), `--count`, `--few-shot-k`, `--mock`, `--skip-existing`, `--tema`, `--abertura`. | `./.venv/bin/python scripts/populate_questoes_ineditas.py --habilidades all --count 1` |
| `scripts/seed_alunos_ficticios.py` | Gera **dados fictícios** de uso sem chamar o LLM: 5 estudantes (`<slug>@ficticio.vera`, senha `aluno123`) com perfis distintos, simulados de 45 itens montados por `gerar_simulado_enem` e respondidos via TRI 3PL com os parâmetros `a`/`b`/`c` de cada item, submetidos por `submeter_tentativa_simulado` (atualiza `desempenho_habilidades`), datas espalhadas nas últimas semanas e simulados pendentes. Não gera feedbacks, chat nem inéditas. Parâmetros TRI sem separador decimal no CSV (44 itens, sobretudo 2012) são normalizados (÷1000) na leitura. Requer `seed_questoes.py` antes. | `./.venv/bin/python scripts/seed_alunos_ficticios.py [--alunos N] [--seed 42] [--recriar \| --limpar]` |
| `scripts/run_retrieval_eval.py` | **Experimento 1 do TCC**: roda as 126 queries de `evaluation/data/retrieval_gold.json` nos sistemas `e5_denso`, `e5_rerank` e `bm25`, nos cenários `fechado` (63 PDFs `ENEM_MAT_*`) e `completo`. Gera Hit@K, MRR@10, nDCG@10, Context Precision@3 e latência, com IC 95% por bootstrap e testes de permutação pareados (Holm). Saída em `evaluation/results/<pasta>/`; prefixo `piloto-` enquanto o gabarito não estiver congelado. Flags: `--sistemas`, `--cenarios`, `--limit`, `--recalcular <pasta>`, `--atualizar-corpus`. | `./.venv/bin/python scripts/run_retrieval_eval.py [--limit 5]` |
| `scripts/run_rewriting_eval.py` | **Experimento 2 do TCC**: compara `sem_reescrita`, `com_reescrita` (`ChatService.rewrite_query`) e `oraculo` nos 30 diálogos de `evaluation/data/rewriting_dialogs.json`. Exige o Ollama ativo. Flags: `--cenario`, `--recalcular <pasta>`. | `./.venv/bin/python scripts/run_rewriting_eval.py` |
| `scripts/relevance_agreement.py` | Validação do gabarito por segundo avaliador: `exportar` monta o pool cego (gabarito + top-5 de cada rodada) em `evaluation/data/anotacao/pool.csv`; `calcular` dá o kappa de Cohen (simples e ponderado) e as divergências. | `./.venv/bin/python scripts/relevance_agreement.py exportar --rodada evaluation/results/<pasta>` |
| `scripts/freeze_gold.py` | Congela o gabarito e os diálogos (`congelado: true` + data) e imprime o SHA-256 (`RN-AVAL02`). | `./.venv/bin/python scripts/freeze_gold.py` |
| `scripts/clean_tiny_chunks.py` | Audita e remove chunks residuais curtos (`< 15` palavras) do namespace `materiais_didaticos` no Pinecone (`RN-CHUNK02`). | `./.venv/bin/python scripts/clean_tiny_chunks.py` |
| `scripts/search_pinecone.py` | Utilitário CLI para inspecionar e testar consultas semânticas nos namespaces do Pinecone. | `./.venv/bin/python scripts/search_pinecone.py` |
| `scripts/ollama_forwarder.py` | Proxy/forwarder utilitário para roteamento de chamadas ao daemon do Ollama entre WSL e host Windows quando necessário. | `./.venv/bin/python scripts/ollama_forwarder.py` |

---

## 3. Como Manter a Memória do Projeto Atualizada

A pasta `docs/` funciona como um **Vault de Memória Viva** (estilo Obsidian) sincronizado com o [AGENTS.md](../../AGENTS.md):

1. **Nova Decisão Arquitetural ou Pedagógica**: adicione uma nova seção em [decisoes-dsr.md](../00-fundamentos/decisoes-dsr.md) explicando *Contexto*, *Problema no Ciclo DSR*, *Solução Implementada* e *Arquivos de Referência*, e atualize a tabela resumo no `AGENTS.md`.
2. **Nova Regra de Negócio (`RN-*`)**: documente a regra na nota temática correspondente em `docs/01-*`, `docs/02-*` ou `docs/03-*` e registre seu código no Índice Rápido do `AGENTS.md`.
3. **Limite de Tamanho do `AGENTS.md` Raiz**: mantenha o [AGENTS.md](../../AGENTS.md) sempre **abaixo de 10 KB** (o limite físico de truncamento do motor de regras é de `24.000` bytes). Detalhes extensos devem sempre residir nas notas modulares em `docs/`.

---

## Notas Relacionadas

- [Visão Arquitetural e Infraestrutura](../01-arquitetura-e-dados/visao-arquitetural.md)
- [Roadmap e Status de Implementação](./roadmap-e-status.md)
