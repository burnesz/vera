import React from 'react';
import { useAuth } from '../context/AuthContext';
import {
  FileCheck2,
  BotMessageSquare,
  Sparkles,
  ArrowRight,
  GraduationCap,
  Clock,
  Award,
  Layers,
} from 'lucide-react';

interface HomePageProps {
  onNavigate: (page: string) => void;
}

export const HomePage: React.FC<HomePageProps> = ({ onNavigate }) => {
  const { user, isAuthenticated } = useAuth();

  return (
    <div className="container" style={{ padding: '2.5rem 1.25rem 4rem' }}>
      {/* Hero Section */}
      <section
        style={{
          background: 'linear-gradient(135deg, var(--ocean-900) 0%, var(--ocean-700) 100%)',
          borderRadius: 'var(--radius-lg)',
          padding: '3rem 2.5rem',
          color: 'var(--white)',
          marginBottom: '3rem',
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
              marginBottom: '1.25rem',
              backdropFilter: 'blur(4px)',
            }}
          >
            <Sparkles size={16} />
            Plataforma RAG para Matemática no ENEM
          </div>

          <h1
            style={{
              fontSize: 'clamp(2rem, 4vw, 2.75rem)',
              fontWeight: 800,
              color: 'var(--white)',
              lineHeight: 1.15,
              marginBottom: '1rem',
            }}
          >
            {isAuthenticated && user
              ? `Olá, ${user.nome.split(' ')[0]}! Pronto para treinar?`
              : 'Domine a Matemática do ENEM com Inteligência Pedagógica'}
          </h1>

          <p
            style={{
              fontSize: '1.1rem',
              color: 'var(--ocean-100)',
              lineHeight: 1.6,
              marginBottom: '2rem',
              maxWidth: '680px',
            }}
          >
            Simulados com o caderno completo de <strong>45 questões</strong>, diagnósticos detalhados por habilidade da Matriz de Referência e tutoria interativa com Chain-of-Thought.
          </p>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem' }}>
            <button
              onClick={() => onNavigate('simulado')}
              className="btn btn-lg"
              style={{
                backgroundColor: 'var(--white)',
                color: 'var(--ocean-900)',
                fontWeight: 700,
                boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
              }}
            >
              <FileCheck2 size={20} />
              Iniciar Simulado Geral (45 Itens)
            </button>

            <button
              onClick={() => onNavigate('chat')}
              className="btn btn-lg btn-outline"
              style={{
                backgroundColor: 'transparent',
                borderColor: 'var(--white)',
                color: 'var(--white)',
                fontWeight: 600,
              }}
            >
              <BotMessageSquare size={20} />
              Tirar Dúvidas com a Tutora VERA
            </button>
          </div>
        </div>

        {/* Efeito decorativo sutil de fundo */}
        <div
          style={{
            position: 'absolute',
            right: '-40px',
            bottom: '-40px',
            opacity: 0.08,
            pointerEvents: 'none',
          }}
        >
          <GraduationCap size={360} />
        </div>
      </section>

      {/* Seção de Módulos Principais */}
      <section style={{ marginBottom: '3.5rem' }}>
        <div style={{ marginBottom: '1.75rem' }}>
          <h2 style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--ocean-950)' }}>
            Recursos Principais da Plataforma
          </h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem' }}>
            Treine em condições reais de prova e receba orientações didáticas passo a passo
          </p>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
            gap: '1.75rem',
          }}
        >
          {/* Card 1: Simulado Geral */}
          <div
            className="card"
            style={{
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              borderTop: '4px solid var(--ocean-600)',
            }}
          >
            <div>
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
                  marginBottom: '1.25rem',
                }}
              >
                <FileCheck2 size={26} />
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                <span className="badge badge-ocean">Caderno Oficial</span>
                <span className="badge badge-dark">45 Questões</span>
              </div>
              <h3 style={{ fontSize: '1.35rem', fontWeight: 800, color: 'var(--text-primary)', marginBottom: '0.75rem' }}>
                Simulado Geral de Matemática
              </h3>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.925rem', lineHeight: 1.6, marginBottom: '1.25rem' }}>
                Realize um teste completo no modelo do segundo dia do ENEM. Acompanhe o tempo pelo cronômetro integrado, navegue pela grade de 45 questões e receba o gabarito detalhado.
              </p>
            </div>

            <button
              onClick={() => onNavigate('simulado')}
              className="btn btn-primary"
              style={{ width: '100%', justifyContent: 'space-between' }}
            >
              <span>Começar Prova</span>
              <ArrowRight size={18} />
            </button>
          </div>

          {/* Card 2: Chatbot Especialista */}
          <div
            className="card"
            style={{
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              borderTop: '4px solid var(--ocean-500)',
            }}
          >
            <div>
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
                  marginBottom: '1.25rem',
                }}
              >
                <BotMessageSquare size={26} />
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                <span className="badge badge-ocean">RAG + CoT</span>
                <span className="badge badge-success">Online</span>
              </div>
              <h3 style={{ fontSize: '1.35rem', fontWeight: 800, color: 'var(--text-primary)', marginBottom: '0.75rem' }}>
                Tutora VERA (IA Especialista)
              </h3>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.925rem', lineHeight: 1.6, marginBottom: '1.25rem' }}>
                Converse com a tutora inteligente treinada para explicar erros, apresentar resoluções guiadas em fórmulas matemáticas e sugerir estratégias práticas para o ENEM.
              </p>
            </div>

            <button
              onClick={() => onNavigate('chat')}
              className="btn btn-outline"
              style={{ width: '100%', justifyContent: 'space-between' }}
            >
              <span>Abrir Conversa</span>
              <ArrowRight size={18} />
            </button>
          </div>

          {/* Card 3: Matriz de Referência */}
          <div
            className="card"
            style={{
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              borderTop: '4px solid var(--ocean-800)',
            }}
          >
            <div>
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
                  marginBottom: '1.25rem',
                }}
              >
                <Layers size={26} />
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                <span className="badge badge-ocean">INEP / ENEM</span>
                <span className="badge badge-dark">H01 – H30</span>
              </div>
              <h3 style={{ fontSize: '1.35rem', fontWeight: 800, color: 'var(--text-primary)', marginBottom: '0.75rem' }}>
                Matriz de Referência Oficial
              </h3>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.925rem', lineHeight: 1.6, marginBottom: '1.25rem' }}>
                Todas as questões e feedbacks pedagógicos da plataforma são rigorosamente ancorados nas 7 Competências de Área e 30 Habilidades oficiais de Matemática do INEP.
              </p>
            </div>

            <div
              style={{
                backgroundColor: 'var(--ocean-50)',
                borderRadius: 'var(--radius-md)',
                padding: '0.75rem 1rem',
                fontSize: '0.85rem',
                color: 'var(--ocean-900)',
                fontWeight: 600,
                textAlign: 'center',
              }}
            >
              30 Habilidades Cadastradas no Sistema
            </div>
          </div>
        </div>
      </section>

      {/* Destaques Técnicos do Projeto (TCC) */}
      <section
        style={{
          backgroundColor: 'var(--white)',
          borderRadius: 'var(--radius-lg)',
          border: '1px solid var(--border-light)',
          padding: '2rem 2.5rem',
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: '2rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div
            style={{
              padding: '0.85rem',
              backgroundColor: 'var(--ocean-100)',
              borderRadius: 'var(--radius-md)',
              color: 'var(--ocean-700)',
            }}
          >
            <Clock size={28} />
          </div>
          <div>
            <div style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--text-primary)' }}>45 Itens</div>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', fontWeight: 500 }}>
              Padrão Prova Oficial
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div
            style={{
              padding: '0.85rem',
              backgroundColor: 'var(--ocean-100)',
              borderRadius: 'var(--radius-md)',
              color: 'var(--ocean-700)',
            }}
          >
            <Layers size={28} />
          </div>
          <div>
            <div style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--text-primary)' }}>30 Habilidades</div>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', fontWeight: 500 }}>
              Cobertura Integral (H01–H30)
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div
            style={{
              padding: '0.85rem',
              backgroundColor: 'var(--ocean-100)',
              borderRadius: 'var(--radius-md)',
              color: 'var(--ocean-700)',
            }}
          >
            <Award size={28} />
          </div>
          <div>
            <div style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--text-primary)' }}>100% Gratuito</div>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', fontWeight: 500 }}>
              Inferência Local e Ética
            </div>
          </div>
        </div>
      </section>
    </div>
  );
};
