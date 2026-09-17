import React from 'react';
import { useAuth } from '../context/AuthContext';
import {
  GraduationCap,
  LayoutDashboard,
  FileCheck2,
  BotMessageSquare,
  LogOut,
  X,
} from 'lucide-react';

interface SidebarProps {
  currentPage: string;
  onNavigate: (page: string) => void;
  isOpen: boolean;
  onClose: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentPage,
  onNavigate,
  isOpen,
  onClose,
}) => {
  const { user, logout } = useAuth();

  const handleItemClick = (page: string) => {
    onNavigate(page);
    onClose();
  };

  return (
    <>
      {/* Overlay escurecido para telas menores */}
      {isOpen && <div className="sidebar-overlay" onClick={onClose} />}

      <aside className={`workspace-sidebar ${isOpen ? 'open' : ''}`}>
        {/* Topo do Menu Lateral / Brand */}
        <div
          style={{
            padding: '1.25rem 1.25rem 1rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderBottom: '1px solid var(--border-light)',
          }}
        >
          <div
            onClick={() => handleItemClick('home')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.65rem',
              cursor: 'pointer',
              userSelect: 'none',
            }}
          >
            <div
              style={{
                width: '38px',
                height: '38px',
                borderRadius: '10px',
                backgroundColor: 'var(--ocean-600)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--white)',
                boxShadow: '0 3px 8px rgba(2, 132, 199, 0.3)',
                flexShrink: 0,
              }}
            >
              <GraduationCap size={22} strokeWidth={2.2} />
            </div>
            <div>
              <div
                style={{
                  fontSize: '1.25rem',
                  fontWeight: 800,
                  color: 'var(--ocean-900)',
                  letterSpacing: '-0.03em',
                  lineHeight: 1.1,
                }}
              >
                VERA
              </div>
              <div
                style={{
                  fontSize: '0.7rem',
                  fontWeight: 700,
                  color: 'var(--ocean-600)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                }}
              >
                Portal do Aluno
              </div>
            </div>
          </div>

          {/* Botão Fechar no Mobile */}
          <button
            onClick={onClose}
            style={{
              display: 'none',
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              color: 'var(--text-muted)',
              padding: '0.25rem',
            }}
            className="sidebar-close-btn"
            aria-label="Fechar menu"
          >
            <X size={20} />
          </button>
        </div>

        {/* Links de Navegação Principal */}
        <div style={{ flex: 1, padding: '1.25rem 0.85rem', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
          <div
            style={{
              fontSize: '0.725rem',
              fontWeight: 700,
              color: 'var(--text-muted)',
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
              padding: '0.25rem 0.75rem 0.5rem',
            }}
          >
            Menu Principal
          </div>

          <button
            onClick={() => handleItemClick('home')}
            className={`sidebar-nav-item ${currentPage === 'home' ? 'active' : ''}`}
          >
            <LayoutDashboard size={20} />
            <span>Painel do Estudante</span>
          </button>

          <button
            onClick={() => handleItemClick('simulado')}
            className={`sidebar-nav-item ${currentPage === 'simulado' ? 'active' : ''}`}
            style={{ justifyContent: 'space-between' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
              <FileCheck2 size={20} />
              <span>Simulado Geral</span>
            </div>
            <span
              style={{
                fontSize: '0.725rem',
                fontWeight: 700,
                padding: '0.15rem 0.45rem',
                borderRadius: 'var(--radius-full)',
                backgroundColor: currentPage === 'simulado' ? 'rgba(255,255,255,0.25)' : 'var(--ocean-100)',
                color: currentPage === 'simulado' ? 'var(--white)' : 'var(--ocean-800)',
              }}
            >
              45 Itens
            </span>
          </button>

          <button
            onClick={() => handleItemClick('chat')}
            className={`sidebar-nav-item ${currentPage === 'chat' ? 'active' : ''}`}
            style={{ justifyContent: 'space-between' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
              <BotMessageSquare size={20} />
              <span>Tutora VERA</span>
            </div>
            <span
              style={{
                fontSize: '0.725rem',
                fontWeight: 700,
                padding: '0.15rem 0.45rem',
                borderRadius: 'var(--radius-full)',
                backgroundColor: currentPage === 'chat' ? 'rgba(255,255,255,0.25)' : 'var(--color-success-bg)',
                color: currentPage === 'chat' ? 'var(--white)' : 'var(--color-success)',
              }}
            >
              Online
            </span>
          </button>
        </div>

        {/* Rodapé do Menu Lateral: Perfil do Estudante & Sair */}
        <div
          style={{
            padding: '1rem 1.1rem',
            borderTop: '1px solid var(--border-light)',
            backgroundColor: 'var(--surface-subtle)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '0.5rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', minWidth: 0 }}>
            <div
              style={{
                width: '36px',
                height: '36px',
                borderRadius: '50%',
                backgroundColor: 'var(--ocean-700)',
                color: 'var(--white)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '0.9rem',
                fontWeight: 700,
                flexShrink: 0,
              }}
            >
              {user?.nome ? user.nome.charAt(0).toUpperCase() : 'E'}
            </div>
            <div style={{ minWidth: 0 }}>
              <div
                style={{
                  fontSize: '0.875rem',
                  fontWeight: 700,
                  color: 'var(--text-primary)',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
                title={user?.nome}
              >
                {user?.nome || 'Estudante'}
              </div>
              <div
                style={{
                  fontSize: '0.725rem',
                  color: 'var(--text-muted)',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {user?.email || 'Aluno VERA'}
              </div>
            </div>
          </div>

          <button
            onClick={() => {
              logout();
              onNavigate('login');
            }}
            className="btn btn-ghost btn-sm"
            title="Sair do sistema"
            style={{
              padding: '0.45rem',
              color: 'var(--color-danger)',
              flexShrink: 0,
            }}
          >
            <LogOut size={18} />
          </button>
        </div>

        <style>{`
          @media (max-width: 900px) {
            .sidebar-close-btn {
              display: block !important;
            }
          }
        `}</style>
      </aside>
    </>
  );
};
