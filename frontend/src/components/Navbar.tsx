import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import {
  GraduationCap,
  FileCheck2,
  BotMessageSquare,
  LogOut,
  LogIn,
  UserPlus,
  Menu,
  X,
  Lock,
} from 'lucide-react';

interface NavbarProps {
  currentPage: string;
  onNavigate: (page: string) => void;
}

export const Navbar: React.FC<NavbarProps> = ({ currentPage, onNavigate }) => {
  const { user, isAuthenticated, logout } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const handleNav = (page: string) => {
    onNavigate(page);
    setMobileMenuOpen(false);
  };

  return (
    <header
      style={{
        backgroundColor: 'var(--white)',
        borderBottom: '2px solid var(--ocean-100)',
        boxShadow: 'var(--shadow-sm)',
        position: 'sticky',
        top: 0,
        zIndex: 1000,
      }}
    >
      <div
        className="container"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          height: 'var(--header-height)',
        }}
      >
        {/* Brand / Logo */}
        <div
          onClick={() => handleNav('home')}
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
              width: '42px',
              height: '42px',
              borderRadius: '10px',
              backgroundColor: 'var(--ocean-600)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--white)',
              boxShadow: '0 4px 10px rgba(2, 132, 199, 0.3)',
            }}
          >
            <GraduationCap size={26} strokeWidth={2.2} />
          </div>
          <div>
            <div
              style={{
                fontSize: '1.45rem',
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
                fontSize: '0.725rem',
                fontWeight: 600,
                color: 'var(--ocean-600)',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
              }}
            >
              Matemática ENEM
            </div>
          </div>
        </div>

        {/* Desktop Navigation Links */}
        <nav
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.75rem',
          }}
          className="desktop-nav"
        >
          <button
            onClick={() => handleNav('home')}
            className={`btn ${currentPage === 'home' ? 'btn-primary' : 'btn-ghost'}`}
            style={{
              fontWeight: currentPage === 'home' ? 700 : 500,
              fontSize: '0.925rem',
            }}
          >
            Início
          </button>

          <button
            onClick={() => handleNav('simulado')}
            className={`btn ${currentPage === 'simulado' ? 'btn-primary' : 'btn-ghost'}`}
            style={{
              fontWeight: currentPage === 'simulado' ? 700 : 500,
              fontSize: '0.925rem',
            }}
          >
            <FileCheck2 size={18} />
            Simulado Geral (45)
            {!isAuthenticated && <Lock size={13} style={{ opacity: 0.6 }} />}
          </button>

          <button
            onClick={() => handleNav('chat')}
            className={`btn ${currentPage === 'chat' ? 'btn-primary' : 'btn-ghost'}`}
            style={{
              fontWeight: currentPage === 'chat' ? 700 : 500,
              fontSize: '0.925rem',
            }}
          >
            <BotMessageSquare size={18} />
            Tutora VERA
            {!isAuthenticated && <Lock size={13} style={{ opacity: 0.6 }} />}
          </button>
        </nav>

        {/* Auth Actions (Desktop) */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.75rem',
          }}
          className="desktop-nav"
        >
          {isAuthenticated && user ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  padding: '0.35rem 0.75rem',
                  backgroundColor: 'var(--ocean-50)',
                  border: '1px solid var(--border-ocean)',
                  borderRadius: 'var(--radius-full)',
                }}
              >
                <div
                  style={{
                    width: '28px',
                    height: '28px',
                    borderRadius: '50%',
                    backgroundColor: 'var(--ocean-600)',
                    color: 'var(--white)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '0.8rem',
                    fontWeight: 700,
                  }}
                >
                  {user.nome.charAt(0).toUpperCase()}
                </div>
                <div style={{ display: 'flex', flexDirection: 'column' }}>
                  <span style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                    {user.nome.split(' ')[0]}
                  </span>
                </div>
              </div>

              <button
                onClick={() => {
                  logout();
                  handleNav('login');
                }}
                className="btn btn-ghost btn-sm"
                title="Sair da conta"
                style={{ color: 'var(--color-danger)' }}
              >
                <LogOut size={16} />
                Sair
              </button>
            </div>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <button
                onClick={() => handleNav('login')}
                className={`btn btn-sm ${currentPage === 'login' ? 'btn-primary' : 'btn-outline'}`}
              >
                <LogIn size={16} />
                Entrar
              </button>
              <button
                onClick={() => handleNav('register')}
                className={`btn btn-sm ${currentPage === 'register' ? 'btn-primary' : 'btn-ghost'}`}
              >
                <UserPlus size={16} />
                Cadastrar
              </button>
            </div>
          )}
        </div>

        {/* Mobile Hamburger Button */}
        <button
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          className="btn btn-ghost mobile-toggle"
          aria-label="Alternar Menu"
          style={{ padding: '0.5rem' }}
        >
          {mobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
        </button>
      </div>

      {/* Mobile Drawer Menu */}
      {mobileMenuOpen && (
        <div
          style={{
            borderTop: '1px solid var(--border-ocean)',
            backgroundColor: 'var(--white)',
            padding: '1rem 1.25rem 1.5rem',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.75rem',
          }}
          className="mobile-menu"
        >
          <button
            onClick={() => handleNav('home')}
            className={`btn ${currentPage === 'home' ? 'btn-primary' : 'btn-ghost'}`}
            style={{ justifyContent: 'flex-start', width: '100%' }}
          >
            Início
          </button>
          <button
            onClick={() => handleNav('simulado')}
            className={`btn ${currentPage === 'simulado' ? 'btn-primary' : 'btn-ghost'}`}
            style={{ justifyContent: 'flex-start', width: '100%', gap: '0.65rem' }}
          >
            <FileCheck2 size={18} />
            <span>Simulado Geral (45 Questões)</span>
            {!isAuthenticated && <Lock size={14} style={{ marginLeft: 'auto', opacity: 0.6 }} />}
          </button>
          <button
            onClick={() => handleNav('chat')}
            className={`btn ${currentPage === 'chat' ? 'btn-primary' : 'btn-ghost'}`}
            style={{ justifyContent: 'flex-start', width: '100%', gap: '0.65rem' }}
          >
            <BotMessageSquare size={18} />
            <span>Tutora Especialista VERA</span>
            {!isAuthenticated && <Lock size={14} style={{ marginLeft: 'auto', opacity: 0.6 }} />}
          </button>

          <div style={{ height: '1px', backgroundColor: 'var(--border-light)', margin: '0.5rem 0' }} />

          {isAuthenticated && user ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              <div style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                Conectado como: <strong>{user.nome}</strong> ({user.email})
              </div>
              <button
                onClick={() => {
                  logout();
                  handleNav('login');
                }}
                className="btn btn-outline"
                style={{ color: 'var(--color-danger)', borderColor: 'var(--color-danger)' }}
              >
                <LogOut size={16} />
                Sair da Conta
              </button>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              <button
                onClick={() => handleNav('login')}
                className="btn btn-primary"
                style={{ width: '100%' }}
              >
                <LogIn size={18} />
                Entrar
              </button>
              <button
                onClick={() => handleNav('register')}
                className="btn btn-outline"
                style={{ width: '100%' }}
              >
                <UserPlus size={18} />
                Criar Nova Conta
              </button>
            </div>
          )}
        </div>
      )}

      {/* Media query styling inline for simplicity & responsiveness */}
      <style>{`
        @media (max-width: 768px) {
          .desktop-nav { display: none !important; }
          .mobile-toggle { display: inline-flex !important; }
        }
        @media (min-width: 769px) {
          .mobile-toggle { display: none !important; }
          .mobile-menu { display: none !important; }
        }
      `}</style>
    </header>
  );
};
