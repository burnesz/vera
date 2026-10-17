---
title: "Pipeline PoT de Geração e Validação de Questões Inéditas"
domain: "geracao-questoes"
rules: ["RN-Q01", "RN-Q02", "RN-Q03", "RN-Q04"]
related_code:
  - "app/services/question_service.py"
  - "app/services/code_executor.py"
  - "app/services/question_validator.py"
  - "app/core/prompts.py"
  - "app/schemas/question.py"
  - "app/api/v1/questoes.py"
  - "scripts/populate_questoes_ineditas.py"
  - "data/habilidades_queries.json"
related_notes:
  - "../00-fundamentos/decisoes-dsr.md"
  - "../01-arquitetura-e-dados/ingestao-e-vetorizacao.md"
  - "../01-arquitetura-e-dados/modelo-relacional.md"
---

# Pipeline PoT de Geração e Validação de Questões Inéditas

Para erradicar erros aritméticos, colisões de alternativas e viés de confirmação (*sycophancy*) em modelos locais de 7B parâmetros, a criação de questões inéditas de Matemática adota a arquitetura **Program-Aided Generation (PoT)** aliada a uma **Validação Modular em 3 Etapas**.

---

## 1. Fluxo Completo de Geração e Validação

```mermaid
flowchart TD
    A["Habilidade Alvo (H01-H30)"] --> B["RAG Few-Shot: Top-10 no Pinecone (questoes_enem)\nSorteio de 2 Exemplos + Sorteio de Tema/Abertura\n(Fallback Determinístico no PostgreSQL)"]
    B --> C["Fase 1 (PoT): LLM gera JSON com\nenunciado + tabela_dados (opcional) + solver Python"]
    C --> D["CodeExecutor: AST Check + Subprocesso Isolado (Timeout 5s)"]
    D --> E{"Groundedness Numérico OK?\nExecução sem erro?"}
    E -- "Falha Estrutural" --> F["Linha 2: Stateless Retry\n(Contexto limpo + novo sorteio)"]
    F --> B
    E -- "Sucesso (mesmo com distratores duplicados)" --> G["Linha 1: Auto-Healing Algorítmico de Distratores\n+ Formatação de Tabela Markdown\n+ Embaralhamento A-E por Código (RN-Q02)"]
    G --> H["Validação Etapa 1: Resolução Cega Pura\n(LLM recebe APENAS o enunciado, max_tokens=1536)"]
    H --> I["Validação Etapa 2: Confronto de Equivalência\n(Juiz com contexto do enunciado + recuperação determinística)"]
    I -- "Divergentes (equivalentes = False)" --> J["Early Exit / Curto-Circuito"]
    J --> F
    I -- "Equivalentes (True)" --> K["Validação Etapa 3: Auditoria Semântica\n(LLM avalia 5 flags booleanas de defeito)"]
    K --> L{"Backend: Alguma flag True?\n(not aprovada)"}
    L -- "Sim (Reprovada)" --> F
    L -- "Não (Aprovada)" --> M["Persistência em questoes_ineditas\n(solver -> thought_scratchpad,\nresolucao_cega -> justificativa)"]
```

---

## 2. Regras de Negócio da Geração PoT (`RN-Q01` a `RN-Q04`)

### `RN-Q01` — Validação Estrita Multicamadas (Código + 3 Etapas LLM)
Nenhuma questão inédita pode ser salva ou exibida ao estudante sem cumprir **todos** os 7 critérios abaixo:
1. **Execução limpa da função `def resolver()`**: executada em processo filho isolado (`subprocess.run`) com timeout de **5 segundos** (`execute_solver_code` em `app/services/code_executor.py`), retornando dicionário com `"correta"` e `"distratores"` (4 itens).
2. **Inspeção Estática de Segurança via AST (`check_code_safety`)**:
   - Bloqueia imports de módulos do sistema/rede (`BLOCKED_MODULES`: `os`, `sys`, `subprocess`, `socket`, `shutil`, `urllib`, `requests`, `http`, `pathlib`, `ctypes`, `pickle`, `sqlite3`, etc.).
   - Bloqueia chamadas de funções perigosas (`BLOCKED_CALLS`: `eval`, `exec`, `compile`, `__import__`, `open`, `getattr`, `setattr`, `input`, `exit`, `breakpoint`).
