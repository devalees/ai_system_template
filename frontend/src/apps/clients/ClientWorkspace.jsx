import React, { useState, useEffect } from 'react';
import { useTheme } from '../../core/themeContext';
import api from '../../core/api';
import DynamicTable from '../../components/DynamicTable';
import DynamicForm from '../../components/DynamicForm';
import {
  Users,
  Building2,
  DollarSign,
  ShieldCheck,
  FolderLock,
  Plus,
  ArrowUpRight,
  Sparkles,
  X,
  FileText,
  UserPlus,
} from 'lucide-react';

const INITIAL_CLIENTS = [
  {
    id: 'c101-alpha',
    name: 'Acme Global Holdings',
    company_registration: 'CR-948102',
    is_ai_enabled: true,
    ai_budget_usd: 500.0,
    ai_spend_usd: 142.5,
    user_count: 8,
    doc_count: 14,
    created_at: '2026-09-01',
  },
  {
    id: 'c102-beta',
    name: 'Nexus Financial Logistics',
    company_registration: 'CR-220491',
    is_ai_enabled: true,
    ai_budget_usd: 250.0,
    ai_spend_usd: 195.0,
    user_count: 4,
    doc_count: 6,
    created_at: '2026-09-04',
  },
  {
    id: 'c103-gamma',
    name: 'Apex Robotics Labs',
    company_registration: 'CR-883912',
    is_ai_enabled: false,
    ai_budget_usd: 1000.0,
    ai_spend_usd: 0.0,
    user_count: 12,
    doc_count: 28,
    created_at: '2026-09-08',
  },
  {
    id: 'c104-delta',
    name: 'Sovereign Health AI',
    company_registration: 'CR-771239',
    is_ai_enabled: true,
    ai_budget_usd: 750.0,
    ai_spend_usd: 685.2,
    user_count: 6,
    doc_count: 19,
    created_at: '2026-09-10',
  },
];

