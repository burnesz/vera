---
title: "Visão Arquitetural, Infraestrutura Local (Ollama) e Rotas da API"
domain: "arquitetura"
rules: ["RN-INF01", "RN-INF02", "RN-INF03", "RN-INF04"]
related_code:
  - "app/main.py"
  - "app/core/config.py"
  - "app/core/security.py"
  - "app/api/router.py"
  - "app/api/deps.py"
  - "app/services/llm_client.py"
  - "app/api/v1/health.py"
related_notes:
  - "../00-fundamentos/visao-e-escopo.md"
  - "./modelo-relacional.md"
  - "./ingestao-e-vetorizacao.md"
---

# Visão Arquitetural, Infraestrutura Local e Rotas da API

---

## 1. Topologia dos Módulos do Sistema

```mermaid
flowchart TB
    subgraph Frontend ["Frontend Web (React 18 + TS + Vite)"]
        UI["Páginas: Home, Login, Register,\nStudentDashboard, SimuladoPage, ChatPage"]
        KATEX["MathText.tsx (Renderizador KaTeX)"]
    end

    subgraph Backend ["Backend FastAPI (/api/v1)"]
        API["Rotas: /health, /auth, /chat, /simulados,\n/admin/ineditas, /dashboard, /feedback"]
        SVC["Serviços: ChatService, FeedbackService, QuestionService,\nSimuladoService, CodeExecutor, QuestionValidator"]
        LLM["LLMClient (HTTP Resiliente + Retry + Mock)"]
    end

    subgraph Storage ["Armazenamento Híbrido & Inferência"]
        OLLAMA[("Ollama Local (:11434)\nqwen2.5:7b-instruct-q4_K_M\nqwen3:8b-q4_K_M (feedback e tutora)")]
        PG[("PostgreSQL 15\n(vera_db - 12 tabelas)")]
        PC[("Pinecone (vera-math-index)\n• materiais_didaticos\n• questoes_enem")]
        R2[("Cloudflare R2 (S3)\nAcervo de PDFs Didáticos")]
    end

    UI --> API
    API --> SVC
    SVC --> LLM
    LLM --> OLLAMA
    SVC --> PG
    SVC --> PC
    R2 -->|"Pipeline de Ingestão"| PC
```

### Camadas Principais

1. **Frontend Web (`frontend/`)**: SPA em React 18 + TypeScript + Vite com Design System proprietário em Vanilla CSS (*Ocean & Coral Palette*) e renderização de fórmulas via KaTeX (`MathText.tsx`).
2. **Backend e API (`app/`)**: FastAPI assíncrono, injeção de dependências tipadas (`app/api/deps.py`), validação Pydantic v2 (`app/schemas/`) e autenticação stateless via JWT (`HS256`, expiração padrão de 24h / 1440 min) + hash de senhas Bcrypt (`app/core/security.py`).
3. **Inferência Local (`app/services/llm_client.py`)**: Comunicação direta com o daemon local do Ollama executando `qwen2.5:7b-instruct-q4_K_M` e, no feedback e na tutora, `qwen3:8b-q4_K_M` sem raciocínio (**RN-INF07**, `DSR-08`).
4. **Armazenamento Híbrido**:
   - **PostgreSQL 15**: dados relacionais transacionais e auditoria pedagógica.
   - **Pinecone (`vera-math-index`)**: busca semântica em 1024 dimensões (`intfloat/multilingual-e5-large`, métrica cosseno) dividida nos namespaces `materiais_didaticos` e `questoes_enem`.
   - **Cloudflare R2**: Object Storage S3-compatível para armazenamento dos PDFs didáticos originais (`app/services/storage.py`).

---

## 2. Regras de Infraestrutura e Inferência Local (`RN-INF01` a `RN-INF04`)

