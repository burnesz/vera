export type AlternativaLetra = 'A' | 'B' | 'C' | 'D' | 'E';

export interface AlternativasDict {
  A: string;
  B: string;
  C: string;
  D: string;
  E: string;
}

export interface QuestaoItem {
  simulado_item_id: string;
  ordem: number;
  origem_questao: 'enem' | 'inedita';
  questao_id: string;
  ano?: number | null;
  habilidade_codigo: string;
  enunciado: string;
  alternativas: AlternativasDict;
}

export interface Simulado {
  id: string;
  user_id?: string | null;
  titulo: string;
  descricao?: string;
  tipo: string;
  total_itens: number;
  total_enem: number;
  total_ineditas: number;
  itens: QuestaoItem[];
  created_at: string;
}

export interface RespostaItemInput {
  questao_id: string;
  alternativa_marcada: AlternativaLetra | 'X';
}

export interface SimuladoSubmissaoPayload {
  respostas: RespostaItemInput[];
}

export interface ItemCorrecao {
  ordem: number;
  simulado_item_id: string;
  questao_id: string;
  habilidade_codigo: string;
  alternativa_selecionada?: AlternativaLetra | null;
  gabarito_oficial: string;
  is_correto: boolean;
}

export interface SimuladoResultado {
  tentativa_id: string;
  simulado_id: string;
  user_id: string;
  status: string;
  total_itens: number;
  total_acertos: number;
  score_percentual: number;
  started_at: string;
  completed_at: string;
  itens: ItemCorrecao[];
}
