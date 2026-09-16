-- ==============================================================================
-- VERA: Script DDL de Inicialização do Banco de Dados Relacional (PostgreSQL)
-- Plataforma baseada em RAG para Tutoria e Simulados de Matemática do ENEM
-- ==============================================================================

-- Extensão para geração nativa de UUIDs (compatível com PostgreSQL 13+)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ------------------------------------------------------------------------------
-- 1. Tabela: users (Estudantes e Administradores)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nome VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'student',
    is_ativo BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

-- ------------------------------------------------------------------------------
-- 2. Tabela: habilidades_enem (Matriz de Referência de Matemática do ENEM)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS habilidades_enem (
    codigo VARCHAR(10) PRIMARY KEY, -- Ex: 'H01', 'H02', ..., 'H30'
    competencia INTEGER NOT NULL,    -- 1 a 7
    descricao TEXT NOT NULL,
    eixo_tematico VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_habilidades_competencia ON habilidades_enem(competencia);

-- ------------------------------------------------------------------------------
-- 3. Tabela: questoes_enem (Acervo Histórico Original extraído de CSV)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS questoes_enem (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ano INTEGER NOT NULL,
    habilidade_codigo VARCHAR(10) NOT NULL REFERENCES habilidades_enem(codigo) ON DELETE RESTRICT,
    enunciado TEXT NOT NULL,
    alternativas JSONB NOT NULL,
    gabarito CHAR(1) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_questoes_enem_ano ON questoes_enem(ano);
CREATE INDEX IF NOT EXISTS idx_questoes_enem_hab ON questoes_enem(habilidade_codigo);

-- ------------------------------------------------------------------------------
-- 4. Tabela: questoes_ineditas (Geradas pelo LLM Qwen2.5 para Treino do Aluno)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS questoes_ineditas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    habilidade_codigo VARCHAR(10) NOT NULL REFERENCES habilidades_enem(codigo) ON DELETE RESTRICT,
    enunciado TEXT NOT NULL,
    alternativas JSONB NOT NULL,
    gabarito CHAR(1) NOT NULL,
    justificativa TEXT NOT NULL,
    thought_scratchpad TEXT,
    is_validated BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_questoes_ineditas_hab ON questoes_ineditas(habilidade_codigo);
CREATE INDEX IF NOT EXISTS idx_questoes_ineditas_validated ON questoes_ineditas(is_validated);

-- ------------------------------------------------------------------------------
-- 5. Tabela: simulados (Cadernos de Simulado)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS simulados (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    titulo VARCHAR(255) NOT NULL,
    descricao TEXT,
    tipo VARCHAR(50) NOT NULL DEFAULT 'diagnostico',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_simulados_tipo ON simulados(tipo);

-- ------------------------------------------------------------------------------
-- 6. Tabela: simulado_itens (Composição dos Itens do Simulado)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS simulado_itens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    simulado_id UUID NOT NULL REFERENCES simulados(id) ON DELETE CASCADE,
    ordem INTEGER NOT NULL,
    origem_questao VARCHAR(20) NOT NULL, -- 'enem' ou 'inedita'
    questao_enem_id UUID REFERENCES questoes_enem(id) ON DELETE CASCADE,
    questao_inedita_id UUID REFERENCES questoes_ineditas(id) ON DELETE CASCADE,
    CONSTRAINT chk_simulado_item_origem CHECK (
        (origem_questao = 'enem' AND questao_enem_id IS NOT NULL AND questao_inedita_id IS NULL) OR
        (origem_questao = 'inedita' AND questao_inedita_id IS NOT NULL AND questao_enem_id IS NULL)
    ),
    CONSTRAINT uq_simulado_item_ordem UNIQUE (simulado_id, ordem)
);

CREATE INDEX IF NOT EXISTS idx_simulado_itens_simulado ON simulado_itens(simulado_id);

-- ------------------------------------------------------------------------------
-- 7. Tabela: simulado_tentativas (Submissões de Simulados pelos Estudantes)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS simulado_tentativas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    simulado_id UUID NOT NULL REFERENCES simulados(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'in_progress', -- 'in_progress', 'completed', 'abandoned'
    total_itens INTEGER NOT NULL DEFAULT 0,
    total_acertos INTEGER NOT NULL DEFAULT 0,
    score_percentual DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_tentativas_user ON simulado_tentativas(user_id);
CREATE INDEX IF NOT EXISTS idx_tentativas_simulado ON simulado_tentativas(simulado_id);
CREATE INDEX IF NOT EXISTS idx_tentativas_status ON simulado_tentativas(status);

-- ------------------------------------------------------------------------------
-- 8. Tabela: respostas_itens (Respostas Dadas pelo Estudante)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS respostas_itens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tentativa_id UUID NOT NULL REFERENCES simulado_tentativas(id) ON DELETE CASCADE,
    origem_questao VARCHAR(20) NOT NULL, -- 'enem' ou 'inedita'
    questao_enem_id UUID REFERENCES questoes_enem(id) ON DELETE CASCADE,
    questao_inedita_id UUID REFERENCES questoes_ineditas(id) ON DELETE CASCADE,
    alternativa_marcada CHAR(1) NOT NULL,
    is_correta BOOLEAN NOT NULL,
    answered_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_resposta_item_origem CHECK (
        (origem_questao = 'enem' AND questao_enem_id IS NOT NULL AND questao_inedita_id IS NULL) OR
        (origem_questao = 'inedita' AND questao_inedita_id IS NOT NULL AND questao_enem_id IS NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_respostas_tentativa ON respostas_itens(tentativa_id);
CREATE INDEX IF NOT EXISTS idx_respostas_correta ON respostas_itens(is_correta);

-- ------------------------------------------------------------------------------
-- 9. Tabela: feedbacks (Feedback Pedagógico Gerado para Erros - RN-FB01)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS feedbacks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resposta_item_id UUID UNIQUE NOT NULL REFERENCES respostas_itens(id) ON DELETE CASCADE,
    feedback_content TEXT NOT NULL,
    thought_scratchpad TEXT,
    context_chunks JSONB NOT NULL DEFAULT '[]'::jsonb,
    is_verified BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_feedbacks_resposta ON feedbacks(resposta_item_id);

-- ------------------------------------------------------------------------------
-- 10. Tabela: desempenho_habilidades (Histórico Agregado de Domínio)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS desempenho_habilidades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    habilidade_codigo VARCHAR(10) NOT NULL REFERENCES habilidades_enem(codigo) ON DELETE CASCADE,
    total_questoes INTEGER NOT NULL DEFAULT 0,
    total_acertos INTEGER NOT NULL DEFAULT 0,
    taxa_acerto DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    nivel_dominio VARCHAR(20) NOT NULL DEFAULT 'em_desenvolvimento',
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_user_habilidade_desempenho UNIQUE (user_id, habilidade_codigo)
);

CREATE INDEX IF NOT EXISTS idx_desempenho_user ON desempenho_habilidades(user_id);
CREATE INDEX IF NOT EXISTS idx_desempenho_hab ON desempenho_habilidades(habilidade_codigo);

-- ------------------------------------------------------------------------------
-- 11. Tabelas: chat_sessions e chat_messages (Tutora VERA)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS chat_sessions (
    id VARCHAR(100) PRIMARY KEY, -- Session UUID string
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    titulo VARCHAR(255) NOT NULL DEFAULT 'Conversa com VERA',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_user ON chat_sessions(user_id);

CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(100) NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL, -- 'user', 'assistant', 'system'
    content TEXT NOT NULL,
    thought TEXT,
    context_chunks JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_created ON chat_messages(created_at);
