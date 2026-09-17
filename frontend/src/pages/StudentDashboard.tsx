import React from 'react';
import { useAuth } from '../context/AuthContext';
import {
  FileCheck2,
  BotMessageSquare,
  Sparkles,
  ArrowRight,
  Clock,
  Target,
  BookOpen,
  Zap,
} from 'lucide-react';

interface StudentDashboardProps {
  onNavigate: (page: string) => void;
}

export const StudentDashboard: React.FC<StudentDashboardProps> = ({ onNavigate }) => {
  const { user } = useAuth();
  const firstName = user?.nome ? user.nome.split(' ')[0] : 'Estudante';

  const competencias = [
    { id: 'C1', titulo: 'Números e Operações', habilidades: 'H01 a H05', desc: 'Conjuntos numéricos, operações básicas e notação científica.' },
    { id: 'C2', titulo: 'Geometria e Formas', habilidades: 'H06 a H09', desc: 'Propriedades de figuras planas e espaciais e vistas ortogonais.' },
    { id: 'C3', titulo: 'Grandezas e Medidas', habilidades: 'H10 a H14', desc: 'Cálculo de áreas, volumes, perímetros e conversão de unidades.' },
    { id: 'C4', titulo: 'Proporcionalidade', habilidades: 'H15 a H18', desc: 'Razões, proporções, regra de três e porcentagem aplicada.' },
    { id: 'C5', titulo: 'Funções e Gráficos', habilidades: 'H19 a H23', desc: 'Modelagem algébrica de 1º e 2º graus, exponenciais e trigonometria.' },
    { id: 'C6', titulo: 'Estatística e Gráficos', habilidades: 'H24 a H26', desc: 'Médias, medianas, modas e interpretação rigorosa de dados.' },
    { id: 'C7', titulo: 'Probabilidade e Contagem', habilidades: 'H27 a H30', desc: 'Análise combinatória, permutações e probabilidade condicional.' },
  ];

  return (
    <div style={{ padding: '2rem 2rem 4rem', maxWidth: '1280px', margin: '0 auto', width: '100%' }}>
      {/* Banner de Boas-Vindas do Estudante */}
      <section
        style={{
          background: 'linear-gradient(135deg, var(--ocean-900) 0%, var(--ocean-700) 100%)',
          borderRadius: 'var(--radius-lg)',
          padding: '2.5rem',
          color: 'var(--white)',
          marginBottom: '2.5rem',
          boxShadow: 'var(--shadow-ocean)',
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        <div style={{ maxWidth: '760px', position: 'relative', zIndex: 2 }}>
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
            Centro de Estudos ENEM Matemática
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
            Olá, {firstName}! Pronto para treinar hoje?
          </h2>

          <p
            style={{
              fontSize: '1.05rem',
              color: 'var(--ocean-100)',
              lineHeight: 1.6,
              marginBottom: '1.75rem',
              maxWidth: '640px',
            }}
          >
            Seu ambiente integrado para simulações completas de <strong>45 itens</strong>,
            diagnósticos da Matriz de Referência e tutoria pedagógica interativa com IA local.
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
              <span>Simulado Padrão: 45 Itens (2h30min)</span>
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

      {/* Hub de Ações Rápidas (Bento Grid) */}
      <section style={{ marginBottom: '3rem' }}>
        <div style={{ marginBottom: '1.25rem' }}>
          <h3 style={{ fontSize: '1.45rem', fontWeight: 800, color: 'var(--ocean-950)' }}>
            Ações Rápidas de Estudo
          </h3>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.925rem' }}>
            Escolha sua meta agora: teste cronometrado de prova ou tutoria interativa
          </p>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
            gap: '1.75rem',
          }}
        >
          {/* Card 1: Simulado Geral de Matemática */}
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

              <h4 style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--text-primary)', marginBottom: '0.75rem' }}>
                Simulado Geral de Matemática
              </h4>

              <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem', lineHeight: 1.6, marginBottom: '1.5rem' }}>
                Realize um teste completo no modelo do segundo dia do ENEM. Acompanhe o tempo pelo cronômetro integrado,
                navegue pela grade de 45 questões e receba o gabarito oficial com análise de acertos.
              </p>
            </div>

            <button
              onClick={() => onNavigate('simulado')}
              className="btn btn-primary btn-lg"
              style={{ width: '100%', justifyContent: 'space-between' }}
            >
              <span style={{ fontWeight: 700 }}>Iniciar Simulado Agora</span>
              <ArrowRight size={20} />
            </button>
          </div>

          {/* Card 2: Tutora Inteligente VERA */}
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

              <h4 style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--text-primary)', marginBottom: '0.75rem' }}>
                Tutora VERA (IA Especialista)
              </h4>

              <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem', lineHeight: 1.6, marginBottom: '1.5rem' }}>
                Converse com a tutora inteligente treinada para explicar erros, apresentar resoluções guiadas em fórmulas
                matemáticas (LaTeX) e sugerir estratégias práticas para o ENEM.
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

      {/* Matriz de Referência do ENEM: 7 Competências de Área */}
      <section style={{ marginBottom: '3rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '0.5rem' }}>
          <div>
            <h3 style={{ fontSize: '1.45rem', fontWeight: 800, color: 'var(--ocean-950)' }}>
              Matriz de Referência Oficial (INEP)
            </h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.925rem' }}>
              Todas as 45 questões do seu simulado cobrem as 7 Competências de Área da Matemática
            </p>
          </div>
          <span className="badge badge-ocean" style={{ fontSize: '0.85rem', padding: '0.35rem 0.85rem' }}>
            H01 a H30 Mapeadas
          </span>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
            gap: '1.25rem',
          }}
        >
          {competencias.map((comp) => (
            <div
              key={comp.id}
              style={{
                backgroundColor: 'var(--white)',
                borderRadius: 'var(--radius-md)',
                padding: '1.25rem',
                border: '1px solid var(--border-light)',
                boxShadow: 'var(--shadow-sm)',
              }}
            >
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
                  {comp.id}
                </span>
                <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--ocean-700)' }}>
                  {comp.habilidades}
                </span>
              </div>
              <h5 style={{ fontSize: '1rem', fontWeight: 800, color: 'var(--text-primary)', marginBottom: '0.35rem' }}>
                {comp.titulo}
              </h5>
              <p style={{ fontSize: '0.825rem', color: 'var(--text-muted)', lineHeight: 1.45, margin: 0 }}>
                {comp.desc}
              </p>
            </div>
          ))}
        </div>
      </section>

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
              Resolva primeiro as questões conceituais e fáceis para garantir coerência pedagógica no cálculo da nota.
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
              Ciclo de Melhoria com a Tutora
            </strong>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', margin: 0, lineHeight: 1.5 }}>
              Após o simulado, consulte a Tutora VERA para obter a resolução guiada dos itens em que houve dúvida.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
};
