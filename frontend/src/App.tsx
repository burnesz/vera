import React, { useState, useEffect } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { Navbar } from './components/Navbar';
import { Footer } from './components/Footer';
import { Sidebar } from './components/Sidebar';
import { Topbar } from './components/Topbar';
import { HomePage } from './pages/HomePage';
import { SimuladoPage } from './pages/SimuladoPage';
import { ChatPage } from './pages/ChatPage';
import { LoginPage } from './pages/LoginPage';
import { RegisterPage } from './pages/RegisterPage';

const AppContent: React.FC = () => {
  const { isAuthenticated, isLoading } = useAuth();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Roteador sincronizado com a URL (pathname)
  const [currentPage, setCurrentPage] = useState<string>(() => {
    const path = window.location.pathname.replace(/^\//, '') || 'home';
    if (['home', 'simulado', 'chat', 'login', 'register'].includes(path)) {
      return path;
    }
    return 'home';
  });

  // Atualiza histórico do navegador quando a página muda
  const navigateTo = (page: string) => {
    setCurrentPage(page);
    const newPath = page === 'home' ? '/' : `/${page}`;
    window.history.pushState(null, '', newPath);
    window.scrollTo({ top: 0, behavior: 'smooth' });
    setSidebarOpen(false);
  };

  // Trata botão Voltar/Avançar do navegador
  useEffect(() => {
    const handlePopState = () => {
      const path = window.location.pathname.replace(/^\//, '') || 'home';
      if (['home', 'simulado', 'chat', 'login', 'register'].includes(path)) {
        setCurrentPage(path);
      } else {
        setCurrentPage('home');
      }
    };

    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  if (isLoading) {
    return (
      <div
        style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: 'var(--surface-subtle)',
          color: 'var(--ocean-800)',
          fontWeight: 600,
        }}
      >
        Carregando ambiente VERA...
      </div>
    );
  }

  // =========================================================================
  // CENÁRIO 1: Usuário Autenticado -> Layout Completo com Menu Lateral
  // =========================================================================
  if (isAuthenticated) {
    return (
      <div className="workspace-layout">
        <Sidebar
          currentPage={currentPage}
          onNavigate={navigateTo}
          isOpen={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
        />

        <div className="workspace-main">
          <Topbar
            currentPage={currentPage}
            onOpenSidebar={() => setSidebarOpen(true)}
          />

          <main style={{ flex: 1 }}>
            {currentPage === 'home' && <HomePage onNavigate={navigateTo} />}
            {currentPage === 'simulado' && <SimuladoPage onNavigate={navigateTo} />}
            {currentPage === 'chat' && <ChatPage onNavigate={navigateTo} />}
            {(currentPage === 'login' || currentPage === 'register') && (
              <HomePage onNavigate={navigateTo} />
            )}
          </main>

          <footer
            style={{
              padding: '1.25rem 2rem',
              textAlign: 'center',
              color: 'var(--text-muted)',
              fontSize: '0.8rem',
              borderTop: '1px solid var(--border-light)',
              backgroundColor: 'var(--white)',
            }}
          >
            VERA © 2026 — Plataforma RAG para Matemática no ENEM • Ambiente do Estudante
          </footer>
        </div>
      </div>
    );
  }

  // =========================================================================
  // CENÁRIO 2: Visitante Não Autenticado -> Landing Page Limpa e Header Público
  // =========================================================================
  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Navbar currentPage={currentPage} onNavigate={navigateTo} />

      <main style={{ flex: 1 }}>
        {currentPage === 'home' && <HomePage onNavigate={navigateTo} />}
        {currentPage === 'simulado' && <SimuladoPage onNavigate={navigateTo} />}
        {currentPage === 'chat' && <ChatPage onNavigate={navigateTo} />}
        {currentPage === 'login' && <LoginPage onNavigate={navigateTo} />}
        {currentPage === 'register' && <RegisterPage onNavigate={navigateTo} />}
      </main>

      <Footer />
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
};

export default App;
