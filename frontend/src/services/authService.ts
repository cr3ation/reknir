import axios from 'axios';
import { LoginRequest, LoginResponse, User } from '../types/auth';

const API_URL = 'http://localhost:8000/api/auth';

export const authService = {
  async login(email: string, password: string): Promise<LoginResponse> {
    const loginData: LoginRequest = {
      username: email, // API expects 'username' field
      password: password
    };

    const response = await axios.post<LoginResponse>(`${API_URL}/login`, loginData);
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
