import React, { createContext, useContext, useState, useEffect } from 'react';
import type { User, LoginCredentials, RegisterCredentials } from '../types/auth';
import { authService } from '../services/authService';

interface AuthContextType {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (credentials: LoginCredentials) => Promise<void>;
  register: (credentials: RegisterCredentials) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    async function loadUser() {
      const storedToken = authService.getToken();
      if (storedToken) {
        setToken(storedToken);
        try {
          const profile = await authService.getMe();
          setUser(profile);
        } catch {
          // Se o token estiver expirado ou backend inacessível, tenta manter dados em cache
          const cachedUser = authService.getStoredUser();
          if (cachedUser) {
            setUser(cachedUser);
          } else {
            // Em caso de falha de autenticação real, desloga
            authService.logout();
            setToken(null);
            setUser(null);
          }
        }
      }
      setIsLoading(false);
    }

    loadUser();
  }, []);

  const login = async (credentials: LoginCredentials) => {
    setIsLoading(true);
    try {
      const result = await authService.login(credentials);
      setToken(result.token);
      setUser(result.user);
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (credentials: RegisterCredentials) => {
    setIsLoading(true);
    try {
      await authService.register(credentials);
      // Efetua login automático após registro bem-sucedido
      await login({ email: credentials.email, password: credentials.password });
    } finally {
      setIsLoading(false);
    }
  };

  const logout = () => {
    authService.logout();
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!token,
        isLoading,
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth deve ser utilizado dentro de um AuthProvider');
  }
  return context;
};