| Código | Regra de Negócio | Implementação no Código |
|---|---|---|
| **RN-INF01** | **Variáveis de Ambiente Configuráveis**: o endpoint do LLM e o modelo devem ser lidos obrigatoriamente de `LLM_ENDPOINT_URL` (padrão: `http://localhost:11434`) e `LLM_MODEL` (padrão: `qwen2.5:7b-instruct-q4_K_M`). | `Settings` em `app/core/config.py` e `LLMClient.__init__` em `app/services/llm_client.py`. |
| **RN-INF02** | **Health-Check Proativo**: a API disponibiliza o endpoint `GET /api/v1/health` que inspeciona a conectividade com o Ollama (`/api/tags`), PostgreSQL e Pinecone. | `app/api/v1/health.py` e `LLMClient.health_check()`. |
| **RN-INF03** | **Resiliência com Retry e Backoff**: chamadas ao LLM utilizam política de retry exponencial (até 3 tentativas) e timeout estendido (`LLM_TIMEOUT_SECONDS = 300.0`, `LLM_NUM_CTX = 4096`) para absorver picos de carga na GPU/CPU local. | `LLMClient.generate()` e `LLMClient.agenerate()` em `app/services/llm_client.py`. |
| **RN-INF07** | **Modelo por Função**: o feedback por item e a tutora usam `LLM_MODEL_TUTORIA` (padrão: `qwen3:8b-q4_K_M`) com `LLM_THINK_TUTORIA` (padrão: `false`, raciocínio desligado), escolhidos pelo Experimento 1 de seleção de modelos (`DSR-08`). O teto de saída é `LLM_MAX_TOKENS_TUTORIA`; uma chamada com `max_tokens` explícito (reescrita da consulta: 60) tem precedência. Respostas cortadas pelo teto (`done_reason=length`) geram um aviso no log. Os demais usos seguem `LLM_MODEL`. | `cliente_tutoria()` em `app/services/llm_client.py`; padrões de `FeedbackService`, `ChatService` e `BaselineService`. |
| **RN-INF04** | **Modo Mock para Testes**: o `LLMClient` deve manter suporte a `mock_mode=True` (ou respostas simuladas injetáveis) para execução de suítes Pytest desacopladas do hardware de inferência. | `LLMClient(mock_mode=True)` em `app/services/llm_client.py`. |

---

## 3. Variáveis de Ambiente Consolidada (`app/core/config.py`)

| Grupo | Variável | Valor Padrão | Descrição |
|---|---|---|---|
| **API / Auth** | `API_V1_STR` | `"/api/v1"` | Prefixo base das rotas da API |
| | `JWT_SECRET_KEY` | `"vera-jwt-secret-..."` | Chave de assinatura de tokens JWT (`HS256`) |
| | `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | Tempo de expiração do token (24h) |
| **LLM (Ollama)** | `LLM_ENDPOINT_URL` | `"http://localhost:11434"` | URL do daemon local do Ollama (**RN-INF01**) |
| | `LLM_MODEL` | `"qwen2.5:7b-instruct-q4_K_M"` | Tag do modelo no Ollama (**RN-INF01**) |
| | `LLM_MODEL_TUTORIA` | `"qwen3:8b-q4_K_M"` | Modelo do feedback e da tutora (**RN-INF07**, `DSR-08`) |
| | `LLM_THINK_TUTORIA` | `false` | Liga/desliga o modo de raciocínio do modelo da tutoria (**RN-INF07**) |
| | `LLM_MAX_TOKENS_TUTORIA` | `3072` | Teto de tokens de saída do feedback e da tutora (**RN-INF07**). Com o teto geral de 1024, o `<pensamento>` + `<resposta>` era cortado no meio de fórmulas (2026-11-16) |
| | `LLM_TIMEOUT_SECONDS` | `300.0` | Timeout máximo por requisição HTTP ao Ollama |
| | `LLM_MAX_TOKENS` | `1024` | Limite padrão de tokens de saída (`num_predict`) |
| | `LLM_NUM_CTX` | `4096` | Janela de contexto no Ollama (`num_ctx`), calibrada para acomodar o prompt RAG sem sobrecarregar a VRAM. O `.env` usa `8192`, necessário para caber o prompt do feedback mais os 3072 tokens de saída |
| **Pinecone & E5** | `PINECONE_API_KEY` | `""` | Chave da API Pinecone |
| | `PINECONE_INDEX_NAME` | `"vera-math-index"` | Nome do índice vetorial |
| | `EMBEDDING_MODEL_NAME` | `"intfloat/multilingual-e5-large"` | Modelo local SentenceTransformers (1024 dims) |
| | `EMBEDDING_DEVICE` | `"cpu"` | Dispositivo para embeddings (`cpu` para reservar VRAM total da GPU para o Ollama) |
| | `NAMESPACE_MATERIAIS_DIDATICOS` | `"materiais_didaticos"` | Namespace de apostilas/livros para a Tutora RAG |
| | `NAMESPACE_QUESTOES_ENEM` | `"questoes_enem"` | Desativado desde 2026-11-16: servia à geração de questões que saiu da plataforma. O serviço `questoes-ineditas-enem` usa um ChromaDB próprio |
| **Ingestão / RAG** | `CHUNK_SIZE` / `CHUNK_OVERLAP` | `1200` / `150` | Limites de caracteres do `MaterialChunker`. O `.env` usa `800` / `150`, valores com que a base atual foi indexada |
| | `FORMULA_EXTRACTION_ENABLED` | `True` | Ativa OCR matemático via `pix2tex` no fallback PyMuPDF |
| | `ENABLE_QUERY_REWRITING` | `True` | Ativa reescrita de consultas no `ChatService` |
| **PostgreSQL** | `DATABASE_URL` | Montada via `POSTGRES_*` | String de conexão `postgresql+psycopg2://...` |
| **Admin Seed** | `ADMIN_EMAIL` / `ADMIN_PASSWORD` | `admin@vera.com` | Credenciais provisionadas no startup |

