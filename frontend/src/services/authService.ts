import axios from 'axios';
import { LoginResponse, User } from '../types/auth';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
const API_URL = `${API_BASE_URL}/auth`;

export const authService = {
  async login(email: string, password: string): Promise<LoginResponse> {
    // OAuth2PasswordRequestForm expects form-encoded data, not JSON
    const formData = new URLSearchParams();
    formData.append('username', email);
    formData.append('password', password);

    const response = await axios.post<LoginResponse>(`${API_URL}/login`, formData, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded'
      }
    });
    return response.data;
  },

  async getCurrentUser(token: string): Promise<User> {
    const response = await axios.get<User>(`${API_URL}/me`, {
      headers: {
        Authorization: `Bearer ${token}`
      }
    });
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
