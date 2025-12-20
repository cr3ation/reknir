import api from './api';

export interface SystemInfo {
  needs_setup: boolean;
  version: string;
}

export const systemService = {
  async getSystemInfo(): Promise<SystemInfo> {
    const response = await api.get<SystemInfo>('/system/info');
    return response.data;
  },
};
