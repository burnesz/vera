---
title: "Catálogo de Decisões de Engenharia DSR (Design Science Research)"
domain: "fundamentos"
rules: ["DSR-01", "DSR-02", "DSR-03", "DSR-04", "DSR-05", "DSR-06", "DSR-07"]
related_code:
  - "app/services/llm_client.py"
  - "app/services/chat_service.py"
  - "app/services/question_service.py"
  - "app/services/code_executor.py"
  - "app/services/question_validator.py"
  - "app/core/prompts.py"
related_notes:
  - "./visao-e-escopo.md"
  - "../02-dominios-e-fluxos/tutoria-rag-chat.md"
  - "../02-dominios-e-fluxos/geracao-questoes-pot.md"
---

# Catálogo de Decisões de Engenharia DSR

> Registro arquitetural (ADR/DSR) contendo as justificativas técnicas e científicas para a banca examinadora do TCC sobre a evolução dos artefatos da plataforma VERA.

---

## Decisão 1 (`DSR-01`): Orquestração Nativa e Tipada vs. Frameworks Pesados (LangChain)

- **Contexto Inicial**: A proposta preliminar do projeto previa o uso de LangChain para encadear os passos de IA (prompts, parsers e recuperação vetorial).
- **Problema Identificado no Ciclo DSR**: Durante o desenvolvimento, constatou-se que abstrações genéricas do LangChain introduziam opacidade no tratamento de erros, dependências frágeis entre versões e sobrecarga de latência nas chamadas locais ao Ollama.
- **Solução Implementada**: Orquestração desacoplada em serviços especializados em Python puro (`ChatService`, `QuestionService`, `LLMClient`), utilizando tipagem estrita com **Pydantic v2**, chamadas HTTP diretas (`httpx`) com *exponential backoff* e controle granular sobre schemas JSON, sanitização de LaTeX e extração de blocos CoT.
- **Arquivos de Referência**: `app/services/llm_client.py`, `app/services/chat_service.py`, `app/services/question_service.py`.

---

## Decisão 2 (`DSR-02`): Tutoria Interativa Conversacional vs. Feedback Estático Unidirecional

- **Contexto Inicial**: O pré-projeto descrevia apenas a emissão de um texto estático de feedback após a submissão do simulado.
- **Problema Identificado no Ciclo DSR**: Um feedback passivo e unidirecional é pouco engajador e não permite que o estudante tire dúvidas específicas surgidas durante a leitura da resolução.
- **Solução Implementada**: Além do suporte a feedback por item (`app/db/models/feedback.py`), o estudante recebe a correção imediata no simulado com identificação das habilidades erradas e é direcionado com um clique para a **Tutora Virtual VERA** (`ChatPage.tsx`). A tutora opera em sessão multiturno contínua persistida no PostgreSQL (`chat_sessions` / `chat_messages`), com *Query Rewriting*, busca vetorial em `materiais_didaticos` e transparência do raciocínio interno retrátil (`<pensamento>`).
- **Arquivos de Referência**: `app/services/chat_service.py`, `app/api/v1/chat.py`, `frontend/src/pages/ChatPage.tsx`.

---

## Decisão 3 (`DSR-03`): Arquitetura PoT (*Program-Aided Generation*) para Questões Inéditas

- **Contexto Inicial**: Geração direta de enunciado, 5 alternativas e gabarito pelo LLM em chamada única (*one-shot* ou *few-shot* puro).
- **Problema Identificado no Ciclo DSR**: LLMs locais de 7B parâmetros operando em geração textual direta cometem falhas aritméticas frequentes (*shortcut reasoning*, parada em passo intermediário, inversão de operações, distratores com contas incorretas ou letra do gabarito trocada).
- **Solução Implementada**: Adoção de *Program-Aided Generation* (PoT) com execução isolada em subprocesso (`app/services/code_executor.py`). Na Fase 1, o LLM cria exclusivamente a narrativa contextualizada (`enunciado` + `tabela_dados` opcional) e a função Python `def resolver()`. O interpretador Python executa o código em ambiente seguro (AST validada e timeout de 5s) e monta o gabarito e as alternativas A–E de forma determinística, elevando a precisão aritmética do cálculo para 100%.
- **Arquivos de Referência**: `app/services/code_executor.py`, `app/services/question_service.py`, `app/schemas/question.py`.

---

## Decisão 4 (`DSR-04`): Busca Semântica com Amostragem Diversificada (Top-10 $\rightarrow$ 2 itens) e Fallback Determinístico

