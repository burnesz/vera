import { apiFetch } from './api';
import type { ChatRequest, ChatResponse, ChatHistoryResponse } from '../types/chat';

export const chatService = {
  /**
   * Envia uma mensagem para o endpoint real do backend FastAPI (/api/v1/chat),
   * que consulta Pinecone (RAG) e executa o Qwen2.5 via Ollama local com CoT.
   */
  async sendMessage(request: ChatRequest): Promise<ChatResponse> {
    return await apiFetch<ChatResponse>('/chat', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  },

  /**
   * Recupera o histórico de mensagens da sessão no backend.
   */
  async getHistory(sessionId: string): Promise<ChatHistoryResponse> {
    try {
      return await apiFetch<ChatHistoryResponse>(`/chat/history/${sessionId}`);
    } catch {
      return { session_id: sessionId, messages: [] };
    }
  },

  /**
   * Limpa o histórico de uma sessão de conversa no backend.
   */
  async clearSession(sessionId: string): Promise<{ cleared: boolean }> {
    try {
      return await apiFetch<{ cleared: boolean; message: string }>(`/chat/session/${sessionId}`, {
        method: 'DELETE',
      });
    } catch {
      return { cleared: true };
    }
  },
};
