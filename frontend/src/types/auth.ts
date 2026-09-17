export interface User {
  id: string;
  nome: string;
  email: string;
  role: 'student' | 'specialist' | 'admin';
  is_ativo: boolean;
  created_at?: string;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface RegisterCredentials {
  nome: string;
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}
