import api from './api';
import { LoginResponse, User, UserCreate } from '../types/auth';

export const authService = {
  async login(email: string, password: string): Promise<LoginResponse> {
    // OAuth2PasswordRequestForm expects form-encoded data, not JSON
    const formData = new URLSearchParams();
    formData.append('username', email);
    formData.append('password', password);

    const response = await api.post<LoginResponse>('/auth/login', formData, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded'
      }
    });
    return response.data;
  },

  async getCurrentUser(token: string): Promise<User> {
    const response = await api.get<User>('/auth/me', {
      headers: {
        Authorization: `Bearer ${token}`
      }
    });
    return response.data;
  },

  async register(userData: UserCreate): Promise<User> {
    const response = await api.post<User>('/auth/register', userData);
    return response.data;
  },

  saveToken(token: string): void {
    localStorage.setItem('auth_token', token);
  },

  getToken(): string | null {
    return localStorage.getItem('auth_token');
  },

  removeToken(): void {
    localStorage.removeItem('auth_token');
  }
};
