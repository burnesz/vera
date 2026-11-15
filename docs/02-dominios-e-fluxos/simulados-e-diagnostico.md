---
title: "Fluxo de Simulados Estratificados e Diagnóstico por Habilidade"
domain: "simulados-diagnostico"
rules: ["RN-SIM01", "RN-SIM02", "RN-SIM03"]
related_code:
  - "app/services/simulado_service.py"
  - "app/api/v1/simulado.py"
  - "app/api/v1/dashboard.py"
  - "app/schemas/simulado.py"
  - "app/schemas/dashboard.py"
  - "app/db/models/simulado.py"
  - "app/db/models/submission.py"
  - "app/db/models/history.py"
  - "frontend/src/pages/SimuladoPage.tsx"
  - "frontend/src/pages/StudentDashboard.tsx"
  - "frontend/src/services/simuladoService.ts"
  - "frontend/src/services/dashboardService.ts"
related_notes:
  - "../01-arquitetura-e-dados/modelo-relacional.md"
  - "./geracao-questoes-pot.md"
  - "./frontend-e-ux.md"
  - "./feedback-pedagogico-item.md"
---

# Fluxo de Simulados Estratificados e Diagnóstico por Habilidade

O módulo de simulados (`app/services/simulado_service.py`) reproduz a estrutura oficial do caderno de Matemática e suas Tecnologias do ENEM (45 itens), combinando questões históricas do INEP e questões inéditas validadas pelo pipeline PoT.

---

## 1. Regras de Negócio de Simulados (`RN-SIM01` a `RN-SIM03`)

### `RN-SIM01` — Montagem Estratificada do Caderno de 45 Questões (`gerar_simulado_enem`)
Cada simulado contém exatamente **45 questões** selecionadas por amostragem estratificada em 3 estágios:

1. **Proporção Híbrida Configurável (`proporcao_ineditas = 0.15` por padrão)**:
   - **Cota de Inéditas (15% = 7 itens)**: selecionadas dentre as questões com `is_validated = True` em `questoes_ineditas`, garantindo no máximo 1 questão inédita por habilidade sorteada. Caso o banco possua menos inéditas disponíveis, as vagas remanescentes são automaticamente transferidas para a cota histórica.
   - **Cota de Históricas (85% = 38 itens)**: selecionadas a partir das 402 questões reais em `questoes_enem`.
2. **Estágio 1 — Cobertura Horizontal da Matriz (28 habilidades textuais)**:
   - O algoritmo garante primeiro 1 questão para cada uma das habilidades disponíveis no acervo textual que ainda não tenha recebido questão inédita na etapa anterior.
3. **Estágio 2 — Complemento pelas Habilidades de Maior Peso Histórico (17 itens complementares)**:
   - As vagas restantes para completar 45 itens são preenchidas priorizando:
     - `HABILIDADES_TOP13` (habilidades com $\ge 15$ questões históricas no acervo: `H01, H02, H03, H04, H11, H12, H16, H17, H18, H19, H21, H28, H29`).
     - Sorteio complementar dentre `HABILIDADES_EMPATADAS_14` (`H05, H10, H14, H23, H27, H30`), evitando repetição de `questao.id` dentro do mesmo caderno.
4. **Embaralhamento e Persistência (*Exclusive Arc*)**:
   - Os 45 itens (históricos + inéditos) são embaralhados aleatoriamente e gravados em `simulado_itens` com `ordem` de `1` a `45` e `origem_questao` (`'enem'` ou `'inedita'`).

### `RN-SIM02` — Omissão Estrita de Gabarito Durante a Prova
- O endpoint de consulta do caderno (`GET /api/v1/simulados/{simulado_id}`) e o schema de exibição de prova ativa **nunca** retornam os campos `gabarito` ou `justificativa`.
- Isso impede vazamento de respostas no DevTools/rede do navegador enquanto o estudante realiza o simulado.