3. **Nexo Numérico Flexível e Inteligente (*Groundedness* — `validate_solver_consistency` / `_extract_correta_code_numbers`)**:
   - Realiza *backward slicing* na AST de `resolver()` a partir da expressão de `"correta"`, extraindo apenas os literais numéricos (`ast.Constant`) que participam direta ou indiretamente do cálculo do gabarito (isentando constantes auxiliares exclusivas das variáveis de `"distratores"`).
   - Verifica se cada número consta no `enunciado` ou na `tabela_dados`, aceitando também:
     - **Numerais por extenso e termos temporais** em português (`PORTUGUESE_WORD_NUMBERS`: `"oito"` $\rightarrow 8$, `"mensal"`/`"mês"` $\rightarrow 30$, `"semana"` $\rightarrow 7$, `"ano"` $\rightarrow 12, 365$, `"mil"` $\rightarrow 1000$, etc.).
     - **Conversões diretas de escala métrica e geometria** dos números presentes no enunciado ($\times 10, \times 100, \times 1000, \div 10, \div 100, \div 1000$, metade/raio $\div 2$ e dobro $\times 2$).
      - **Fatores e complementos percentuais** (para $p\%$, aceita $p$, $p/100$, $100-p$, $1 - p/100$ e $1 + p/100$).
      - Constantes matemáticas, geométricas e temporais padrão (`ALLOWED_NUMERIC_CONSTANTS`).
    - Se a questão incluir `tabela_dados`, valida-se um teto de **10 linhas** (para permitir cálculo manual) e que **todas as colunas numéricas de dados** participem efetivamente do cálculo de `"correta"` (bloqueando tabelas decorativas ou colunas mortas).
4. **Unicidade Estrita das 5 Alternativas**: a resposta correta e os 4 distratores devem resultar em 5 strings formatadas mutuamente exclusivas.
5. **Validação Etapa 1 — Resolução Cega Pura (`QuestaoBlindSolvingOutput`)**:
   - O LLM resolve o problema recebendo **exclusivamente o enunciado** (sem alternativas e sem gabarito, com orçamento `max_tokens=1536`), produzindo `resolucao_passo_a_passo` e o valor final único em `resultado_obtido`.
6. **Validação Etapa 2 — Confronto Direto de Equivalência com *Fast-Path* 0ms e *Early Exit* (`QuestaoEquivalenciaOutput`)**:
   - Se `resultado_solver` e `resultado_obtido` forem escalares numéricos, o backend decide em **0ms** (aprovando se iguais ou equivalentes percentuais, e reprovando imediatamente com *Early Exit* se divergentes, sem chamar o LLM e eliminando qualquer risco de *sycophancy*). Caso envolva strings ou estruturas complexas, o juiz LLM é chamado via Structured Output (JSON Schema) com default estrito `False` caso a chave seja omitida.
7. **Validação Etapa 3 — Auditoria Semântica com Visão da Resolução (`QuestaoAuditoriaSemanticaOutput`)**:
   - Recebe o `enunciado`, a `habilidade_descricao`, a `resolucao_passo_a_passo` da Etapa 1 e as `alternativas`, exigindo primeiro um campo textual de raciocínio (`analise_critica`) antes das flags de defeito semântico (`possui_incoerencia`, `possui_ambiguidade`, `deficit_informacoes`).
   - Defeitos sintáticos como termos de bastidores vazados (`erros_ou_vazamentos`) e tabelas duplicadas (`duplicacao_tabelas`) são interceptados deterministicamente em Python (`check_code_leakage` e `check_table_duplication`).
   - A aprovação (`aprovada = not any(...)`) e o `motivo_rejeicao` continuam calculados em Python no backend.