export default function ClientWorkspace() {
  const { language } = useTheme();
  const [clients, setClients] = useState(INITIAL_CLIENTS);
  const [selectedClient, setSelectedClient] = useState(null);
  const [showAddModal, setShowAddModal] = useState(false);

  // Fetch live clients from Django backend if reachable
  useEffect(() => {
    api.get('/api/v1/clients/').then((data) => {
      if (data && Array.isArray(data.results)) {
        setClients(data.results);
      } else if (Array.isArray(data)) {
        setClients(data);
      }
    }).catch(() => {
      // Fallback to initial clients in dev/isolated environment
    });
  }, []);

  const handleAddClient = (formData) => {
    const newClient = {
      id: `c-${Date.now()}`,
      name: formData.name,
      company_registration: formData.company_registration || 'CR-NEW',
      is_ai_enabled: formData.is_ai_enabled ?? true,
      ai_budget_usd: Number(formData.ai_budget_usd) || 500,
      ai_spend_usd: 0.0,
      user_count: 1,
      doc_count: 0,
      created_at: new Date().toISOString().split('T')[0],
    };
    setClients([newClient, ...clients]);
    setShowAddModal(false);
  };

  const columns = [
    {
      key: 'name',
      label: language === 'ar' ? 'اسم العميل / الشركة' : 'CLIENT / COMPANY',
      render: (val, row) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div
            style={{
              width: '32px',
              height: '32px',
              borderRadius: '8px',
              background: 'rgba(14, 165, 233, 0.15)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#38bdf8',
            }}
          >
            <Building2 size={16} />
          </div>
          <div>
            <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{val}</div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{row.company_registration}</div>
          </div>
        </div>
      ),
    },
    {
      key: 'is_ai_enabled',
      label: language === 'ar' ? 'خدمة الذكاء الاصطناعي' : 'AI SERVICE',
      render: (val) =>
        val ? (
          <span className="badge badge-emerald">ENABLED</span>
        ) : (
          <span className="badge badge-rose">DISABLED</span>
        ),
    },
    {
      key: 'budget_gauge',
      label: language === 'ar' ? 'استهلاك الميزانية' : 'AI BUDGET SPEND GAUGE',
      render: (_, row) => {
        const pct = Math.min(100, Math.round((row.ai_spend_usd / (row.ai_budget_usd || 1)) * 100));
        const color = pct > 90 ? 'var(--accent-rose)' : pct > 60 ? 'var(--accent-amber)' : 'var(--accent-emerald)';

        return (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', minWidth: '160px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--text-secondary)' }}>
              <span>${row.ai_spend_usd.toFixed(1)}</span>
              <span style={{ fontWeight: 700, color }}>{pct}% (${row.ai_budget_usd})</span>
            </div>
            <div style={{ width: '100%', height: '6px', background: 'rgba(255,255,255,0.08)', borderRadius: '3px', overflow: 'hidden' }}>
              <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: '3px', transition: 'width 0.4s ease' }} />
            </div>
          </div>
        );
      },
    },
    {
      key: 'user_count',
      label: language === 'ar' ? 'المستخدمين' : 'USERS',
      render: (val) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
          <Users size={13} color="var(--text-muted)" />
          <span>{val} users</span>
        </div>
      ),
    },
    {
      key: 'doc_count',
      label: language === 'ar' ? 'المستندات' : 'DOCUMENTS',
      render: (val) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
          <FolderLock size={13} color="var(--text-muted)" />
          <span>{val} files</span>
        </div>
      ),
    },
  ];

  return (
    <div style={{ flex: 1, height: 'calc(100vh - 38px)', overflowY: 'auto', padding: '28px 36px 100px', background: 'var(--bg-primary)' }}>
      {/* Metric Cards Banner */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px', marginBottom: '24px' }}>
        <div className="glass-card" style={{ padding: '18px' }}>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Total Managed Clients</div>
          <div style={{ fontSize: '24px', fontWeight: 800, color: 'var(--text-primary)', marginTop: '6px' }}>{clients.length}</div>
          <div style={{ fontSize: '11px', color: 'var(--accent-emerald)', marginTop: '4px' }}>100% Tenant Scoped</div>
        </div>

        <div className="glass-card" style={{ padding: '18px' }}>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Total Allocated AI Budget</div>
          <div style={{ fontSize: '24px', fontWeight: 800, color: 'var(--accent-cyan)', marginTop: '6px' }}>
            ${clients.reduce((acc, c) => acc + c.ai_budget_usd, 0).toLocaleString()}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>Dollar Denominated Ceilings</div>
        </div>

        <div className="glass-card" style={{ padding: '18px' }}>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Total Monthly AI Spend</div>
          <div style={{ fontSize: '24px', fontWeight: 800, color: 'var(--accent-amber)', marginTop: '6px' }}>
            ${clients.reduce((acc, c) => acc + c.ai_spend_usd, 0).toFixed(2)}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--accent-emerald)', marginTop: '4px' }}>Audit Health: Optimal</div>
        </div>
      </div>

      {/* Main Dynamic Table */}
      <DynamicTable
        title={language === 'ar' ? 'دليل حسابات العملاء والشركات' : 'Client Accounts Roster'}
        subtitle={language === 'ar' ? 'حوكمة ميزانيات الذكاء الاصطناعي، المستودعات الرقمية، والمستخدمين المرتبطين' : 'Enterprise 3-tier hierarchy, AI budget governance, and dedicated physical storage'}
        columns={columns}
        data={clients}
        onRowClick={(row) => setSelectedClient(row)}
        onAddClick={() => setShowAddModal(true)}
      />

      {/* Client Detail Modal */}
      {selectedClient && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 1200,
            background: 'rgba(0,0,0,0.6)',
            backdropFilter: 'blur(16px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
          onClick={(e) => {
            if (e.target === e.currentTarget) setSelectedClient(null);
          }}
        >
          <div
            className="glass-panel"
            style={{ width: '100%', maxWidth: '640px', maxHeight: '85vh', overflowY: 'auto', padding: '28px', display: 'flex', flexDirection: 'column', gap: '20px' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div
                  style={{
                    width: '42px',
                    height: '42px',
                    borderRadius: '12px',
                    background: 'rgba(14, 165, 233, 0.2)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#38bdf8',
                  }}
                >
                  <Building2 size={22} />
                </div>
                <div>
                  <h3 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-primary)' }}>{selectedClient.name}</h3>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>ID: {selectedClient.id}</div>
                </div>
              </div>
              <button
                onClick={() => setSelectedClient(null)}
                style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
              >
                <X size={20} />
              </button>
            </div>

            {/* AI Governance Snapshot */}
            <div className="glass-card" style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-secondary)' }}>AI Service Authorization</span>
                <span className={`badge ${selectedClient.is_ai_enabled ? 'badge-emerald' : 'badge-rose'}`}>
                  {selectedClient.is_ai_enabled ? 'AUTHORIZED' : 'LOCKED'}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
                <span style={{ color: 'var(--text-muted)' }}>Dedicated Storage Path:</span>
                <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
                  documents/clients/{selectedClient.id}/
                </span>
              </div>
            </div>

            {/* Associated Users Inline */}
            <div>
              <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '10px' }}>
                Linked Users ({selectedClient.user_count})
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {Array.from({ length: Math.min(3, selectedClient.user_count) }).map((_, i) => (
                  <div
                    key={i}
                    className="glass-card"
                    style={{ padding: '10px 14px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}
                  >
                    <div style={{ fontSize: '13px', color: 'var(--text-primary)' }}>user_{i + 1}@{selectedClient.name.toLowerCase().replace(/[^a-z]/g, '')}.com</div>
                    <span className="badge badge-cyan">CLIENT PORTAL</span>
                  </div>
                ))}
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '10px' }}>
              <button onClick={() => setSelectedClient(null)} className="glass-button">
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add Client Modal Form */}
      {showAddModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 1200,
            background: 'rgba(0,0,0,0.6)',
            backdropFilter: 'blur(16px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <div style={{ width: '100%', maxWidth: '520px' }}>
            <DynamicForm
              title={language === 'ar' ? 'تسجيل عميل جديد' : 'Register New Client'}
              fields={[
                { name: 'name', label: 'Client / Company Name', type: 'text', required: true, placeholder: 'e.g. Acme Corp' },
                { name: 'company_registration', label: 'Registration Number', type: 'text', placeholder: 'CR-...' },
                { name: 'ai_budget_usd', label: 'Monthly AI Budget ($ USD)', type: 'number', defaultValue: 500 },
                { name: 'is_ai_enabled', label: 'Authorize AI Services', type: 'checkbox', defaultValue: true },
              ]}
              onSubmit={handleAddClient}
              onCancel={() => setShowAddModal(false)}
            />
          </div>
        </div>
      )}
    </div>
  );
}
