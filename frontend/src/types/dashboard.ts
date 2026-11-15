export interface HabilidadeProgresso {
  habilidade_codigo: string;
  competencia: number;
  descricao: string;
  eixo_tematico?: string | null;
  total_questoes: number;
  total_acertos: number;
  taxa_acerto: number;
  nivel_dominio: 'critico' | 'em_desenvolvimento' | 'consolidado';
  updated_at?: string | null;
}

export interface CompetenciaProgresso {
  competencia: number;
  titulo: string;
  descricao: string;
  total_questoes: number;
  total_acertos: number;
  taxa_acerto: number;
  nivel_dominio: 'critico' | 'em_desenvolvimento' | 'consolidado';
  habilidades_total: number;
  habilidades_consolidadas: number;
}

export interface TentativaResumo {
  tentativa_id: string;
  simulado_id: string;
  titulo: string;
  total_itens: number;
  total_acertos: number;
  score_percentual: number;
  started_at: string;
  completed_at?: string | null;
}

export interface DashboardDesempenhoData {
  total_simulados: number;
  total_questoes_respondidas: number;
  total_acertos: number;
  taxa_acerto_global: number;
  total_habilidades_consolidadas: number;
  total_habilidades_em_desenvolvimento: number;
  total_habilidades_criticas: number;
  competencias: CompetenciaProgresso[];
  habilidades: HabilidadeProgresso[];
  ultimas_tentativas: TentativaResumo[];
}
