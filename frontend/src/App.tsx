import React, { useState, useEffect } from 'react';
import { AuthProvider } from './context/AuthContext';
import { Navbar } from './components/Navbar';
import { Footer } from './components/Footer';
import { HomePage } from './pages/HomePage';
import { SimuladoPage } from './pages/SimuladoPage';
import { ChatPage } from './pages/ChatPage';
import { LoginPage } from './pages/LoginPage';
import { RegisterPage } from './pages/RegisterPage';

export const App: React.FC = () => {
  // Roteador leve sincronizado com a URL (pathname)
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

  return (
    <AuthProvider>
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
    </AuthProvider>
  );
};

export default App;