- **Contexto Inicial**: Resgate fixo dos mesmos Top-K exemplos mais próximos da habilidade no banco vetorial.
- **Problema Identificado no Ciclo DSR**: Resgatar sempre os mesmos exemplos de topo fixos induzia o modelo 7B a repetir estruturas narrativas, nomes e premissas quase idênticas às questões de exemplo.
- **Solução Implementada**:
  1. Consulta ao namespace `questoes_enem` no Pinecone resgatando os **Top-10 itens candidatos** mais similares semanticamente (ancorados nas queries expandidas em `data/habilidades_queries.json`, com `filter={"habilidade_codigo": clean_hab}`).
  2. Amostragem aleatória (`random.sample`) de **2 exemplos** dentre os candidatos por chamada.
  3. Sorteio estocástico de **tema do cotidiano** (`TEMAS_COTIDIANO`) e **formato de abertura narrativa** (`FORMAS_ABERTURA`) via `sortear_contexto_criativo()` em `app/core/prompts.py`.
  4. **Fallback Relacional Determinístico**: caso o Pinecone esteja indisponível ou sem itens para a habilidade, o sistema consulta automaticamente o PostgreSQL (`WHERE habilidade_codigo = :habilidade ORDER BY random()`), garantindo 100% de disponibilidade offline.
- **Arquivos de Referência**: `app/services/question_service.py` (`retrieve_rag_few_shot_examples`, `retrieve_few_shot_examples`), `app/core/prompts.py`, `data/habilidades_queries.json`.

---

## Decisão 5 (`DSR-05`): Auto-Healing Limitado de Distratores e Stateless Retry Guiado (Superação de *Anchoring Bias*)

- **Contexto Inicial**: Uso de um loop de auto-correção contextual (*Stateful Correction*) que injetava o código/enunciado defeituoso anterior no prompt pedindo que o modelo corrigisse o erro.
- **Problema Identificado no Ciclo DSR**: Modelos locais de 7B parâmetros (como o Qwen 2.5) sofrem de forte viés de ancoragem (*context anchoring bias* — Huang et al., 2023). Ao receber seu próprio rascunho defeituoso no contexto, o modelo tendia a repetir as mesmas colisões de distratores ou os mesmos vícios lógicos. Por outro lado, curar todos os 4 distratores sinteticamente enfraquecia a exigência de distratores baseados em erros cognitivos reais.
- **Solução Implementada (Defesa em Duas Linhas)**:
  1. **Linha 1 — Normalização de 5$\rightarrow$4 Distratores e Auto-Healing Limitado a 1 Colisão (`_normalize_five_distractors` + `auto_heal_distractors`)**: Se o solver retornar 5 itens em `distratores` sendo 1 igual a `correta`, o item coincidente é descartado para reaproveitar os 4 distratores legítimos. Se, dentre os 4 distratores, houver **apenas 1 colisão** (`3` distratores únicos distintos de `correta`), o Python sintetiza 1 substituto plausível em `0ms`. Se houver **$\ge 2$ colisões**, a tentativa é reprovada imediatamente.
  2. **Linha 2 — Stateless Retry Guiado por Categoria Curta**: Quando ocorre falha estrutural ou reprovação na validação, descarta-se integralmente o rascunho/código anterior. A nova tentativa (até `max_attempts=5`, escalando temperatura de `0.2` a `0.6`) inicia limpa (*Stateless*), recebendo novo sorteio de tema/abertura/few-shot, `enunciados_recentes` da habilidade e **apenas uma diretriz curta de 1 linha da categoria do erro anterior** (`_classify_retry_hint`), orientando sem ancorar.
- **Arquivos de Referência**: `app/services/code_executor.py` (`_normalize_five_distractors`, `auto_heal_distractors`), `app/services/question_service.py` (`_classify_retry_hint`, `_generate_pot_item`).

---

## Decisão 6 (`DSR-06`): Validação Modular em 3 Etapas contra Viés de Confirmação (*Sycophancy*)