### `RN-SIM03` — Submissão, Correção Automática e Atualização de Diagnóstico
- Ao submeter as respostas (`POST /api/v1/simulados/{simulado_id}/submeter`):
  1. O backend compara cada alternativa marcada com o gabarito oficial da questão correspondente (`questoes_enem` ou `questoes_ineditas`).
  2. Persiste a tentativa (`simulado_tentativas`) com `total_acertos`, `score_percentual` e os registros individuais em `respostas_itens`.
  3. Atualiza, na mesma transação, a tabela agregadora `desempenho_habilidades` (`submeter_tentativa_simulado`): os totais da tentativa por habilidade são **somados** aos acumulados do estudante (linha criada sob demanda), `taxa_acerto = total_acertos / total_questoes` (0.0–1.0, 3 casas) e `nivel_dominio` é reclassificado:
     - `taxa_acerto < 0.50` $\rightarrow$ `critico`
     - `0.50 ≤ taxa_acerto < 0.75` $\rightarrow$ `em_desenvolvimento`
     - `taxa_acerto ≥ 0.75` $\rightarrow$ `consolidado`
     - Itens em branco (`"X"`) contam como questão respondida e errada.
  4. Libera o relatório completo de conferência (`ItemCorrecaoResponse`): alternativa marcada, gabarito oficial, status de acerto/erro, código da habilidade, `enunciado`, `alternativas`, `justificativa` (inéditas: resolução cega; ENEM: `metadados.justificativa`, se houver) e `resposta_item_id`, usado para solicitar o **feedback pontual da Tutora VERA** sobre questões erradas (ver [feedback-pedagogico-item.md](./feedback-pedagogico-item.md)).

---

## 2. Endpoints de Simulados (`app/api/v1/simulado.py` — prefixo `/api/v1/simulados`)

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/simulados/` | Lista simulados do estudante. |
| `POST` | `/simulados/gerar` | Gera caderno estratificado de 45 itens (`RN-SIM01`). |
| `GET` | `/simulados/{simulado_id}` | Caderno para prova, sem gabarito/justificativa (`RN-SIM02`). |
| `POST` | `/simulados/{simulado_id}/submeter` | Corrige, persiste tentativa e atualiza diagnóstico (`RN-SIM03`). |
| `GET` | `/simulados/tentativas/me` | Histórico de tentativas concluídas (`SimuladoTentativaHistoricoResponse`, mais recente primeiro). |
| `GET` | `/simulados/tentativas/{tentativa_id}` | Relatório de correção de uma tentativa. |
| `GET` | `/simulados/{simulado_id}/resultado` | Relatório de correção da tentativa do simulado. |
| `DELETE` | `/simulados/{simulado_id}` | Exclui um simulado. |

---

## 3. Dashboard de Diagnóstico (`GET /api/v1/dashboard/desempenho`)

Implementado em `app/api/v1/dashboard.py` (schemas em `app/schemas/dashboard.py`), consumido por `StudentDashboard.tsx` via `dashboardService.ts`. Retorna `DashboardDesempenhoResponse`:

- **Métricas globais**: `total_simulados`, `total_questoes_respondidas`, `total_acertos` e `taxa_acerto_global` (em **percentual** 0–100, calculada sobre as tentativas concluídas).
- **30 habilidades** (`HabilidadeProgressoItem`): dados de `desempenho_habilidades`; habilidades sem histórico aparecem com zeros e `nivel_dominio = em_desenvolvimento`. Contadores `total_habilidades_consolidadas / em_desenvolvimento / criticas`.
- **7 competências** (`CompetenciaProgressoItem`): agregação dos totais das habilidades de cada competência (títulos em `COMPETENCIAS_INFO`), com a mesma régua 0.50/0.75 de `RN-SIM03` (taxa em fração 0.0–1.0), além de `habilidades_total` e `habilidades_consolidadas`.
- **`ultimas_tentativas`**: as 5 tentativas concluídas mais recentes.

---

## Notas Relacionadas

- [Modelo de Dados e Persistência Relacional](../01-arquitetura-e-dados/modelo-relacional.md)
- [Fluxo da Tutora Virtual VERA (Chat RAG)](./tutoria-rag-chat.md)
- [Frontend e Experiência do Usuário](./frontend-e-ux.md)
- [Feedback Pedagógico Pontual por Item](./feedback-pedagogico-item.md)
