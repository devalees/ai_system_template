/**
 * Multi-Company Context & Dual-Header Switcher Modal.
 * Supports active single-company selection (mutations) and aggregated multi-company filtering (reads).
 */

import React from 'react';
import { useCompany } from '../../kernel/company/CompanyContext';
import { Building2, CheckSquare, Square, X, Layers } from 'lucide-react';

interface CompanySwitcherModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const CompanySwitcherModal: React.FC<CompanySwitcherModalProps> = ({ isOpen, onClose }) => {
  const {
    activeCompany,
    allowedCompanies,
    aggregatedCompanyIds,
    switchActiveCompany,
    toggleAggregatedCompany,
  } = useCompany();

  if (!isOpen) return null;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal-card"
        style={{
          width: '540px',
          maxWidth: '92vw',
          padding: '20px',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '16px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Building2 size={18} color="var(--accent-primary)" />
            <span style={{ fontSize: '15px', fontWeight: 600 }}>Multi-Company Organization Context</span>
          </div>
          <button
            onClick={onClose}
            className="btn btn-ghost btn-icon"
            style={{ padding: '4px', color: 'var(--text-muted)' }}
          >
            <X size={16} />
          </button>
        </div>

        {/* Dual Header Protocol Notice */}
        <div
          style={{
            background: 'var(--accent-subtle)',
            border: '1px solid var(--accent-primary)',
            borderRadius: 'var(--radius-md)',
            padding: '10px 12px',
            marginBottom: '16px',
            fontSize: '11px',
            color: 'var(--text-secondary)',
            display: 'flex',
            gap: '8px',
          }}
        >
          <Layers size={16} color="var(--accent-primary)" style={{ flexShrink: 0, marginTop: '2px' }} />
          <div>
            <span style={{ fontWeight: 600, color: 'var(--accent-primary)' }}>
              Dual-Header Enterprise Protocol:
            </span>{' '}
            Click a row to set your <strong>Active Mutation Tenant</strong> (<code>X-Company-ID</code>).
            Check boxes on the right to aggregate multiple entities in <strong>Consolidated Reports</strong> (<code>X-Company-IDs</code>).
          </div>
        </div>

        {/* Company List */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '16px' }}>
          {allowedCompanies.map((comp) => {
            const isActive = comp.id === activeCompany.id;
            const isAggregated = aggregatedCompanyIds.includes(comp.id);

            return (
              <div
                key={comp.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '12px 14px',
                  borderRadius: 'var(--radius-md)',
                  background: isActive ? 'var(--bg-surface-elevated)' : 'var(--bg-surface)',
                  border: `1.5px solid ${isActive ? 'var(--accent-primary)' : 'var(--border-subtle)'}`,
                  boxShadow: isActive ? 'var(--shadow-sm)' : 'none',
                  transition: 'var(--transition-fast)',
                }}
              >
                {/* Active Company Target (Clickable Left Section) */}
                <div
                  onClick={() => switchActiveCompany(comp.id)}
                  style={{ flex: 1, display: 'flex', alignItems: 'center', gap: '12px', cursor: 'pointer' }}
                >
                  <div
                    style={{
                      width: '32px',
                      height: '32px',
                      borderRadius: 'var(--radius-sm)',
                      background: isActive ? 'var(--accent-primary)' : 'var(--bg-card)',
                      color: isActive ? '#ffffff' : 'var(--text-secondary)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontWeight: 700,
                      fontSize: '12px',
                    }}
                  >
                    {comp.country_code || 'HQ'}
                  </div>

                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span style={{ fontSize: '13px', fontWeight: isActive ? 600 : 500 }}>
                        {comp.name}
                      </span>
                      {comp.is_primary && (
                        <span className="badge badge-primary" style={{ fontSize: '9px', padding: '1px 5px' }}>
                          Primary
                        </span>
                      )}
                      {isActive && (
                        <span className="badge badge-success" style={{ fontSize: '9px', padding: '1px 5px' }}>
                          Active
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                      Code: {comp.code} | Currency: {comp.currency}
                    </div>
                  </div>
                </div>

                {/* Aggregated Filter Checkbox (Right Section) */}
                <div
                  onClick={() => toggleAggregatedCompany(comp.id)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '6px 10px',
                    borderRadius: 'var(--radius-sm)',
                    background: isAggregated ? 'var(--bg-hover)' : 'transparent',
                    cursor: 'pointer',
                    userSelect: 'none',
                  }}
                  title="Toggle inclusion in consolidated read reports"
                >
                  {isAggregated ? (
                    <CheckSquare size={16} color="var(--accent-primary)" />
                  ) : (
                    <Square size={16} color="var(--border-strong)" />
                  )}
                  <span style={{ fontSize: '11px', color: isAggregated ? 'var(--text-primary)' : 'var(--text-muted)' }}>
                    Include
                  </span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Live Headers Telemetry Footer */}
        <div
          style={{
            padding: '10px 12px',
            background: 'var(--bg-card)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-md)',
            fontSize: '10px',
            fontFamily: 'var(--font-mono)',
            color: 'var(--text-secondary)',
          }}
        >
          <div>
            <span style={{ color: 'var(--accent-primary)' }}>X-Company-ID:</span> {activeCompany.id}
          </div>
          <div style={{ marginTop: '2px' }}>
            <span style={{ color: 'var(--success)' }}>X-Company-IDs:</span>{' '}
            {aggregatedCompanyIds.join(', ')} ({aggregatedCompanyIds.length} aggregated)
          </div>
        </div>

        {/* Action Buttons */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '16px' }}>
          <button onClick={onClose} className="btn btn-primary">
            Apply Context
          </button>
        </div>
      </div>
    </div>
  );
};
