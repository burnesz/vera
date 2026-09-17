import { apiFetch } from './api';
import type { User, LoginCredentials, RegisterCredentials, TokenResponse } from '../types/auth';

const TOKEN_KEY = 'vera_token';
const USER_KEY = 'vera_user';

export const authService = {
  async register(credentials: RegisterCredentials): Promise<User> {
    return await apiFetch<User>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(credentials),
    });
  },

  async login(credentials: LoginCredentials): Promise<{ token: string; user: User }> {
    const tokenRes = await apiFetch<TokenResponse>('/auth/login/json', {
      method: 'POST',
      body: JSON.stringify(credentials),
    });

    localStorage.setItem(TOKEN_KEY, tokenRes.access_token);

    // Busca o perfil completo do usuário autenticado
    const user = await this.getMe();
    localStorage.setItem(USER_KEY, JSON.stringify(user));

    return { token: tokenRes.access_token, user };
  },

  async getMe(): Promise<User> {
    return await apiFetch<User>('/auth/me');
  },

  getToken(): string | null {
    return localStorage.getItem(TOKEN_KEY);
  },

  getStoredUser(): User | null {
    const raw = localStorage.getItem(USER_KEY);
    if (!raw) return null;
    try {
      return JSON.parse(raw);
    } catch {
      return null;
    }
  },

  logout(): void {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  },

  isAuthenticated(): boolean {
    return !!localStorage.getItem(TOKEN_KEY);
  },
};
