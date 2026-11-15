import { apiFetch } from './api';
import type { DashboardDesempenhoData } from '../types/dashboard';

export const dashboardService = {
  /**
   * Obtém o diagnóstico consolidado de proficiência do estudante no ENEM:
   * estatísticas gerais, 7 Competências (C1-C7), 30 Habilidades (H01-H30) e histórico de tentativas.
   */
  async obterDashboardDesempenho(): Promise<DashboardDesempenhoData> {
    return await apiFetch<DashboardDesempenhoData>('/dashboard/desempenho');
  },
};
