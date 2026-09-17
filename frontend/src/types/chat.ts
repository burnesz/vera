export interface ChatMessage {
  id: string;
  sender: 'user' | 'vera';
  text: string;
  timestamp: string;
  session_id?: string;
  habilidade_codigo?: string;
}

export interface ChatRequest {
  session_id: string;
  message: string;
  habilidade_alvo?: string;
}

export interface ChatResponse {
  session_id: string;
  reply: string;
  habilidade_detectada?: string;
}

export interface ChatHistoryResponse {
  session_id: string;
  messages: Array<{
    sender: 'user' | 'assistant';
    text: string;
    timestamp: string;
  }>;
}
