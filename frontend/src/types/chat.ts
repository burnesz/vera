export interface ChatMessage {
  id: string;
  sender: 'user' | 'vera';
  text: string;
  timestamp: string;
  session_id?: string;
  thought?: string;
  habilidade_codigo?: string;
  context_chunks?: Array<{
    id: string;
    title: string;
    topic: string;
    text: string;
    score: number;
    page_number?: number;
    document_name?: string;
  }>;
}

export interface ChatSessionSummary {
  id: string;
  titulo: string;
  created_at: string;
  updated_at: string;
  total_messages: number;
}

export interface ChatSessionListResponse {
  sessions: ChatSessionSummary[];
  total: number;
}

export interface ChatRequest {
  session_id?: string;
  message: string;
  top_k_context?: number;
  habilidade_alvo?: string;
}

export interface ChatResponse {
  session_id: string;
  reply: string;
  thought?: string;
  habilidade_detectada?: string;
  context_chunks?: any[];
  inference_time_seconds?: number;
}

export interface ChatHistoryResponse {
  session_id: string;
  titulo?: string;
  messages: Array<{
    id?: string;
    role?: 'user' | 'assistant' | 'system';
    sender?: 'user' | 'assistant';
    content?: string;
    text?: string;
    thought?: string;
    timestamp?: number | string;
    created_at?: string;
    context_chunks?: any[];
  }>;
  total_messages?: number;
}