- **Contexto Inicial**: Auto-validação em chamada única onde o LLM recebia o enunciado, as 5 alternativas e o gabarito pretendido para julgar se a questão estava correta.
- **Problema Identificado no Ciclo DSR**: Ocorria viés de confirmação (*sycophancy*): mesmo quando o enunciado era insolúvel, ambíguo ou matematicamente defeituoso (ex.: pedir a moda de um conjunto amodal), a presença do gabarito da banca induzia o modelo a forçar cálculos para concordar com a resposta fornecida.
- **Solução Implementada (Pipeline de Validação em 3 Chamadas Independentes)**:
  1. **Etapa 1 — Resolução Cega Pura (`build_blind_solving_prompt`)**: O LLM recebe **exclusivamente o enunciado e a tabela** (zero alternativas, zero gabarito, zero código do solver) e deduz a solução do zero, retornando `resolucao_passo_a_passo`, `premissas_assumidas`, `dados_nao_utilizados`, `pergunta_respondivel` e `resultado_obtido` (em tipo primitivo Python).
  2. **Etapa 2 — Confronto Direto de Equivalência com *Early Exit* (`build_equivalencia_gabarito_prompt`)**: Um juiz matemático conciso compara apenas `resultado_solver` vs. `resultado_obtido`. Se divergirem (`equivalentes == False`), ocorre **curto-circuito imediato (*Early Exit*)** para o *Stateless Retry*, economizando a chamada da Etapa 3.
  3. **Etapa 3 — Auditoria Semântica e Pedagógica com Rejeição Determinística (`build_auditoria_semantica_prompt`)**: O LLM avalia `analise` + 4 macro-critérios semânticos essenciais (`incoerencia_ou_absurdo`, `comando_ambiguo_ou_incompativel`, `deficit_ou_contradicao`, `complexidade_insuficiente`), enquanto checagens estruturais (vazamento de termos proibidos como 'solver'/'python' e integridade de tabelas) são executadas deterministicamente em Python (`check_prohibited_terms`). A aprovação (`aprovada = not any(...)`) e o `motivo_rejeicao` são calculados deterministicamente em Python (`QuestaoAuditoriaSemanticaOutput`), eliminando qualquer leniência subjetiva do modelo.
- **Arquivos de Referência**: `app/services/question_service.py`, `app/core/prompts.py`, `app/schemas/question.py`.

---

## Decisão 7 (`DSR-07`): Complexidade Padrão ENEM e Premissas Explícitas (Combate a Itens Triviais e Convenções Implícitas)

- **Contexto Inicial**: O prompt da Fase 1 exigia apenas "situação-problema realista com comando final claro" e trazia como exemplo de formato uma soma simples de três valores de uma tabela. `ALLOWED_NUMERIC_CONSTANTS` incluía `365`.
- **Problema Identificado no Ciclo DSR**: A análise das questões inéditas aprovadas revelou dois defeitos sistemáticos:
  1. **Itens triviais**, resolvidos com uma única operação, abaixo do padrão ENEM (que exige interpretação e articulação de mais de um conceito). Causa principal: o modelo 7B ancora no nível do exemplo *few-shot* de formato mais do que nas instruções textuais.
  2. **Premissas implícitas e dados ociosos** (ex.: "frequência mensal" calculada como 30 dias sem declaração, ou tabelas com colunas não utilizadas no cálculo). Como gerador e resolvedor cego são o **mesmo modelo, com o mesmo viés**, ambos assumem a mesma convenção e a Etapa 2 (equivalência) aprova o item.
- **Solução Implementada**:
  1. **Prompt de Geração e Orçamento (`num_ctx=4096`, `max_tokens=1536`, `temperature=0.2`)**: campo obrigatório `"planejamento"` antes do enunciado; regras explícitas de complexidade (≥ 2 etapas encadeadas, proibição de operação única), de premissas explícitas e de distratores baseados em variáveis nomeadas por erro típico; sorteio de 1 dentre 3 *few-shots* multi-etapas (`POT_FEW_SHOT_EXAMPLES`, usando `len([...])` para contagens); resolução do valor real da alternativa correta (`Resposta Correta Oficial: <valor>`) nos 2 exemplos dinâmicos do RAG.
  2. **Auto-relato na Resolução Cega (Etapa 1b)**: o resolvedor reporta `pergunta_respondivel`, `premissas_assumidas` e `dados_nao_utilizados`. Pergunta não respondível, premissa implícita não vazia ou $> 1$ dado não utilizado reprovam o item deterministicamente com *Early Exit* antes da Etapa 2.
  3. **Auditoria Semântica Consolidada (4 Macro-Critérios)**: avalia `incoerencia_ou_absurdo`, `comando_ambiguo_ou_incompativel`, `deficit_ou_contradicao` e `complexidade_insuficiente`.
  4. **Nexo Numérico com Numerais por Extenso**: `365` removido de `ALLOWED_NUMERIC_CONSTANTS` e adicionado `_WORDS_TO_NUMBERS` + complementos percentuais em `validate_solver_consistency`.
- **Arquivos de Referência**: `app/core/prompts.py`, `app/schemas/question.py`, `app/services/question_service.py`, `app/services/code_executor.py`.

---

## Notas Relacionadas

- [Visão Geral, Escopo Pedagógico e Glossário](./visao-e-escopo.md)
- [Pipeline PoT de Geração e Validação de Questões Inéditas](../02-dominios-e-fluxos/geracao-questoes-pot.md)
- [Fluxo da Tutora Virtual VERA (Chat RAG)](../02-dominios-e-fluxos/tutoria-rag-chat.md)