### Diretrizes de Geração da Fase 1 (`POT_QUESTION_GENERATOR_SYSTEM_PROMPT` — `DSR-07`)
- **Complexidade padrão ENEM**: no mínimo 2 etapas de raciocínio encadeadas, evitando questões de operação única e priorizando valores compatíveis (resultados inteiros ou decimais exatos de até 2 casas) e sem empates entre opções comparadas.
- **Distratores baseados em erros comuns**: o solver modela erros típicos de raciocínio (parar em etapa intermediária, esquecer fator ou considerar apenas parte dos dados), com normalização de distratores negativos acidentais quando a resposta é positiva.
- **Few-shot multi-etapas sem vício de tabela**: o exemplo de formato (`POT_FEW_SHOT_EXAMPLE`) e o template final usam `"tabela_dados": null` por padrão para evitar que o modelo 7B force tabelas artificiais em habilidades de Geometria, Escala ou Álgebra. O orçamento da Fase 1 é de `max_tokens=1536`.
- **Ancoragem RAG filtrada por habilidade e higienizada**: `retrieve_rag_few_shot_examples` filtra no Pinecone estritamente por `filter_dict={"habilidade_codigo": clean_hab}`, descarta enunciados históricos com OCR quebrado e injeta `Resposta Correta Oficial: <valor>`.

### `RN-Q02` — Atribuição Determinística de Alternativas e Gabarito
- O LLM **nunca** escolhe a letra do gabarito na geração PoT.
- A função `assemble_alternatives_and_gabarito` (`app/services/code_executor.py`) formata os números no padrão brasileiro (`format_number`: inteiros limpos ou decimais com vírgula até 2 casas), embaralha as 5 opções com `random.shuffle` e atribui deterministicamente as letras `"A"` a `"E"`, identificando a letra exata correspondente a `correta`.

### `RN-Q03` — Defesa em Cascata: Auto-Healing Algorítmico e Stateless Retry
- **Linha 1 (`auto_heal_distractors`)**: quando `resolver()` acerta o cálculo principal mas produz distratores repetidos ou iguais à correta, o backend preserva os distratores únicos e sintetiza os faltantes deterministicamente usando o passo característico $\Delta$ da distribuição e variações cognitivas típicas do ENEM ($\pm k\Delta$, dobro/metade, escala decimal $\times 10$ / $\div 10$).
- **Linha 2 (*Stateless Retry*)**: em caso de falha estrutural na Fase 1 ou reprovação nas Etapas 1b/2/3 da validação, descarta-se toda a tentativa e inicia-se uma nova iteração com contexto limpo, novo sorteio de tema/abertura (`sortear_contexto_criativo`), nova amostragem dos Top-10 candidatos no Pinecone e progressão gradual de temperatura a partir de `0.0` (`0.0` $\rightarrow$ `0.1` $\rightarrow$ `0.2` $\rightarrow$ `0.3`, limitada a `0.6`).

### `RN-Q04` — Rastreabilidade e Auditoria na Persistência
- Na tabela `questoes_ineditas`:
  - A coluna `thought_scratchpad` armazena o código Python de `def resolver()`.
  - A coluna `justificativa` armazena a `resolucao_passo_a_passo` gerada de forma independente na Resolução Cega Pura.

---

## 3. Contratos Técnicos de Sanitização e Formatação (`question_validator.py`)

1. **Sanitização de Colisões LaTeX em JSON (`sanitize_latex_json_text` e `sanitize_parsed_dict_values`)**:
   - Em JSON padrão, sequências como `\frac`, `\times`, `\right`, `\neq`, `\bar` e `\beta` colidem com caracteres de escape (`\f` form-feed `chr(12)`/`\x0c`, `\t` tab, `\r` carriage return, `\n` newline, `\b` backspace), corrompendo `\frac{a}{b}` para `\x0crac{a}{b}`.
   - O validador intercepta a string bruta antes de `json.loads()`, restaura `\x0crac` para `\\frac`, escapa barras simples de comandos LaTeX e limpa recursivamente o dicionário resultante.
2. **Formatação Estruturada de Tabelas (`tabela_dados` $\rightarrow$ Markdown)**:
   - Quando a questão envolve dados tabulares, o LLM preenche o campo opcional `tabela_dados: List[Dict[str, Any]]`.
   - A função `format_enunciado_with_table` converte `tabela_dados` em uma tabela Markdown limpa e a incorpora ao `enunciado` (evitando duplicação caso o modelo já tenha desenhado pipes `|` no texto).

---

## Notas Relacionadas

- [Decisões de Engenharia DSR (Decisões 3, 4, 5 e 6)](../00-fundamentos/decisoes-dsr.md)
- [Modelo de Dados Relacional (`questoes_ineditas`)](../01-arquitetura-e-dados/modelo-relacional.md)
- [Guia Operacional e Scripts (`populate_questoes_ineditas.py`)](../04-operacoes-e-roadmap/guia-operacional-e-scripts.md)
