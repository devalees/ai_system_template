/**
 * Authentication and RBAC User Types matching backend `identity_rbac`.
 */

export interface AuthUser {
  id: string;
  email: string;
  username: string;
  full_name: string;
  user_type: 'human' | 'ai_agent';
  is_superuser: boolean;
  is_primary_admin?: boolean;
  email_verified?: boolean;
  two_factor_enabled?: boolean;
  preferred_language: string;
  is_active: boolean;
  company_id: string;
}

export interface TokenResponse {
  access_token?: string | null;
  token_type?: string;
  user?: AuthUser | null;
  company_id?: string | null;
  mfa_required: boolean;
  mfa_token?: string | null;
}

export interface AuthState {
  user: AuthUser | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  is2FARequired: boolean;
  mfaToken: string | null;
  error: string | null;
}
