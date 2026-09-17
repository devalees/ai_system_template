/**
 * Multi-Company Context & Dual-Header Protocol Engine.
 * Enforces `X-Company-ID` for mutation requests and `X-Company-IDs` for aggregated read queries.
 */

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';

export interface CompanyEntity {
  id: string;
  name: string;
  code: string;
  currency: string;
  is_primary: boolean;
  country_code?: string;
}

export interface CompanyContextType {
  activeCompany: CompanyEntity;
  allowedCompanies: CompanyEntity[];
  aggregatedCompanyIds: string[];
  switchActiveCompany: (companyId: string) => void;
  toggleAggregatedCompany: (companyId: string) => void;
  setAllAggregatedCompanies: (companyIds: string[]) => void;
  getCompanyHeaders: (method?: string) => Record<string, string>;
}

const DEFAULT_COMPANIES: CompanyEntity[] = [
  {
    id: '00000000-0000-0000-0000-000000000001',
    name: 'Acme Corp HQ',
    code: 'ACME-HQ',
    currency: 'USD',
    is_primary: true,
    country_code: 'US',
  },
  {
    id: '00000000-0000-0000-0000-000000000002',
    name: 'Acme Europe Logistics',
    code: 'ACME-EU',
    currency: 'EUR',
    is_primary: false,
    country_code: 'DE',
  },
  {
    id: '00000000-0000-0000-0000-000000000003',
    name: 'Acme Middle East FZCO',
    code: 'ACME-ME',
    currency: 'AED',
    is_primary: false,
    country_code: 'AE',
  },
];

const ACTIVE_COMPANY_STORAGE_KEY = 'sovereign_active_company_id';
const AGGREGATED_COMPANIES_STORAGE_KEY = 'sovereign_aggregated_company_ids';

const CompanyContext = createContext<CompanyContextType | undefined>(undefined);

export const CompanyProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [allowedCompanies] = useState<CompanyEntity[]>(DEFAULT_COMPANIES);

  const [activeCompany, setActiveCompany] = useState<CompanyEntity>(() => {
    const savedId = localStorage.getItem(ACTIVE_COMPANY_STORAGE_KEY);
    const found = DEFAULT_COMPANIES.find((c) => c.id === savedId);
    return found || DEFAULT_COMPANIES[0];
  });

  const [aggregatedCompanyIds, setAggregatedCompanyIds] = useState<string[]>(() => {
    try {
      const saved = localStorage.getItem(AGGREGATED_COMPANIES_STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) return parsed;
      }
    } catch {
      // ignore parse errors
    }
    return [DEFAULT_COMPANIES[0].id];
  });

  useEffect(() => {
    localStorage.setItem(ACTIVE_COMPANY_STORAGE_KEY, activeCompany.id);
  }, [activeCompany]);

  useEffect(() => {
    localStorage.setItem(AGGREGATED_COMPANIES_STORAGE_KEY, JSON.stringify(aggregatedCompanyIds));
  }, [aggregatedCompanyIds]);

  const switchActiveCompany = (companyId: string) => {
    const target = allowedCompanies.find((c) => c.id === companyId);
    if (target) {
      setActiveCompany(target);
      // Ensure the newly active company is also included in aggregated reads
      if (!aggregatedCompanyIds.includes(target.id)) {
        setAggregatedCompanyIds((prev) => [...prev, target.id]);
      }
    }
  };

  const toggleAggregatedCompany = (companyId: string) => {
    setAggregatedCompanyIds((prev) => {
      if (prev.includes(companyId)) {
        // Prevent deselecting everything
        if (prev.length === 1) return prev;
        return prev.filter((id) => id !== companyId);
      } else {
        return [...prev, companyId];
      }
    });
  };

  const setAllAggregatedCompanies = (companyIds: string[]) => {
    if (companyIds.length > 0) {
      setAggregatedCompanyIds(companyIds);
    }
  };

  /**
   * Generates multi-company HTTP headers:
   * - Mutations (POST, PUT, PATCH, DELETE): `X-Company-ID` set to single active company.
   * - Queries (GET): `X-Company-IDs` set to comma-separated aggregated company IDs.
   */
  const getCompanyHeaders = (method = 'GET'): Record<string, string> => {
    const upperMethod = method.toUpperCase();
    if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(upperMethod)) {
      return {
        'X-Company-ID': activeCompany.id,
      };
    } else {
      return {
        'X-Company-IDs': aggregatedCompanyIds.join(','),
        'X-Company-ID': activeCompany.id, // also send active company as primary reference
      };
    }
  };

  return (
    <CompanyContext.Provider
      value={{
        activeCompany,
        allowedCompanies,
        aggregatedCompanyIds,
        switchActiveCompany,
        toggleAggregatedCompany,
        setAllAggregatedCompanies,
        getCompanyHeaders,
      }}
    >
      {children}
    </CompanyContext.Provider>
  );
};

export const useCompany = (): CompanyContextType => {
  const context = useContext(CompanyContext);
  if (!context) {
    throw new Error('useCompany must be used within a CompanyProvider');
  }
  return context;
};
