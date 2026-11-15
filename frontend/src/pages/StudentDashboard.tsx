import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { dashboardService } from '../services/dashboardService';
import type { DashboardDesempenhoData, HabilidadeProgresso } from '../types/dashboard';
import {
  FileCheck2,
  BotMessageSquare,
  Sparkles,
  ArrowRight,
  Clock,
  Target,
  BookOpen,
  Zap,
  Award,
  AlertTriangle,
  CheckCircle2,
  Calendar,
  RotateCcw,
} from 'lucide-react';

interface StudentDashboardProps {
  onNavigate: (page: string) => void;
}

type HabilidadeFilter = 'todas' | 'critico' | 'em_desenvolvimento' | 'consolidado';

export const StudentDashboard: React.FC<StudentDashboardProps> = ({ onNavigate }) => {
  const { user } = useAuth();
  const firstName = user?.nome ? user.nome.split(' ')[0] : 'Estudante';

  const [dashboardData, setDashboardData] = useState<DashboardDesempenhoData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [habilidadeFilter, setHabilidadeFilter] = useState<HabilidadeFilter>('todas');

  useEffect(() => {
    let isMounted = true;
    async function carregarDashboard() {
      setIsLoading(true);
      try {
        const data = await dashboardService.obterDashboardDesempenho();
        if (isMounted) {
          setDashboardData(data);
        }
      } catch (err) {
        console.warn('Erro ao carregar dados do dashboard na API:', err);
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }
    carregarDashboard();
    return () => {
      isMounted = false;
    };
  }, []);

  const habilidadesFiltradas: HabilidadeProgresso[] = (dashboardData?.habilidades || []).filter((h) => {
    if (habilidadeFilter === 'todas') return true;
    return h.nivel_dominio === habilidadeFilter;
  });

  const getDominioBadge = (nivel: string) => {
    switch (nivel) {
      case 'consolidado':
        return (
          <span className="badge badge-success" style={{ gap: '0.25rem', display: 'inline-flex', alignItems: 'center' }}>
            <CheckCircle2 size={12} />
            Consolidado
          </span>
        );
      case 'critico':
        return (
          <span className="badge badge-danger" style={{ gap: '0.25rem', display: 'inline-flex', alignItems: 'center' }}>
            <AlertTriangle size={12} />
            Crítico
          </span>
        );
      default:
        return (
          <span className="badge badge-ocean" style={{ gap: '0.25rem', display: 'inline-flex', alignItems: 'center' }}>
            <Sparkles size={12} />
            Em Desenvolvimento
          </span>
        );
    }
  };

  const getDominioColor = (nivel: string) => {
    switch (nivel) {
      case 'consolidado':
        return 'var(--color-success)';
      case 'critico':
        return 'var(--color-danger)';
      default:
        return 'var(--ocean-600)';
    }
  };

  return (
    <div style={{ padding: '2rem 2rem 4rem', maxWidth: '1280px', margin: '0 auto', width: '100%' }}>
      {/* Banner de Boas-Vindas */}
      <section
        style={{
          background: 'linear-gradient(135deg, var(--ocean-900) 0%, var(--ocean-700) 100%)',
          borderRadius: 'var(--radius-lg)',
          padding: '2.5rem',
          color: 'var(--white)',
          marginBottom: '2rem',
          boxShadow: 'var(--shadow-ocean)',
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        <div style={{ maxWidth: '780px', position: 'relative', zIndex: 2 }}>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.5rem',
              backgroundColor: 'rgba(255, 255, 255, 0.15)',
              padding: '0.35rem 0.85rem',
              borderRadius: 'var(--radius-full)',
              fontSize: '0.85rem',
              fontWeight: 600,
              marginBottom: '1rem',
              backdropFilter: 'blur(4px)',
            }}
          >
            <Sparkles size={16} />
            Diagnóstico Pedagógico • Matemática ENEM
          </div>

          <h2
            style={{
              fontSize: 'clamp(1.8rem, 3.5vw, 2.35rem)',
              fontWeight: 800,
              color: 'var(--white)',
              lineHeight: 1.2,
              marginBottom: '0.85rem',
            }}
          >
            Olá, {firstName}! Bem-vindo ao seu painel.
          </h2>

          <p
            style={{
              fontSize: '1.05rem',
              color: 'var(--ocean-100)',
              lineHeight: 1.6,
              marginBottom: '1.75rem',
              maxWidth: '660px',
            }}
          >
            Acompanhe seu nível de domínio nas <strong>30 habilidades</strong> da Matriz de Referência do ENEM,
            analise os acertos dos seus simulados e treine com a Tutora VERA.
          </p>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.85rem' }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                backgroundColor: 'rgba(255, 255, 255, 0.12)',
                padding: '0.45rem 0.95rem',
                borderRadius: 'var(--radius-md)',
                fontSize: '0.85rem',
                fontWeight: 600,
              }}
            >
              <Clock size={16} />
              <span>Caderno Oficial: 45 Itens</span>
            </div>

            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                backgroundColor: 'rgba(255, 255, 255, 0.12)',
                padding: '0.45rem 0.95rem',
                borderRadius: 'var(--radius-md)',
                fontSize: '0.85rem',
                fontWeight: 600,
              }}
            >
              <Target size={16} />
              <span>30 Habilidades Mapeadas (H01–H30)</span>
            </div>
          </div>
        </div>
      </section>

      {/* Grid de Métricas Chave em Tempo Real */}
      <section style={{ marginBottom: '2.5rem' }}>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: '1.25rem',
          }}
        >
          {/* Card 1: Simulados Concluídos */}
          <div className="card" style={{ padding: '1.5rem', display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <div
              style={{
                width: '48px',
                height: '48px',
                borderRadius: '12px',
                backgroundColor: 'var(--ocean-100)',
                color: 'var(--ocean-700)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}
            >
              <FileCheck2 size={24} />
            </div>
            <div>
              <div style={{ fontSize: '1.8rem', fontWeight: 800, color: 'var(--ocean-950)', lineHeight: 1.1 }}>
                {isLoading ? '--' : dashboardData?.total_simulados ?? 0}
              </div>
              <div style={{ fontSize: '0.825rem', fontWeight: 600, color: 'var(--text-muted)' }}>
                Simulados Concluídos
              </div>
            </div>
          </div>

          {/* Card 2: Taxa de Acerto Global */}
          <div className="card" style={{ padding: '1.5rem', display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <div
              style={{
                width: '48px',
                height: '48px',
                borderRadius: '12px',
                backgroundColor: 'var(--ocean-100)',
                color: 'var(--ocean-700)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}
            >
              <Award size={24} />
            </div>
            <div>
              <div style={{ fontSize: '1.8rem', fontWeight: 800, color: 'var(--ocean-950)', lineHeight: 1.1 }}>
                {isLoading ? '--' : `${dashboardData?.taxa_acerto_global ?? 0}%`}
              </div>
              <div style={{ fontSize: '0.825rem', fontWeight: 600, color: 'var(--text-muted)' }}>
                Aproveitamento Global
              </div>
            </div>
          </div>

          {/* Card 3: Total Questões Respondidas */}
          <div className="card" style={{ padding: '1.5rem', display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <div
              style={{
                width: '48px',
                height: '48px',
                borderRadius: '12px',
                backgroundColor: 'var(--ocean-100)',
                color: 'var(--ocean-700)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}
            >
              <Target size={24} />
            </div>
            <div>
              <div style={{ fontSize: '1.8rem', fontWeight: 800, color: 'var(--ocean-950)', lineHeight: 1.1 }}>
                {isLoading ? '--' : dashboardData?.total_questoes_respondidas ?? 0}
              </div>
              <div style={{ fontSize: '0.825rem', fontWeight: 600, color: 'var(--text-muted)' }}>
                Questões Respondidas
              </div>
            </div>
          </div>

          {/* Card 4: Diagnóstico de Lacunas */}
          <div className="card" style={{ padding: '1.5rem', display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <div
              style={{
                width: '48px',
                height: '48px',
                borderRadius: '12px',
                backgroundColor: 'var(--color-success-bg)',
                color: 'var(--color-success)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}
            >
              <CheckCircle2 size={24} />
            </div>
            <div>
              <div style={{ fontSize: '1.8rem', fontWeight: 800, color: 'var(--ocean-950)', lineHeight: 1.1 }}>
                {isLoading ? '--' : `${dashboardData?.total_habilidades_consolidadas ?? 0} / 30`}
              </div>
              <div style={{ fontSize: '0.825rem', fontWeight: 600, color: 'var(--text-muted)' }}>
                Habilidades Consolidadas
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Ações Rápidas de Estudo */}
      <section style={{ marginBottom: '3rem' }}>
        <div style={{ marginBottom: '1.25rem' }}>
          <h3 style={{ fontSize: '1.45rem', fontWeight: 800, color: 'var(--ocean-950)' }}>
            Ações Rápidas de Estudo
          </h3>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.925rem' }}>
            Inicie um novo teste ou abra a tutoria com a inteligência pedagógica da VERA
          </p>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
            gap: '1.75rem',
          }}
        >
          {/* Card Simulado Geral */}
          <div
            className="card"
            style={{
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              borderTop: '5px solid var(--ocean-600)',
              padding: '2rem',
            }}
          >
            <div>
              <div
                style={{
                  width: '52px',
                  height: '52px',
                  borderRadius: '14px',
                  backgroundColor: 'var(--ocean-100)',
                  color: 'var(--ocean-700)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  marginBottom: '1.25rem',
                }}
              >
                <FileCheck2 size={30} />
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
                <span className="badge badge-ocean">Caderno Oficial</span>
                <span className="badge badge-dark">45 Questões</span>
              </div>

              <h4 style={{ fontSize: '1.35rem', fontWeight: 800, color: 'var(--text-primary)', marginBottom: '0.75rem' }}>
                Simulado Geral de Matemática
              </h4>

              <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem', lineHeight: 1.6, marginBottom: '1.5rem' }}>
                Caderno estratificado de 45 questões (históricas e inéditas). Cronômetro integrado, folha de respostas
                e conferência imediata com explicações guiadas.
              </p>
            </div>

            <button
              onClick={() => onNavigate('simulado')}
              className="btn btn-primary btn-lg"
              style={{ width: '100%', justifyContent: 'space-between' }}
            >
              <span style={{ fontWeight: 700 }}>Acessar Simulados</span>
              <ArrowRight size={20} />
            </button>
          </div>

          {/* Card Tutora VERA */}
          <div
            className="card"
            style={{
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              borderTop: '5px solid var(--ocean-500)',
              padding: '2rem',
            }}
          >
            <div>
              <div
                style={{
                  width: '52px',
                  height: '52px',
                  borderRadius: '14px',
                  backgroundColor: 'var(--ocean-100)',
                  color: 'var(--ocean-700)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  marginBottom: '1.25rem',
                }}
              >
                <BotMessageSquare size={30} />
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
                <span className="badge badge-ocean">RAG + CoT</span>
                <span className="badge badge-success">Online 24/7</span>
              </div>

              <h4 style={{ fontSize: '1.35rem', fontWeight: 800, color: 'var(--text-primary)', marginBottom: '0.75rem' }}>
                Tutora VERA (IA Especialista)
              </h4>

              <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem', lineHeight: 1.6, marginBottom: '1.5rem' }}>
                Converse com a tutora treinada para explicar distratores, apresentar resoluções passo a passo em LaTeX
                e orientar seu plano de estudos individualizado.
              </p>
            </div>

            <button
              onClick={() => onNavigate('chat')}
              className="btn btn-outline btn-lg"
              style={{ width: '100%', justifyContent: 'space-between' }}
            >
              <span style={{ fontWeight: 700 }}>Abrir Conversa com VERA</span>
              <ArrowRight size={20} />
            </button>
          </div>
        </div>
      </section>

      {/* Seção das 7 Competências com Barras de Progresso */}
      <section style={{ marginBottom: '3rem' }}>
        <div style={{ marginBottom: '1.25rem' }}>
          <h3 style={{ fontSize: '1.45rem', fontWeight: 800, color: 'var(--ocean-950)' }}>
            Proficiência nas 7 Competências de Área (INEP)
          </h3>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.925rem' }}>
            Acompanhe o rendimento acumulado em cada um dos 7 eixos estruturantes da prova
          </p>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
            gap: '1.25rem',
          }}
        >
          {(dashboardData?.competencias || []).map((comp) => {
            const pct = Math.round(comp.taxa_acerto * 100);
            return (
              <div
                key={comp.competencia}
                style={{
                  backgroundColor: 'var(--white)',
                  borderRadius: 'var(--radius-md)',
                  padding: '1.35rem',
                  border: '1px solid var(--border-light)',
                  boxShadow: 'var(--shadow-sm)',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.65rem' }}>
                    <span
                      style={{
                        backgroundColor: 'var(--ocean-600)',
                        color: 'var(--white)',
                        fontWeight: 800,
                        fontSize: '0.8rem',
                        padding: '0.2rem 0.55rem',
                        borderRadius: 'var(--radius-sm)',
                      }}
                    >
                      C{comp.competencia}
                    </span>
                    {getDominioBadge(comp.nivel_dominio)}
                  </div>

                  <h5 style={{ fontSize: '1.05rem', fontWeight: 800, color: 'var(--text-primary)', marginBottom: '0.35rem' }}>
                    {comp.titulo}
                  </h5>

                  <p style={{ fontSize: '0.825rem', color: 'var(--text-muted)', lineHeight: 1.45, marginBottom: '1rem' }}>
                    {comp.descricao}
                  </p>
                </div>

                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', fontWeight: 700, marginBottom: '0.35rem' }}>
                    <span style={{ color: 'var(--text-secondary)' }}>
                      {comp.total_acertos} / {comp.total_questoes} acertos
                    </span>
                    <span style={{ color: getDominioColor(comp.nivel_dominio) }}>
                      {comp.total_questoes > 0 ? `${pct}%` : 'Sem dados'}
                    </span>
                  </div>

                  <div
                    style={{
                      width: '100%',
                      height: '7px',
                      backgroundColor: 'var(--ocean-100)',
                      borderRadius: '4px',
                      overflow: 'hidden',
                    }}
                  >
                    <div
                      style={{
                        width: `${comp.total_questoes > 0 ? pct : 0}%`,
                        height: '100%',
                        backgroundColor: getDominioColor(comp.nivel_dominio),
                        transition: 'width 0.4s ease',
                      }}
                    />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* Matriz das 30 Habilidades com Filtros de Nível */}
      <section style={{ marginBottom: '3rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <h3 style={{ fontSize: '1.45rem', fontWeight: 800, color: 'var(--ocean-950)' }}>
              Matriz de Habilidades (H01–H30)
            </h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.925rem' }}>
              Identifique pontualmente quais habilidades precisam de reforço teórico imediato
            </p>
          </div>

          {/* Filtros de Habilidades */}
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            <button
              onClick={() => setHabilidadeFilter('todas')}
              className={`btn btn-sm ${habilidadeFilter === 'todas' ? 'btn-primary' : 'btn-outline'}`}
            >
              Todas (30)
            </button>
            <button
              onClick={() => setHabilidadeFilter('critico')}
              className={`btn btn-sm ${habilidadeFilter === 'critico' ? 'btn-primary' : 'btn-outline'}`}
            >
              Críticas ({dashboardData?.total_habilidades_criticas ?? 0})
            </button>
            <button
              onClick={() => setHabilidadeFilter('em_desenvolvimento')}
              className={`btn btn-sm ${habilidadeFilter === 'em_desenvolvimento' ? 'btn-primary' : 'btn-outline'}`}
            >
              Em Treino ({dashboardData?.total_habilidades_em_desenvolvimento ?? 0})
            </button>
            <button
              onClick={() => setHabilidadeFilter('consolidado')}
              className={`btn btn-sm ${habilidadeFilter === 'consolidado' ? 'btn-primary' : 'btn-outline'}`}
            >
              Consolidadas ({dashboardData?.total_habilidades_consolidadas ?? 0})
            </button>
          </div>
        </div>

        {/* Grade de Habilidades */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
            gap: '1rem',
          }}
        >
          {habilidadesFiltradas.map((hab) => {
            const pct = Math.round(hab.taxa_acerto * 100);
            return (
              <div
                key={hab.habilidade_codigo}
                className="card"
                style={{
                  padding: '1.25rem',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  gap: '0.85rem',
                  borderLeft: `4px solid ${getDominioColor(hab.nivel_dominio)}`,
                }}
              >
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <strong style={{ fontSize: '1.1rem', color: 'var(--ocean-950)' }}>
                        {hab.habilidade_codigo}
                      </strong>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                        (Comp. {hab.competencia})
                      </span>
                    </div>
                    {getDominioBadge(hab.nivel_dominio)}
                  </div>

                  <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.45, margin: 0 }}>
                    {hab.descricao}
                  </p>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: '0.5rem', borderTop: '1px solid var(--border-light)' }}>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                    {hab.total_questoes > 0 ? (
                      <>
                        <strong>{hab.total_acertos}</strong> de {hab.total_questoes} ({pct}%)
                      </>
                    ) : (
                      'Nenhum item respondido'
                    )}
                  </div>

                  <button
                    onClick={() => onNavigate('chat')}
                    className="btn btn-ghost btn-sm"
                    style={{ fontSize: '0.8rem', padding: '0.2rem 0.5rem', color: 'var(--ocean-700)', gap: '0.3rem' }}
                    title={`Estudar ${hab.habilidade_codigo} com a Tutora VERA`}
                  >
                    <BotMessageSquare size={14} />
                    <span>Estudar</span>
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* Histórico das Últimas Tentativas Concluídas */}
      {dashboardData && dashboardData.ultimas_tentativas.length > 0 && (
        <section style={{ marginBottom: '3rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
            <div>
              <h3 style={{ fontSize: '1.45rem', fontWeight: 800, color: 'var(--ocean-950)' }}>
                Seus Últimos Simulados
              </h3>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.925rem' }}>
                Revise suas provas anteriores e consulte as explicações das questões
              </p>
            </div>

            <button
              onClick={() => onNavigate('simulado')}
              className="btn btn-outline btn-sm"
              style={{ gap: '0.35rem', fontWeight: 700 }}
            >
              <RotateCcw size={16} />
              Ver Todos os Simulados
            </button>
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
              gap: '1.25rem',
            }}
          >
            {dashboardData.ultimas_tentativas.map((tent) => (
              <div
                key={tent.tentativa_id}
                className="card"
                style={{
                  padding: '1.35rem',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  borderTop: '4px solid var(--ocean-600)',
                }}
              >
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
                    <h5 style={{ fontSize: '1.05rem', fontWeight: 800, color: 'var(--ocean-950)', margin: 0 }}>
                      {tent.titulo}
                    </h5>
                    <span className="badge badge-success">Concluído</span>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
                    <Calendar size={14} />
                    <span>
                      {tent.completed_at
                        ? new Date(tent.completed_at).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' })
                        : 'Recente'}
                    </span>
                  </div>

                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-around',
                      backgroundColor: 'var(--ocean-50)',
                      padding: '0.85rem',
                      borderRadius: 'var(--radius-sm)',
                      marginBottom: '1rem',
                    }}
                  >
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: '1.35rem', fontWeight: 800, color: 'var(--ocean-900)' }}>
                        {tent.score_percentual}%
                      </div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Acertos</div>
                    </div>
                    <div style={{ width: '1px', height: '28px', backgroundColor: 'var(--border-ocean)' }} />
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: '1.35rem', fontWeight: 800, color: 'var(--ocean-900)' }}>
                        {tent.total_acertos} / {tent.total_itens}
                      </div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Questões</div>
                    </div>
                  </div>
                </div>

                <button
                  onClick={() => onNavigate('simulado')}
                  className="btn btn-outline"
                  style={{ width: '100%', fontWeight: 700, gap: '0.4rem' }}
                >
                  <FileCheck2 size={16} />
                  Revisar Caderno & Gabarito
                </button>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Dicas Táticas do Sistema */}
      <section
        style={{
          backgroundColor: 'var(--white)',
          borderRadius: 'var(--radius-lg)',
          border: '1px solid var(--border-light)',
          padding: '1.75rem 2rem',
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
          gap: '1.5rem',
        }}
      >
        <div style={{ display: 'flex', gap: '1rem' }}>
          <div
            style={{
              width: '42px',
              height: '42px',
              borderRadius: '10px',
              backgroundColor: 'var(--ocean-100)',
              color: 'var(--ocean-700)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
            }}
          >
            <Clock size={22} />
          </div>
          <div>
            <strong style={{ fontSize: '0.95rem', color: 'var(--text-primary)', display: 'block', marginBottom: '0.25rem' }}>
              Gestão de Tempo na Prova
            </strong>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', margin: 0, lineHeight: 1.5 }}>
              Com 45 itens e 2h30min dedicadas à Matemática, reserve em média 3 minutos por questão.
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '1rem' }}>
          <div
            style={{
              width: '42px',
              height: '42px',
              borderRadius: '10px',
              backgroundColor: 'var(--ocean-100)',
              color: 'var(--ocean-700)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
            }}
          >
            <Zap size={22} />
          </div>
          <div>
            <strong style={{ fontSize: '0.95rem', color: 'var(--text-primary)', display: 'block', marginBottom: '0.25rem' }}>
              Estratégia TRI (Coerência)
            </strong>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', margin: 0, lineHeight: 1.5 }}>
              Garanta primeiro as questões fáceis e médias para valorizar sua curva de pontuação na TRI.
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '1rem' }}>
          <div
            style={{
              width: '42px',
              height: '42px',
              borderRadius: '10px',
              backgroundColor: 'var(--ocean-100)',
              color: 'var(--ocean-700)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
            }}
          >
            <BookOpen size={22} />
          </div>
          <div>
            <strong style={{ fontSize: '0.95rem', color: 'var(--text-primary)', display: 'block', marginBottom: '0.25rem' }}>
              Ciclo de Feedback da Tutora
            </strong>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', margin: 0, lineHeight: 1.5 }}>
              Ao terminar o simulado, peça a explicação da Vera para cada questão errada e entenda o distrator.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
};
