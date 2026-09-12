/**
 * Universal API Client for Django Backend Integration
 * Handles DRF TokenAuth, workspace scoping, and JSON payloads.
 */

const API_BASE = import.meta.env.VITE_API_URL || '';

class ApiClient {
  constructor() {
    this.token = localStorage.getItem('token') || '';
    this.workspace = localStorage.getItem('active_workspace') || 'default';
  }

  setToken(token) {
    this.token = token;
    if (token) {
      localStorage.setItem('token', token);
    } else {
      localStorage.removeItem('token');
    }
  }

  setWorkspace(slug) {
    this.workspace = slug;
    localStorage.setItem('active_workspace', slug);
  }

  getHeaders(extraHeaders = {}) {
    const headers = {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      'X-Workspace-Slug': this.workspace,
      ...extraHeaders,
    };
    if (this.token) {
      headers['Authorization'] = `Token ${this.token}`;
    }
    return headers;
  }

  async request(endpoint, options = {}) {
    const url = endpoint.startsWith('http') ? endpoint : `${API_BASE}${endpoint}`;
    const headers = this.getHeaders(options.headers);

    const config = {
      ...options,
      headers,
    };

    if (options.body && typeof options.body === 'object' && !(options.body instanceof FormData)) {
      config.body = JSON.stringify(options.body);
    } else if (options.body instanceof FormData) {
      delete headers['Content-Type']; // Let browser set boundary
    }

    try {
      const response = await fetch(url, config);
      if (response.status === 401) {
        // Token invalid or expired
        console.warn('[API] Received 401 Unauthorized for:', endpoint);
      }
      return response;
    } catch (error) {
      console.error('[API Network Error]:', error);
      throw error;
    }
  }

  async get(endpoint, params = {}) {
    let url = endpoint;
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, val]) => {
      if (val !== undefined && val !== null) {
        searchParams.append(key, val);
      }
    });
    const queryString = searchParams.toString();
    if (queryString) {
      url += (url.includes('?') ? '&' : '?') + queryString;
    }
    const response = await this.request(url, { method: 'GET' });
    if (!response.ok) {
      throw new Error(`GET ${endpoint} failed with HTTP ${response.status}`);
    }
    return response.json();
  }

  async post(endpoint, body = {}) {
    const response = await this.request(endpoint, { method: 'POST', body });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      const msg = (Array.isArray(errorData.non_field_errors) && errorData.non_field_errors[0])
        || errorData.error
        || errorData.detail
        || errorData.message
        || `Request failed (${response.status})`;
      throw new Error(msg);
    }
    return response.json();
  }

  async patch(endpoint, body = {}) {
    const response = await this.request(endpoint, { method: 'PATCH', body });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.error || errorData.detail || `PATCH ${endpoint} failed (${response.status})`);
    }
    return response.json();
  }

  async delete(endpoint) {
    const response = await this.request(endpoint, { method: 'DELETE' });
    if (!response.ok) {
      throw new Error(`DELETE ${endpoint} failed (${response.status})`);
    }
    return true;
  }
}

export const api = new ApiClient();
export default api;
