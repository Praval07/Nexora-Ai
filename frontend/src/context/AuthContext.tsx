import React, { createContext, useContext, useState, useEffect } from 'react';
import axios from 'axios';

interface UserProfile {
  id: string;
  tenant_id: string;
  email: string;
  first_name: string;
  last_name: string;
  roles: string[];
  status: string;
}

interface AuthContextType {
  user: UserProfile | null;
  token: string | null;
  tenantId: string | null;
  login: (token: string, refreshToken: string, user: UserProfile) => void;
  logout: () => void;
  loading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Axios instance shared across the app
export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:5000/api/v1',
});

// Parse JWT token claims without libraries
const parseJwt = (token: string) => {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
      window
        .atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    return JSON.parse(jsonPayload);
  } catch (e) {
    return null;
  }
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const storedToken = localStorage.getItem('token');
    const storedUser = localStorage.getItem('user');
    
    if (storedToken && storedUser) {
      const claims = parseJwt(storedToken);
      if (claims && claims.exp * 1000 > Date.now()) {
        setToken(storedToken);
        setTenantId(claims.tenant_id);
        setUser(JSON.parse(storedUser));
      } else {
        localStorage.removeItem('token');
        localStorage.removeItem('user');
      }
    }
    setLoading(false);
  }, []);

  // Interceptor to attach JWT and Tenant Headers
  useEffect(() => {
    const reqInterceptor = api.interceptors.request.use((config) => {
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      if (tenantId) {
        config.headers['X-Tenant-ID'] = tenantId;
      }
      return config;
    });

    return () => {
      api.interceptors.request.eject(reqInterceptor);
    };
  }, [token, tenantId]);

  const login = (accessToken: string, refreshToken: string, userProfile: UserProfile) => {
    const claims = parseJwt(accessToken);
    const resolvedTenant = claims?.tenant_id || userProfile.tenant_id;
    
    localStorage.setItem('token', accessToken);
    localStorage.setItem('refreshToken', refreshToken);
    localStorage.setItem('user', JSON.stringify(userProfile));

    setToken(accessToken);
    setTenantId(resolvedTenant);
    setUser(userProfile);
  };

  const logout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('refreshToken');
    localStorage.removeItem('user');
    setToken(null);
    setTenantId(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, token, tenantId, login, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