---

## 4. Mapa de Endpoints da API (`app/api/router.py`)

Todos os endpoints são montados sob `/api/v1` em `app/main.py`:

- **Saúde (`app/api/v1/health.py`)**:
  - `GET /api/v1/health`: status do serviço e conectividade com Ollama (`RN-INF02`).
- **Autenticação (`app/api/v1/auth.py`)**:
  - `POST /api/v1/auth/register`: cadastro de estudante (`role="student"`).
  - `POST /api/v1/auth/login`: autenticação OAuth2 (form) retornando token JWT.
  - `POST /api/v1/auth/login/json`: autenticação via corpo JSON (usada pelo frontend).
  - `GET /api/v1/auth/me`: perfil do usuário autenticado.
- **Tutora Virtual VERA (`app/api/v1/chat.py`)**:
  - `POST /api/v1/chat`: envia mensagem para a tutora RAG com CoT.
  - `GET /api/v1/chat/sessions`: lista sessões persistidas do estudante autenticado.
  - `GET /api/v1/chat/history/{session_id}`: recupera histórico completo de uma sessão.
  - `DELETE /api/v1/chat/session/{session_id}`: exclui uma sessão de conversa e seu histórico.
  - `PATCH /api/v1/chat/session/{session_id}`: renomeia o título de uma sessão.
- **Simulados (`app/api/v1/simulado.py` — prefixo `/api/v1/simulados`)**:
  - `POST /api/v1/simulados/gerar`: cria novo caderno estratificado de 45 questões (`RN-SIM01`).
  - `GET /api/v1/simulados/{simulado_id}`: obtém caderno para realização da prova **sem gabarito/justificativa** (`RN-SIM02`).
  - `POST /api/v1/simulados/{simulado_id}/submeter`: submete respostas, corrige tentativa, atualiza `desempenho_habilidades` e revela gabarito (`RN-SIM03`).
  - `GET /api/v1/simulados/`: lista os simulados do estudante.
  - `GET /api/v1/simulados/tentativas/me`: histórico de tentativas concluídas do estudante.
  - `GET /api/v1/simulados/tentativas/{tentativa_id}` e `GET /api/v1/simulados/{simulado_id}/resultado`: relatório de correção.
  - `DELETE /api/v1/simulados/{simulado_id}`: exclui um simulado e seus registros associados.
- **Questões Inéditas, só para administradores (`app/api/v1/admin_ineditas.py`, prefixo `/api/v1/admin/ineditas`)**:
  - A geração roda no serviço externo `questoes-ineditas-enem`, que expõe uma API HTTP na porta 8100.
  - Estas rotas repassam os lotes ao serviço (`/lotes`, `/lotes/{id}`, `/lotes/{id}/cancelar`, `/habilidades` e `/saude`) e importam para `questoes_ineditas` as questões aprovadas que o administrador escolhe (`/importar`).
  - Mais detalhes em [geracao-questoes-pot.md](../02-dominios-e-fluxos/geracao-questoes-pot.md).
- **Dashboard (`app/api/v1/dashboard.py` — prefixo `/api/v1/dashboard`)**:
  - `GET /api/v1/dashboard/desempenho`: diagnóstico consolidado por competência (`C1`–`C7`) e habilidade (`H01`–`H30`) + últimas tentativas.
- **Feedback por Item (`app/api/v1/feedback.py` — prefixo `/api/v1/feedback`)**:
  - `POST /api/v1/feedback/explicar`: gera ou retorna do cache o feedback da Tutora VERA para uma resposta errada (`RN-FB01` a `RN-FB04`); `422` se a explicação for reprovada na verificação contra o gabarito.
  - `GET /api/v1/feedback/{resposta_item_id}`: consulta feedback já gerado.

---

## Notas Relacionadas

- [Modelo de Dados e Persistência Relacional (PostgreSQL)](./modelo-relacional.md)
- [Pipeline de Ingestão e Banco Vetorial (Pinecone)](./ingestao-e-vetorizacao.md)
- [Decisões de Engenharia DSR](../00-fundamentos/decisoes-dsr.md)
