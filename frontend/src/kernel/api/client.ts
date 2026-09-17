/**
 * Native Zero-Dependency Typed Fetch API Client.
 * Features:
 * - Automated `Authorization: Bearer <jwt>` injection.
 * - Dual-header multi-company context propagation (`X-Company-ID` vs `X-Company-IDs`).
 * - 401 interception with silent refresh attempt and event bus emission.
 * - Structured API error serialization.
 */

export interface ApiRequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean | undefined | null>;
  skipAuth?: boolean;
  companyId?: string;
  companyIds?: string[];
}

export class ApiError extends Error {
  status: number;
  data: any;

  constructor(message: string, status: number, data: any) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

// Token & Session Storage Keys
const TOKEN_KEY = 'sovereign_auth_token';
const REFRESH_TOKEN_KEY = 'sovereign_refresh_token';

class ApiClient {
  private baseURL: string;

  constructor(baseURL = '') {
    this.baseURL = baseURL;
  }

  private getAuthToken(): string | null {
    return localStorage.getItem(TOKEN_KEY);
  }

  private getRefreshToken(): string | null {
    return localStorage.getItem(REFRESH_TOKEN_KEY);
  }

  public setTokens(accessToken: string, refreshToken?: string): void {
    localStorage.setItem(TOKEN_KEY, accessToken);
    if (refreshToken) {
      localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
    }
  }

  public clearTokens(): void {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
  }

  /**
   * Internal request executor with automatic header injection and 401 retry handling.
   */
  public async request<T = any>(endpoint: string, options: ApiRequestOptions = {}): Promise<T> {
    const {
      params,
      skipAuth = false,
      companyId,
      companyIds,
      headers: customHeaders,
      ...customOptions
    } = options;

    let url = endpoint.startsWith('http') ? endpoint : `${this.baseURL}${endpoint}`;

    // Append query parameters if provided
    if (params) {
      const searchParams = new URLSearchParams();
      for (const [key, value] of Object.entries(params)) {
        if (value !== undefined && value !== null) {
          searchParams.append(key, String(value));
        }
      }
      const qs = searchParams.toString();
      if (qs) {
        url += (url.includes('?') ? '&' : '?') + qs;
      }
    }

    // Prepare Request Headers
    const headers: Record<string, string> = {
      'Accept': 'application/json',
      ...(customHeaders as Record<string, string>),
    };

    if (!(customOptions.body instanceof FormData) && !headers['Content-Type']) {
      headers['Content-Type'] = 'application/json';
    }

    // Inject Bearer Token
    if (!skipAuth) {
      const token = this.getAuthToken();
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }
    }

    // Multi-Company Dual-Header Protocol
    const method = (customOptions.method || 'GET').toUpperCase();
    const isMutation = ['POST', 'PUT', 'PATCH', 'DELETE'].includes(method);

    if (companyId) {
      headers['X-Company-ID'] = companyId;
    } else {
      const savedActiveId = localStorage.getItem('sovereign_active_company_id');
      if (savedActiveId) {
        headers['X-Company-ID'] = savedActiveId;
      }
    }

    if (!isMutation) {
      if (companyIds && companyIds.length > 0) {
        headers['X-Company-IDs'] = companyIds.join(',');
      } else {
        const savedAggregated = localStorage.getItem('sovereign_aggregated_company_ids');
        if (savedAggregated) {
          try {
            const parsed = JSON.parse(savedAggregated);
            if (Array.isArray(parsed) && parsed.length > 0) {
              headers['X-Company-IDs'] = parsed.join(',');
            }
          } catch {
            // fallback
          }
        }
      }
    }

    // Execute Native Fetch
    let response: Response;
    try {
      response = await fetch(url, {
        ...customOptions,
        headers,
      });
    } catch (networkErr: any) {
      throw new ApiError(`Network request failed: ${networkErr.message}`, 0, null);
    }

    // Handle 401 Unauthorized (Token Refresh / Session Expiry)
    if (response.status === 401 && !skipAuth) {
      const refreshed = await this.attemptTokenRefresh();
      if (refreshed) {
        // Retry the original request once with the new token
        return this.request<T>(endpoint, { ...options, skipAuth: false });
      } else {
        window.dispatchEvent(new CustomEvent('sovereign:session_expired'));
      }
    }

    // Parse Response Body
    const contentType = response.headers.get('content-type') || '';
    let responseData: any = null;

    if (contentType.includes('application/json')) {
      try {
        responseData = await response.json();
      } catch {
        responseData = null;
      }
    } else {
      responseData = await response.text();
    }

    if (!response.ok) {
      const errorMessage =
        (responseData && (responseData.detail || responseData.message || responseData.error)) ||
        `HTTP Error ${response.status}: ${response.statusText}`;
      throw new ApiError(errorMessage, response.status, responseData);
    }

    return responseData as T;
  }

  /**
   * Attempt silent token refresh via backend `/api/v1/auth/refresh`.
   */
  private async attemptTokenRefresh(): Promise<boolean> {
    const refreshToken = this.getRefreshToken();
    if (!refreshToken) return false;

    try {
      const res = await fetch(`${this.baseURL}/api/v1/auth/refresh`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (res.ok) {
        const data = await res.json();
        if (data && data.access_token) {
          this.setTokens(data.access_token, data.refresh_token);
          return true;
        }
      }
    } catch (err) {
      console.warn('[ApiClient] Silent token refresh failed:', err);
    }

    this.clearTokens();
    return false;
  }

  // HTTP Verb Convenience Methods
  public get<T = any>(endpoint: string, options?: ApiRequestOptions): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: 'GET' });
  }

  public post<T = any>(endpoint: string, body?: any, options?: ApiRequestOptions): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'POST',
      body: body instanceof FormData ? body : JSON.stringify(body),
    });
  }

  public put<T = any>(endpoint: string, body?: any, options?: ApiRequestOptions): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'PUT',
      body: body instanceof FormData ? body : JSON.stringify(body),
    });
  }

  public patch<T = any>(endpoint: string, body?: any, options?: ApiRequestOptions): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'PATCH',
      body: body instanceof FormData ? body : JSON.stringify(body),
    });
  }

  public delete<T = any>(endpoint: string, options?: ApiRequestOptions): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: 'DELETE' });
  }
}

export const apiClient = new ApiClient('');
export default apiClient;
