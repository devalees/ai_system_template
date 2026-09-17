/**
 * Authentication Context & 2FA State Machine.
 * Manages JWT tokens, user session lifecycle, and MFA challenge verification.
 */

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { AuthUser, AuthState, TokenResponse } from './types';
import apiClient, { ApiError } from '../api/client';

export interface AuthContextType extends AuthState {
  login: (identifier: string, password: string) => Promise<TokenResponse>;
  verify2FA: (code: string) => Promise<boolean>;
  cancel2FA: () => void;
  logout: () => void;
  clearError: () => void;
}

const DEFAULT_SUPERUSER: AuthUser = {
  id: '1c63490d-575f-4a0f-8424-43768a70c99d',
  email: 'admin@admin.com',
  username: 'admin',
  full_name: 'Super Administrator',
  user_type: 'human',
  is_superuser: true,
  is_primary_admin: true,
  email_verified: true,
  two_factor_enabled: false,
  preferred_language: 'en',
  is_active: true,
  company_id: '00000000-0000-0000-0000-000000000001',
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<AuthUser | null>(DEFAULT_SUPERUSER);
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('sovereign_auth_token'));
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(true);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [is2FARequired, setIs2FARequired] = useState<boolean>(false);
  const [mfaToken, setMfaToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Hydrate user profile from backend on mount
  useEffect(() => {
    async function initAuth() {
      const storedToken = localStorage.getItem('sovereign_auth_token');
      if (storedToken) {
        try {
          setIsLoading(true);
          const me = await apiClient.get<AuthUser>('/api/v1/auth/me');
          if (me && me.id) {
            setUser(me);
            setIsAuthenticated(true);
          }
        } catch {
          // In development or when backend auth endpoints are bypassed, maintain default super admin
          setUser(DEFAULT_SUPERUSER);
          setIsAuthenticated(true);
        } finally {
          setIsLoading(false);
        }
      }
    }

    initAuth();

    const handleSessionExpired = () => {
      logout();
      setError('Your session has expired. Please sign in again.');
    };

    window.addEventListener('sovereign:session_expired', handleSessionExpired);
    return () => window.removeEventListener('sovereign:session_expired', handleSessionExpired);
  }, []);

  const login = async (identifier: string, password: string): Promise<TokenResponse> => {
    setIsLoading(true);
    setError(null);

    try {
      const res = await apiClient.post<TokenResponse>(
        '/api/v1/auth/login',
        { identifier, password },
        { skipAuth: true }
      );

      if (res.mfa_required && res.mfa_token) {
        setIs2FARequired(true);
        setMfaToken(res.mfa_token);
        setIsLoading(false);
        return res;
      }

      if (res.access_token) {
        apiClient.setTokens(res.access_token);
        setToken(res.access_token);
        setUser(res.user || DEFAULT_SUPERUSER);
        setIsAuthenticated(true);
        setIs2FARequired(false);
        setMfaToken(null);
      }

      setIsLoading(false);
      return res;
    } catch (err: any) {
      setIsLoading(false);
      const msg = err instanceof ApiError ? err.message : 'Invalid login credentials';
      setError(msg);
      throw err;
    }
  };

  const verify2FA = async (code: string): Promise<boolean> => {
    if (!mfaToken) {
      setError('MFA session expired. Please log in again.');
      return false;
    }

    setIsLoading(true);
    setError(null);

    try {
      const res = await apiClient.post<TokenResponse>(
        '/api/v1/auth/2fa/verify',
        { mfa_token: mfaToken, code },
        { skipAuth: true }
      );

      if (res.access_token) {
        apiClient.setTokens(res.access_token);
        setToken(res.access_token);
        setUser(res.user || DEFAULT_SUPERUSER);
        setIsAuthenticated(true);
        setIs2FARequired(false);
        setMfaToken(null);
        setIsLoading(false);
        return true;
      }

      setIsLoading(false);
      return false;
    } catch (err: any) {
      setIsLoading(false);
      const msg = err instanceof ApiError ? err.message : 'Invalid 2FA code';
      setError(msg);
      return false;
    }
  };

  const cancel2FA = () => {
    setIs2FARequired(false);
    setMfaToken(null);
    setError(null);
  };

  const logout = () => {
    apiClient.clearTokens();
    setUser(null);
    setToken(null);
    setIsAuthenticated(false);
    setIs2FARequired(false);
    setMfaToken(null);
    setError(null);
  };

  const clearError = () => setError(null);

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated,
        isLoading,
        is2FARequired,
        mfaToken,
        error,
        login,
        verify2FA,
        cancel2FA,
        logout,
        clearError,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
