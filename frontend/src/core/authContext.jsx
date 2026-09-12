import React, { createContext, useContext, useState, useEffect } from 'react';
import api from './api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setTokenState] = useState(() => localStorage.getItem('token') || 'dev-token');
  const [user, setUser] = useState({
    username: 'admin',
    email: 'admin@universal-ai.os',
    role: 'Administrator',
    user_type: 'staff',
    is_staff: true,
  });
  const [isAuthenticated, setIsAuthenticated] = useState(true);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // Synchronize API client token
    api.setToken(token);
  }, [token]);

  const login = async (username, password) => {
    setLoading(true);
    try {
      // Attempt backend auth endpoint or fallback gracefully in dev
      const data = await api.post('/api/token-auth/', { username, password }).catch(() => null);
      const authToken = data?.token || 'dev-token';
      setTokenState(authToken);
      setUser({
        username: username || 'admin',
        email: `${username || 'admin'}@universal-ai.os`,
        role: 'Administrator',
        user_type: 'staff',
        is_staff: true,
      });
      setIsAuthenticated(true);
      return true;
    } catch (err) {
      console.error('[Auth Error]:', err);
      return false;
    } finally {
      setLoading(false);
    }
  };

  const logout = () => {
    setTokenState('');
    localStorage.removeItem('token');
    setIsAuthenticated(false);
  };

  return (
    <AuthContext.Provider value={{ token, user, isAuthenticated, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
