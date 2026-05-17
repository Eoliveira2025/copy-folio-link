import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || '/api/v1';

const getAuthHeader = () => {
  const token = localStorage.getItem('token');
  return token ? { Authorization: `Bearer ${token}` } : {};
};

export const metaapiV3Api = {
  // Cliente
  getMyAccount: async () => {
    const response = await axios.get(`${API_URL}/metaapi/me/account`, {
      headers: getAuthHeader(),
    });
    return response.data;
  },

  getMySubscription: async () => {
    const response = await axios.get(`${API_URL}/metaapi/me/subscription`, {
      headers: getAuthHeader(),
    });
    return response.data;
  },

  getAllowedStrategies: async () => {
    const response = await axios.get(`${API_URL}/metaapi/me/allowed-strategies`, {
      headers: getAuthHeader(),
    });
    return response.data;
  },

  importAccount: async (login: string) => {
    const response = await axios.post(
      `${API_URL}/metaapi/me/import-existing`,
      { login },
      { headers: getAuthHeader() }
    );
    return response.data;
  },

  // Admin
  markProvisioned: async (data: {
    user_id: string;
    login: string;
    strategy_code: string;
    copyfactory_subscription_id?: string;
  }) => {
    const response = await axios.post(
      `${API_URL}/metaapi/admin/mark-provisioned`,
      data,
      { headers: getAuthHeader() }
    );
    return response.data;
  },

  // Monitoramento Admin
  getHealth: async () => {
    const response = await axios.get(`${API_URL}/metaapi/admin/health`, {
      headers: getAuthHeader(),
    });
    return response.data;
  },

  getMonitorEvents: async (severity?: string) => {
    const response = await axios.get(`${API_URL}/metaapi/admin/events${severity ? `?severity=${severity}` : ''}`, {
      headers: getAuthHeader(),
    });
    return response.data;
  },

  triggerMonitorScan: async () => {
    const response = await axios.post(`${API_URL}/metaapi/admin/monitor/scan`, {}, {
      headers: getAuthHeader(),
    });
    return response.data;
  },
};
