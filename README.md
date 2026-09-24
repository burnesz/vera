# VERA — Validação e Ensino com Recuperação Aumentada

> **Plataforma baseada em RAG para feedback pedagógico personalizado e geração de questões inéditas de Matemática no contexto do ENEM.**
>
> *Projeto de Pesquisa e Desenvolvimento em Inteligência Artificial aplicada à Educação (TCC baseado na metodologia Design Science Research - DSR).*

---

## 📌 Sumário

- [Visão Geral](#-visão-geral)
- [Problema & Motivação](#-problema--motivação)
- [Arquitetura do Sistema](#-arquitetura-do-sistema)
- [Decisão de Engenharia DSR (Armazenamento Híbrido)](#-decisão-de-engenharia-dsr-armazenamento-híbrido)
- [Fluxos Centrais de IA](#-fluxos-centrais-de-ia)
  - [1. Simulado ENEM & Diagnóstico de Lacunas](#1-simulado-enem--diagnóstico-de-lacunas)
  - [2. Feedback Pedagógico (RAG + CoT)](#2-feedback-pedagógico-rag--cot)
  - [3. Geração de Questões Inéditas (Few-Shot Determinístico)](#3-geração-de-questões-inéditas-few-shot-determinístico)
  - [4. Tutora Virtual Interativa](#4-tutora-virtual-interativa)
- [Pilha Tecnológica](#-pilha-tecnológica)
- [Estrutura do Repositório](#-estrutura-do-repositório)
- [Configuração de Ambiente](#-configuração-de-ambiente)
- [Como Executar o Projeto](#-como-executar-o-projeto)
  - [Opção 1: Via Docker Compose (Recomendado)](#opção-1-via-docker-compose-recomendado)
  - [Opção 2: Execução Local (Desenvolvimento)](#opção-2-execução-local-desenvolvimento)
- [Scripts de Carga e Inicialização (Seeds)](#-scripts-de-carga-e-inicialização-seeds)
- [Suíte de Testes](#-suíte-de-testes)
- [Critérios de Avaliação e Baseline](#-critérios-de-avaliação-e-baseline)
- [Licença](#-licença)

---

## 🧠 Visão Geral

A plataforma **VERA** é um ambiente educacional inteligente voltado para a prova de **Matemática e suas Tecnologias do ENEM**, concebida sob o framework metodológico **Design Science Research (DSR)**.

A plataforma integra:
1. **Simulados realistas do ENEM** com 45 itens e amostragem estratificada pelas 30 habilidades oficiais (`H01` a `H30`) da Matriz de Referência do INEP.
2. **Tutoria com RAG (*Retrieval-Augmented Generation*)**: recuperação semântica de materiais didáticos para ancorar as explicações do LLM e erradicar alucinações conceituais.
3. **Chain-of-Thought (CoT) com auto-validação**: mecanismo de raciocínio passo a passo onde o modelo resolve a questão internamente antes de emitir a explicação didática.
4. **Geração de Questões Inéditas**: produção de novos itens no padrão rigoroso do ENEM (enunciado contextualizado, 5 alternativas e distratores plausíveis) com validação estrutural automática.
5. **Inferência 100% Local e Privada**: acionamento do modelo **Qwen 2.5 7B Instruct** quantizado via daemon do **Ollama**, assegurando soberania de dados, custo zero por token e reprodutibilidade científica.

---

## 🎯 Problema & Motivação

- **Gabaritos Secos**: No ensino tradicional e em plataformas de simulados convencionais, o estudante recebe apenas a indicação de acerto ou erro ("Gabarito: C"), sem entender o motivo de sua falha conceitual ou o distrator no qual caiu.
- **Limitações de LLMs Genéricos**: Modelos de linguagem generalistas em zero-shot cometem alucinações aritméticas, trocam gabaritos, não seguem a matriz de habilidades do INEP e frequentemente criam alternativas duplicadas ou incoerentes.
- **A Abordagem VERA**: Mitiga tais falhas combinando **banco relacional determinístico** (itens históricos reais do INEP para amostragem *few-shot*), **banco vetorial denso** (recuperação de teoria pedagógica), **prompts estruturados com raciocínio interno** e **validação programática estrita**.

---

## 🏗 Arquitetura do Sistema

```mermaid
flowchart TD
    subgraph Frontend ["Frontend Web (React + TypeScript + Vite)"]
        UI_Home[Home & Autenticação]
        UI_Simulado[Caderno de Simulado & Cartão Resposta]
        UI_Feedback[Relatório de Desempenho & Feedbacks]
        UI_Chat[Tutora Virtual VERA com CoT & LaTeX]
        UI_Dash[Dashboard de Habilidades H01-H30]
    end

    subgraph Backend ["Backend & Orquestração (FastAPI)"]
        API_Router["API Gateway /api/v1"]
        Auth_Service["Autenticação JWT & Usuários"]
        Simulado_Service["Engine de Simulados Estratificados"]
        Question_Service["Pipeline de Geração de Questões"]
        Question_Validator["Validador Estrutural (JSON, Unicidade)"]
        Chat_Service["Orquestrador de Tutoria RAG"]
        LLM_Client["LLM Client (Ollama Qwen 2.5 + Retry/Backoff)"]
    end

    subgraph Storage ["Armazenamento Híbrido"]
        Postgres[(PostgreSQL 15)]
        Pinecone[(Pinecone Vector DB)]
    end

    subgraph Inference ["Módulo de Inferência Local"]
        OllamaLocal["Ollama Daemon\nqwen2.5:7b-instruct-q4_K_M"]
    end

    Frontend <-->|REST API + JWT| API_Router
    API_Router --> Simulado_Service
    API_Router --> Question_Service
    API_Router --> Chat_Service
    API_Router --> Auth_Service

    Simulado_Service <--> Postgres
    Question_Service <-->|Few-Shot Determinístico| Postgres
    Question_Service --> Question_Validator
    Question_Service <--> LLM_Client
    Chat_Service <--> LLM_Client
    Chat_Service <-->|Embeddings Multilingual-E5| Pinecone

    LLM_Client <-->|HTTP /api/chat| OllamaLocal
```

---

## 💡 Decisão de Engenharia DSR (Armazenamento Híbrido)

Durante o desenvolvimento do protótipo e os ciclos de avaliação da DSR, adotou-se uma evolução arquitetural estratégica em relação ao armazenamento:

| Componente | Repositório | Estratégia de Consulta | Justificativa Técnica |
|---|---|---|---|
| **Acervo Histórico do ENEM (2009–2024)** | **PostgreSQL** (`questoes_enem`) | Filtragem relacional direta (`WHERE habilidade_codigo = :habilidade`) | **100% determinístico**. Na geração de questões inéditas, o modelo necessita de itens de exemplo *da mesma habilidade*. A busca relacional elimina ruídos semânticos do Pinecone (que poderia resgatar itens de habilidades vizinhas por termos correlatos). Custo zero de embeddings e integridade relacional com simulados. |
| **Materiais Didáticos Teóricos** | **Pinecone** (`materiais_didaticos`) | Busca vetorial por similaridade de cosseno (1024 dimensões) | **Similaridade semântica**. Quando o estudante erra ou faz uma pergunta conceitual na tutoria, a busca semântica recupera os trechos explicativos mais pertinentes nos materiais didáticos (PDFs processados). |
| **Questões Inéditas Geradas** | **PostgreSQL** (`questoes_ineditas`) | Inserção após validação estrutural estrita | Persistência auditável de itens gerados pelo LLM com histórico de geração, gabarito e justificativa. |

---

## 🔄 Fluxos Centrais de IA

### 1. Simulado ENEM & Diagnóstico de Lacunas
- O estudante gera um simulado oficial com **45 itens** estruturado conforme o ENEM:
  - 28 questões base cobrindo 100% das habilidades textuais disponíveis no banco.
  - 17 questões complementares balanceadas nas habilidades de maior incidência histórica.
- Interface cronometrada com folha de respostas dinâmica, marcação de dúvidas e submissão formal.
- Na submissão, a correção automática identifica imediatamente quais habilidades apresentaram erro.

### 2. Feedback Pedagógico (RAG + CoT)
- **Retrieval**: Recupera trechos conceituais relevantes da habilidade no namespace `materiais_didaticos` do Pinecone.
- **CoT**: Prompt direciona o LLM a pensar passo a passo no scratchpad (`<pensamento>`), calculando o resultado e analisando por que a alternativa marcada pelo estudante é um distrator plausível.
- **Verificação**: Checagem de consistência contra o gabarito oficial do INEP antes de entregar a resposta final.

### 3. Geração de Questões Inéditas (Few-Shot Determinístico)
- **Seleção de Contexto**: O `QuestionService` resgata $k$ questões históricas reais do PostgreSQL exatamente da habilidade solicitada.
- **Prompt Few-Shot**: O LLM gera uma questão inédita (situação-problema contextualizada no cotidiano, 5 alternativas e 1 gabarito).
- **Validação Estrutural Estrita (`QuestionValidator`)**:
  - Validação de Schema JSON (campos `enunciado`, `alternativas`, `gabarito_correto`, `justificativa`).
  - Presença das 5 alternativas (A, B, C, D, E).
  - Unicidade estrita: rejeita questões com textos ou números repetidos entre alternativas.
  - Exatamente um gabarito pertencente ao conjunto {A, B, C, D, E}.
  - Descarte e re-tentativa automática caso falhe nas regras (RN-Q01).

### 4. Tutora Virtual Interativa
- Chat conversacional com suporte a equações matemáticas em **LaTeX / KaTeX**.
- Transparência pedagógica: exibe bloco expansível de **Raciocínio Interno (<pensamento>)** e cita os materiais didáticos recuperados via RAG.
- Histórico de mensagens persistente no PostgreSQL com suporte a múltiplas conversas.

---

## 💻 Pilha Tecnológica

### Backend & Inteligência Artificial
- **Linguagem**: Python 3.10+
- **Framework Web**: [FastAPI](https://fastapi.tiangolo.com/) com rotas assíncronas e esquemas Pydantic v2
- **Orquestração LLM**: LangChain / Prompts estruturados versionados
- **Modelo de Linguagem (LLM)**: `qwen2.5:7b-instruct-q4_K_M` executado localmente via [Ollama](https://ollama.com/)
- **Embeddings Vetoriais**: `intfloat/multilingual-e5-large` (1024 dimensões)
- **Banco Vetorial**: [Pinecone](https://www.pinecone.io/) (Namespace `materiais_didaticos`)
- **Banco Relacional & ORM**: PostgreSQL 15 + SQLAlchemy 2.0
- **Autenticação**: JWT (JSON Web Tokens) com senhas criptografadas via Bcrypt
- **Testes Automatizados**: Pytest (65+ testes unitários e de integração)

### Frontend Web
- **Linguagem & Framework**: React 18, TypeScript, [Vite](https://vitejs.dev/)
- **Estilização**: Vanilla CSS com design system customizado (Ocean & Coral Palette, suporte responsivo)
- **Renderização Matemática**: KaTeX / MathText com regex inteligente para fórmulas inline (`$...$`) e em bloco (`$$...$$`)
- **Navegação & Roteamento**: Roteador leve de estado sincronizado com a History API do navegador

---

## 📂 Estrutura do Repositório

```text
vera/
├── app/                        # Núcleo da aplicação Backend (FastAPI)
│   ├── api/                    # Camada de rotas HTTP
│   │   ├── deps.py             # Injeção de dependências (DB, Autenticação)
│   │   ├── router.py           # Agregador central de rotas
│   │   └── v1/                 # Endpoints v1 (auth, simulado, questoes, chat, health)
│   ├── core/                   # Configurações globais e prompts
│   │   ├── config.py           # Leitura de variáveis de ambiente (Pydantic Settings)
│   │   ├── prompts.py          # Templates de CoT, Few-Shot e Tutoria
│   │   └── security.py         # Criptografia de senhas e tokens JWT
│   ├── db/                     # Camada de persistência relacional
│   │   ├── base.py             # Declarative Base do SQLAlchemy
│   │   ├── session.py          # Session factory do PostgreSQL
│   │   ├── init_db.py          # Inicialização e auto-provisionamento de admin
│   │   └── models/             # Modelos relacionais (User, QuestaoEnem, Simulado, etc.)
│   ├── pipeline/               # Ingestão e processamento de dados offline
│   │   ├── chunking.py         # Chunking semântico de PDFs didáticos
│   │   ├── extract_inep.py     # Parser dos microdados brutos do INEP
│   │   └── index_embeddings.py # Vetorização e carga no Pinecone
│   ├── schemas/                # Schemas Pydantic para validação de entrada/saída
│   └── services/               # Lógica de negócio e orquestração de IA
│       ├── chat_service.py     # Sessões de conversa e injeção de contexto RAG
│       ├── llm_client.py       # Cliente HTTP assíncrono para o daemon do Ollama
│       ├── question_service.py # Engine de geração de questões com Few-Shot
│       ├── question_validator.py # Validação estrutural de itens gerados (RN-Q01)
│       ├── simulado_service.py # Montagem, amostragem e correção de simulados
│       └── vectorstore.py      # Interface de busca vetorial no Pinecone
├── data/                       # Arquivos de dados e acervos enriquecidos
│   └── itens_prova_2009_2024_enriquecido.csv # Microdados tratados do INEP
├── frontend/                   # Interface Web moderna em React + TypeScript + Vite
│   ├── src/
│   │   ├── components/         # Componentes reutilizáveis (MathText, Navbar, Sidebar, etc.)
│   │   ├── context/            # Estado global (AuthContext com token JWT e perfil)
│   │   ├── pages/              # Telas (HomePage, SimuladoPage, ChatPage, Login, etc.)
│   │   └── services/           # Clientes HTTP (api.ts, simuladoService.ts, chatService.ts)
│   ├── Dockerfile              # Build multi-stage com Nginx
│   └── package.json            # Dependências do frontend
├── scripts/                    # Utilitários de CLI e migração
│   ├── init_db.sql             # DDL completo das tabelas PostgreSQL
│   ├── seed_habilidades.py     # Carga das 30 habilidades da Matriz do ENEM
│   ├── seed_questoes.py        # Carga dos itens do ENEM a partir do CSV
│   ├── populate_questoes_ineditas.py # Geração em lote de itens inéditos via Ollama
│   └── ollama_forwarder.py     # Proxy de compatibilidade de rede
├── tests/                      # Bateria de testes unitários e de integração
│   ├── test_auth.py            # Testes de autenticação e tokens
│   ├── test_chat.py            # Testes do serviço conversacional RAG
│   ├── test_question_service.py# Testes da geração few-shot de itens
│   ├── test_question_validator.py # Testes dos critérios de rejeição de questões
│   └── test_simulados.py       # Testes de geração e correção de simulados
├── docker-compose.yml          # Orquestração dos containers (API + DB + Web)
├── Dockerfile                  # Container da API FastAPI
├── requirements.txt            # Dependências Python
└── AGENTS.md                   # Caderno de Regras de Negócio e Diretrizes de Engenharia
```

---

## ⚙ Configuração de Ambiente

Crie o arquivo `.env` na raiz do projeto a partir do modelo `.env.example`:

```bash
cp .env.example .env
```

Principais variáveis de configuração:

```ini
# Configurações da API
PROJECT_NAME="VERA API"
VERSION="0.1.0"
API_V1_STR="/api/v1"

# Segurança & Autenticação
JWT_SECRET_KEY="sua-chave-secreta-jwt-em-producao"
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# LLM Local (Ollama)
LLM_ENDPOINT_URL=http://localhost:11434
LLM_MODEL=qwen2.5:7b-instruct-q4_K_M
LLM_TIMEOUT_SECONDS=120.0

# Banco Vetorial (Pinecone)
PINECONE_API_KEY=seu_pinecone_api_key
PINECONE_ENVIRONMENT=us-east-1
PINECONE_INDEX_NAME=vera-math-index
EMBEDDING_MODEL_NAME=intfloat/multilingual-e5-large

# Banco Relacional (PostgreSQL)
POSTGRES_SERVER=localhost
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=vera_db
POSTGRES_PORT=5432
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/vera_db

# Provisionamento Automático do Administrador Inicial
ADMIN_NAME="Administrador VERA"
ADMIN_EMAIL=admin@vera.com
ADMIN_PASSWORD=admin_seguro_123

# Frontend
FRONTEND_PORT=3000
```

---

## 🚀 Como Executar o Projeto

### Pré-requisito: Modelo Qwen 2.5 no Ollama

Certifique-se de que o **Ollama** está instalado e o modelo de 7B baixado:

```bash
# Iniciar o daemon do Ollama
ollama serve

# Baixar o modelo Qwen 2.5 7B quantizado
ollama pull qwen2.5:7b-instruct-q4_K_M
```

---

### Opção 1: Via Docker Compose (Recomendado)

O `docker-compose.yml` sobe a aplicação completa em contêineres:
- **`postgres`**: Banco relacional na porta `5432`.
- **`api`**: Backend FastAPI na porta `8000`.
- **`frontend`**: Frontend React servido via Nginx na porta `3000`.

```bash
# Construir as imagens e iniciar os serviços
docker compose up --build -d

# Visualizar logs em tempo real
docker compose logs -f
```

Acesse:
- **Aplicação Web**: [http://localhost:3000](http://localhost:3000)
- **Documentação Interativa Swagger (API)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Redoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

### Opção 2: Execução Local (Desenvolvimento)

#### 1. Iniciar Banco de Dados
Caso opte por rodar a API localmente, mantenha apenas o container do PostgreSQL ativo:
```bash
docker compose up -d postgres
```

#### 2. Ambiente Virtual Python (Backend)
```bash
# Criar e ativar o ambiente virtual
python3 -m venv .venv
source .venv/bin/activate

# Instalar dependências
pip install -r requirements.txt

# Executar a API em modo reload
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### 3. Frontend Web
Em outro terminal:
```bash
cd frontend
npm install
npm run dev
```

---

## 📦 Scripts de Carga e Inicialização (Seeds)

Após iniciar o PostgreSQL, popule o banco de dados com a Matriz de Referência e as questões históricas do ENEM:

### 1. Carregar as 30 Habilidades Oficiais do ENEM (`H01` a `H30`)
```bash
python scripts/seed_habilidades.py
```

### 2. Importar o Acervo Histórico de Questões do ENEM (2009–2024)
Lê o arquivo enriquecido em `data/itens_prova_2009_2024_enriquecido.csv` e popula a tabela `questoes_enem`:
```bash
python scripts/seed_questoes.py
```

### 3. Povoar Questões Inéditas com o LLM Local
Executa o pipeline de geração de questões com *few-shot* a partir dos dados do PostgreSQL:
```bash
# Gerar 1 questão inédita para todas as 30 habilidades via Ollama local:
python scripts/populate_questoes_ineditas.py --habilidades all --count 1

# Gerar para habilidades específicas:
python scripts/populate_questoes_ineditas.py --habilidades H01,H02,H03

# Modo simulação (rápido/mock para validação de testes sem carregar o LLM):
python scripts/populate_questoes_ineditas.py --habilidades all --mock
```

---

## 🧪 Suíte de Testes

O projeto conta com mais de 60 testes automatizados cobrindo autenticação, integridade dos modelos relacionais, geração de simulados, regras do validador de questões e endpoints da API.

Execute a suíte com o Pytest:

```bash
# Executar todos os testes
pytest -v

# Executar com relatório de cobertura
pytest --cov=app tests/
```

---

## 📊 Critérios de Avaliação e Baseline

Para atender ao rigor acadêmico da pesquisa de TCC baseada em DSR:

- **Baseline Comparativa**: O sistema conta com serviço desacoplado que opera o mesmo modelo `Qwen2.5-7B` em **zero-shot** (sem injeção de contexto RAG e sem exemplos *few-shot* históricos).
- **Métricas Quantitativas**:
  - Precisão e recall da recuperação semântica no namespace `materiais_didaticos`.
  - Latência e tempo de inferência local.
  - Taxa de descarte/alucinação detectada pelo `QuestionValidator`.
- **Avaliação Qualitativa**: Avaliação cega com especialista em Matemática do ENEM baseada em rubrica Likert (1 a 5), aferindo correção factual, clareza pedagógica, adequação dos distratores e ausência de alucinações conceituais.

---

## 📜 Licença

Desenvolvido para fins de pesquisa acadêmica e inovação educacional aberta.
Consulte as diretrizes em [AGENTS.md](AGENTS.md) para detalhes adicionais de regras de negócio.
