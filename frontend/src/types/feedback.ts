export interface ContextChunk {
  id?: string;
  title?: string;
  topic?: string;
  text: string;
  score?: number;
  document_name?: string;
}

export interface FeedbackVera {
  id: string;
  resposta_item_id: string;
  habilidade_codigo: string;
  alternativa_marcada: string;
  gabarito_oficial: string;
  feedback_content: string;
  thought_scratchpad?: string | null;
  context_chunks: ContextChunk[];
  is_verified: boolean;
  created_at: string;
}
