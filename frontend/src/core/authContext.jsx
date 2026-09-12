import React, { createContext, useContext, useState, useEffect } from 'react';
import api from './api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setTokenState] = useState(() => localStorage.getItem('token') || '');
  const [user, setUser] = useState(() => {
    try {
      const saved = localStorage.getItem('user');
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);

  // Auto-authenticate on boot: fetch real token for 'admin' if empty, verify /api/auth/me/
  useEffect(() => {
    async function initAuth() {
      setLoading(true);

      // If the user explicitly logged out, honor the choice and prompt for login
      if (sessionStorage.getItem('is_logged_out') === 'true') {
        setTokenState('');
        setUser(null);
        setIsAuthenticated(false);
        setLoading(false);
        return;
      }

      let activeToken = localStorage.getItem('token');
      if (activeToken === 'dev-token') {
        localStorage.removeItem('token');
        activeToken = null;
      }

      const fetchAdminToken = async () => {
        try {
          const authRes = await fetch('/api/token-auth/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: 'admin' }),
          });
          if (authRes.ok) {
            const data = await authRes.json();
            const newToken = data.token;
            localStorage.setItem('token', newToken);
            setTokenState(newToken);
            api.setToken(newToken);
            if (data.user) {
              setUser(data.user);
              localStorage.setItem('user', JSON.stringify(data.user));
              setIsAuthenticated(true);
            }
            return newToken;
          }
        } catch (err) {
          console.warn('[Auth] Failed auto-login for admin:', err);
        }
        return null;
      };

      // Auto-authenticate admin in local dev if no token exists
      if (!activeToken) {
        activeToken = await fetchAdminToken();
      }

      // Verify token with /api/auth/me/
      if (activeToken) {
        api.setToken(activeToken);
        setTokenState(activeToken);
        try {
          const meData = await api.get('/api/auth/me/');
          setUser(meData);
          localStorage.setItem('user', JSON.stringify(meData));
          setIsAuthenticated(true);
          if (meData.active_workspace) {
            api.setWorkspace(meData.active_workspace);
          }
        } catch (err) {
          console.warn('[Auth] /api/auth/me/ verification failed, attempting token refresh:', err);
          const freshToken = await fetchAdminToken();
          if (freshToken) {
            try {
              const retryMe = await api.get('/api/auth/me/');
              setUser(retryMe);
              localStorage.setItem('user', JSON.stringify(retryMe));
              setIsAuthenticated(true);
              if (retryMe.active_workspace) {
                api.setWorkspace(retryMe.active_workspace);
              }
            } catch (retryErr) {
              console.error('[Auth] Token refresh retry failed:', retryErr);
            }
          }
        }
      }
      setLoading(false);
    }
    initAuth();
  }, []);

  const login = async (username, password) => {
    setLoading(true);
    try {
      const data = await api.post('/api/token-auth/', { username, password });
      const authToken = data?.token;
      if (authToken) {
        sessionStorage.removeItem('is_logged_out');
        localStorage.setItem('token', authToken);
        setTokenState(authToken);
        api.setToken(authToken);
        if (data.user) {
          setUser(data.user);
          localStorage.setItem('user', JSON.stringify(data.user));
          if (data.user.active_workspace) {
            api.setWorkspace(data.user.active_workspace);
          }
        }
        setIsAuthenticated(true);
        return { success: true };
      }
      return { success: false, error: 'No token received from backend' };
    } catch (err) {
      console.error('[Auth Error]:', err);
      return { success: false, error: err.message || 'Invalid username or password' };
    } finally {
      setLoading(false);
    }
  };

  const logout = () => {
    sessionStorage.setItem('is_logged_out', 'true');
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    localStorage.removeItem('active_workspace');
    setTokenState('');
    setUser(null);
    setIsAuthenticated(false);
    api.setToken('');
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
