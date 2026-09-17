import React from 'react';
import { Menu, Sparkles, ShieldCheck } from 'lucide-react';

interface TopbarProps {
  currentPage: string;
  onOpenSidebar: () => void;
}

export const Topbar: React.FC<TopbarProps> = ({ currentPage, onOpenSidebar }) => {
  const getPageInfo = () => {
    switch (currentPage) {
      case 'simulado':
        return {
          title: 'Simulado Geral de Matemática',
          category: 'Caderno de Prova',
          badge: '45 Itens',
        };
      case 'chat':
        return {
          title: 'Tutora VERA (IA Especialista)',
          category: 'Tutoria Inteligente',
          badge: 'RAG + CoT',
        };
      case 'home':
      default:
        return {
          title: 'Painel do Estudante',
          category: 'Ambiente de Estudos',
          badge: 'ENEM 2026',
        };
    }
  };

  const info = getPageInfo();

  return (
    <header className="workspace-topbar">
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
        {/* Botão Hamburger para Mobile */}
        <button
          onClick={onOpenSidebar}
          className="btn btn-ghost"
          style={{ padding: '0.45rem', display: 'inline-flex' }}
          aria-label="Abrir menu lateral"
        >
          <Menu size={22} />
        </button>

        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span
              style={{
                fontSize: '0.75rem',
                fontWeight: 700,
                color: 'var(--ocean-600)',
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
              }}
            >
              {info.category}
            </span>
            <span style={{ color: 'var(--border-medium)', fontSize: '0.8rem' }}>/</span>
            <span
              style={{
                fontSize: '0.75rem',
                fontWeight: 600,
                color: 'var(--text-muted)',
              }}
            >
              {info.badge}
            </span>
          </div>
          <h1
            style={{
              fontSize: '1.25rem',
              fontWeight: 800,
              color: 'var(--text-primary)',
              lineHeight: 1.2,
              margin: 0,
            }}
          >
            {info.title}
          </h1>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.45rem',
            padding: '0.35rem 0.75rem',
            backgroundColor: 'var(--ocean-50)',
            borderRadius: 'var(--radius-full)',
            border: '1px solid var(--border-ocean)',
            fontSize: '0.8rem',
            fontWeight: 600,
            color: 'var(--ocean-800)',
          }}
          className="desktop-status-pill"
        >
          <ShieldCheck size={16} color="var(--color-success)" />
          <span>Matriz do ENEM (H01–H30)</span>
        </div>

        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.4rem',
            padding: '0.35rem 0.65rem',
            backgroundColor: 'var(--color-success-bg)',
            borderRadius: 'var(--radius-full)',
            fontSize: '0.775rem',
            fontWeight: 700,
            color: 'var(--color-success)',
          }}
        >
          <Sparkles size={14} />
          <span>IA Online</span>
        </div>
      </div>

      <style>{`
        @media (min-width: 901px) {
          .workspace-topbar button[aria-label="Abrir menu lateral"] {
            display: none !important;
          }
        }
        @media (max-width: 600px) {
          .desktop-status-pill {
            display: none !important;
          }
        }
      `}</style>
    </header>
  );
};
