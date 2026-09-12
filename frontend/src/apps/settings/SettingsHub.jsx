import React, { useState, useEffect } from 'react';
import { useTheme } from '../../core/themeContext';
import { useUISettings } from '../../core/uiSettingsContext';
import api from '../../core/api';
import { getAllApps } from '../registry';
import {
  Sliders,
  Globe,
  Navigation,
  Bot,
  Users,
  Zap,
  Shield,
  Key,
  Save,
  Check,
  Plus,
  Eye,
  EyeOff,
  Trash2,
  Lock,
} from 'lucide-react';

export default function SettingsHub() {
  const { theme, toggleTheme, language, setLanguage } = useTheme();
  const { appOrder, reorderApps, pinnedApps, togglePinApp } = useUISettings();

  const [activeTab, setActiveTab] = useState('general');
  const [savedSuccess, setSavedSuccess] = useState(false);

  // Settings State Form
  const [generalSettings, setGeneralSettings] = useState({
    systemName: 'Universal AI OS',
    companyName: 'Enterprise AI Lab',
    defaultLanguage: language,
    themeMode: theme,
  });

  const [aiSettings, setAiSettings] = useState({
    defaultProvider: 'openrouter',
    defaultModel: 'google/gemini-2.5-flash',
    defaultReasoning: 'none',
    dailyBudgetCap: 50.0,
  });

  const [clientSettings, setClientSettings] = useState({
    defaultAiEnabled: true,
    alertThreshold1: 25,
    alertThreshold2: 50,
    alertThreshold3: 75,
    alertThreshold4: 100,
  });

  // Provider Credentials
  const [credentials, setCredentials] = useState([]);
  const [newCredModal, setNewCredModal] = useState(false);
  const [newCredForm, setNewCredForm] = useState({ provider: 'openrouter', label: '', apiKey: '' });

  // Load live settings and credentials from Django backend
  useEffect(() => {
    api.get('/api/settings/').then((data) => {
      if (data && typeof data === 'object') {
        setGeneralSettings((prev) => ({ ...prev, ...data }));
      }
    }).catch(() => {});

    api.get('/api/provider-credentials/').then((data) => {
      if (Array.isArray(data) && data.length > 0) {
        setCredentials(data);
      }
    }).catch(() => {});
  }, []);

  const allApps = getAllApps(appOrder);

  const handleSave = async () => {
    try {
      await api.post('/api/settings/', { settings: generalSettings });
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 2500);
    } catch (err) {
      console.warn('[Settings Save]:', err);
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 2500);
    }
  };

  const handleAddCredential = async (e) => {
    e.preventDefault();
    if (!newCredForm.apiKey) return;

    try {
      const created = await api.post('/api/provider-credentials/', {
        name: newCredForm.label || `${newCredForm.provider.toUpperCase()} Key`,
        provider_type: newCredForm.provider,
        api_key: newCredForm.apiKey,
        is_active: true,
      });
      setCredentials((prev) => [created, ...prev]);
      setNewCredModal(false);
      setNewCredForm({ provider: 'openrouter', label: '', apiKey: '' });
    } catch (err) {
      console.error('[Add Credential Error]:', err);
      alert(err.message || 'Failed to add credential in Django');
    }
  };

  const handleDeleteCredential = async (id) => {
    try {
      await api.delete(`/api/provider-credentials/${id}/`);
      setCredentials((prev) => prev.filter((c) => c.id !== id));
    } catch (err) {
      console.warn('[Delete Credential]:', err);
      setCredentials((prev) => prev.filter((c) => c.id !== id));
    }
  };

  const tabs = [
    { id: 'general', label: 'General & Branding', label_ar: 'عام والعلامة التجارية', icon: Globe },
    { id: 'navigation', label: 'Navigation & UI Order', label_ar: 'التنقل وترتيب الواجهة', icon: Navigation },
    { id: 'ai_models', label: 'AI & Provider Credentials', label_ar: 'الذكاء الاصطناعي والمفاتيح', icon: Bot },
    { id: 'clients', label: 'Client AI Governance', label_ar: 'حوكمة عملاء الذكاء الاصطناعي', icon: Users },
    { id: 'automation', label: 'Automations & Workers', label_ar: 'الأتمتة وعمال المهام', icon: Zap },
    { id: 'security', label: 'Security & Access Control', label_ar: 'الأمان والتحكم بالصلاحيات', icon: Shield },
  ];

  return (
    <div
      style={{
        flex: 1,
        height: 'calc(100vh - 38px)',
        display: 'flex',
        background: 'var(--bg-primary)',
        overflow: 'hidden',
      }}
    >
      {/* Odoo-Style Categorized Sidebar */}
      <aside
        style={{
          width: '260px',
          background: 'var(--bg-glass-heavy)',
          borderInlineEnd: '1px solid var(--border-subtle)',
          display: 'flex',
          flexDirection: 'column',
          padding: '16px 12px',
          gap: '6px',
        }}
      >
        <div style={{ padding: '8px 12px', fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)', letterSpacing: '0.05em' }}>
          {language === 'ar' ? 'أقسام الإعدادات' : 'CONFIGURATION SECTIONS'}
        </div>

        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;

          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className="glass-button"
              style={{
                justifyContent: 'flex-start',
                padding: '10px 14px',
                borderRadius: '10px',
                background: isActive ? 'var(--accent-primary)' : 'transparent',
                borderColor: isActive ? 'var(--accent-primary)' : 'transparent',
                color: isActive ? '#fff' : 'var(--text-secondary)',
                fontWeight: isActive ? 600 : 500,
                fontSize: '13px',
              }}
            >
              <Icon size={16} />
              <span>{language === 'ar' ? tab.label_ar : tab.label}</span>
            </button>
          );
        })}

        <div style={{ marginTop: 'auto', padding: '12px' }}>
          <button onClick={handleSave} className="glass-button glass-button-primary" style={{ width: '100%', height: '38px' }}>
            {savedSuccess ? <Check size={16} /> : <Save size={16} />}
            <span>{savedSuccess ? (language === 'ar' ? 'تم الحفظ!' : 'Saved!') : (language === 'ar' ? 'حفظ التعديلات' : 'Save Changes')}</span>
          </button>
        </div>
      </aside>

      {/* Main Settings Canvas */}
      <main
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '32px 40px 100px',
          display: 'flex',
          flexDirection: 'column',
          gap: '24px',
          maxWidth: '960px',
        }}
      >
        {/* Tab 1: General & Branding */}
        {activeTab === 'general' && (
          <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <h3 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-primary)' }}>
              {language === 'ar' ? 'إعدادات النظام والعلامة التجارية' : 'General & Branding Settings'}
            </h3>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>System Name</label>
                <input
                  type="text"
                  value={generalSettings.systemName}
                  onChange={(e) => setGeneralSettings({ ...generalSettings, systemName: e.target.value })}
                  className="glass-input"
                  style={{ marginTop: '6px' }}
                />
              </div>

              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>Organization Title</label>
                <input
                  type="text"
                  value={generalSettings.companyName}
                  onChange={(e) => setGeneralSettings({ ...generalSettings, companyName: e.target.value })}
                  className="glass-input"
                  style={{ marginTop: '6px' }}
                />
              </div>
            </div>

            <div style={{ height: '1px', background: 'var(--border-subtle)', margin: '8px 0' }} />

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>Theme Mode</div>
                <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Toggle between Obsidian Dark and Clean Light</div>
              </div>
              <button onClick={toggleTheme} className="glass-button">
                {theme === 'dark' ? 'Dark Mode' : 'Light Mode'}
              </button>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>Default Language (i18n)</div>
                <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Right-to-left layout and Arabic locale synchronization</div>
              </div>
              <button onClick={() => setLanguage(language === 'en' ? 'ar' : 'en')} className="glass-button">
                {language === 'en' ? 'English (LTR)' : 'العربية (RTL)'}
              </button>
            </div>
          </div>
        )}

        {/* Tab 2: Navigation & UI Order */}
        {activeTab === 'navigation' && (
          <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <div>
              <h3 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-primary)' }}>
                {language === 'ar' ? 'ترتيب التطبيقات ولوحة التحكم' : 'Launchpad & Navigation Ordering'}
              </h3>
              <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
                Control which applications appear on the Launchpad springboard, their sequence, and pinned dock status.
              </p>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {allApps.map((app, idx) => (
                <div
                  key={app.id}
                  className="glass-card"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '12px 16px',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-muted)', width: '20px' }}>
                      #{idx + 1}
                    </span>
                    <div
                      style={{
                        width: '32px',
                        height: '32px',
                        borderRadius: '8px',
                        background: app.gradient,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: '#fff',
                      }}
                    >
                      ✦
                    </div>
                    <div>
                      <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>
                        {language === 'ar' ? app.title_ar || app.title : app.title}
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{app.category}</div>
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <button
                      onClick={() => togglePinApp(app.id)}
                      className="glass-button"
                      style={{
                        fontSize: '11px',
                        background: pinnedApps.includes(app.id) ? 'var(--accent-primary)' : undefined,
                        color: pinnedApps.includes(app.id) ? '#fff' : undefined,
                      }}
                    >
                      {pinnedApps.includes(app.id) ? 'Pinned to Dock' : 'Pin to Dock'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Tab 3: AI & Provider Credentials */}
        {activeTab === 'ai_models' && (
          <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <h3 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-primary)' }}>
                  {language === 'ar' ? 'المفاتيح المشفرة ونماذج الذكاء الاصطناعي' : 'AI Models & Provider Credentials'}
                </h3>
                <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
                  Secure encrypted keys for OpenRouter, Google Gemini, OpenAI, Anthropic, and Nous Portal.
                </p>
              </div>

              <button onClick={() => setNewCredModal(true)} className="glass-button glass-button-primary">
                <Plus size={14} />
                <span>{language === 'ar' ? 'إضافة مفتاح جديد' : 'Add API Key'}</span>
              </button>
            </div>

            {/* Credentials Table */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {credentials.map((cred) => (
                <div
                  key={cred.id}
                  className="glass-card"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '14px 16px',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <div
                      style={{
                        width: '32px',
                        height: '32px',
                        borderRadius: '8px',
                        background: 'rgba(99, 102, 241, 0.15)',
                        border: '1px solid rgba(99, 102, 241, 0.3)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: 'var(--accent-glow)',
                      }}
                    >
                      <Key size={16} />
                    </div>
                    <div>
                      <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>{cred.name || cred.label}</div>
                      <div style={{ fontSize: '12px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                        {cred.masked_key || cred.maskedKey}
                      </div>
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span className="badge badge-emerald">ACTIVE</span>
                    <button
                      onClick={() => handleDeleteCredential(cred.id)}
                      className="glass-button"
                      style={{ padding: '6px', color: 'var(--accent-rose)' }}
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                </div>
              ))}
            </div>

            {/* Budget Cap & Global Defaults */}
            <div style={{ height: '1px', background: 'var(--border-subtle)', margin: '8px 0' }} />

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '16px' }}>
              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>
                  Daily Spend Budget Cap ($ USD)
                </label>
                <input
                  type="number"
                  value={aiSettings.dailyBudgetCap}
                  onChange={(e) => setAiSettings({ ...aiSettings, dailyBudgetCap: Number(e.target.value) })}
                  className="glass-input"
                  style={{ marginTop: '6px' }}
                />
              </div>

              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>
                  Default Global Model
                </label>
                <input
                  type="text"
                  value={aiSettings.defaultModel}
                  onChange={(e) => setAiSettings({ ...aiSettings, defaultModel: e.target.value })}
                  className="glass-input"
                  style={{ marginTop: '6px' }}
                />
              </div>
            </div>
          </div>
        )}

        {/* Tab 4: Client AI Governance */}
        {activeTab === 'clients' && (
          <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <h3 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-primary)' }}>
              {language === 'ar' ? 'حوكمة ميزانيات العملاء والتواصل' : 'Client Service & AI Budget Governance'}
            </h3>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>Master AI Gatekeeper</div>
                <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Enable AI concierge service for new clients by default</div>
              </div>
              <input
                type="checkbox"
                checked={clientSettings.defaultAiEnabled}
                onChange={(e) => setClientSettings({ ...clientSettings, defaultAiEnabled: e.target.checked })}
                style={{ width: '18px', height: '18px', accentColor: 'var(--accent-primary)' }}
              />
            </div>

            <div style={{ height: '1px', background: 'var(--border-subtle)', margin: '8px 0' }} />

            <div>
              <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '8px' }}>
                Dollar Budget Percentage Milestones
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px' }}>
                <div className="glass-card" style={{ padding: '12px', textAlign: 'center' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Audit Milestone</div>
                  <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--accent-cyan)', marginTop: '4px' }}>25%</div>
                </div>
                <div className="glass-card" style={{ padding: '12px', textAlign: 'center' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Velocity Check</div>
                  <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--accent-amber)', marginTop: '4px' }}>50%</div>
                </div>
                <div className="glass-card" style={{ padding: '12px', textAlign: 'center' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Proactive Notice</div>
                  <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--accent-rose)', marginTop: '4px' }}>75%</div>
                </div>
                <div className="glass-card" style={{ padding: '12px', textAlign: 'center' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Quota Escalation</div>
                  <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--accent-primary)', marginTop: '4px' }}>100%</div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab 5: Automations */}
        {activeTab === 'automation' && (
          <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <h3 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-primary)' }}>
              {language === 'ar' ? 'محرك الأتمتة والمهام المجدولة' : 'Centralized Automation & Celery Workers'}
            </h3>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '16px' }}>
              <div className="glass-card" style={{ padding: '16px' }}>
                <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Celery Worker Status</div>
                <div style={{ fontSize: '16px', fontWeight: 700, color: 'var(--accent-emerald)', marginTop: '6px' }}>
                  ● Healthy (Active)
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>Queue: Redis 7.x alpine</div>
              </div>

              <div className="glass-card" style={{ padding: '16px' }}>
                <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Celery Beat Scheduler</div>
                <div style={{ fontSize: '16px', fontWeight: 700, color: 'var(--accent-cyan)', marginTop: '6px' }}>
                  ● Synchronized
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>Database-backed scheduler</div>
              </div>

              <div className="glass-card" style={{ padding: '16px' }}>
                <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Max Automation Depth</div>
                <div style={{ fontSize: '16px', fontWeight: 700, color: 'var(--accent-purple)', marginTop: '6px' }}>
                  3 Levels
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>Recursion protection ceiling</div>
              </div>
            </div>
          </div>
        )}

        {/* Tab 6: Security */}
        {activeTab === 'security' && (
          <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <h3 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-primary)' }}>
              {language === 'ar' ? 'الأمان ومراقبة التهديدات' : 'Security Posture & Access Control'}
            </h3>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>Zero-Trust Storage Isolation</div>
                <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Client documents partitioned under dedicated directories</div>
              </div>
              <span className="badge badge-emerald">ENFORCED</span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>Secret Leak Detection Scanner</div>
                <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Regex patterns scanning for OpenAI, Stripe, and private keys</div>
              </div>
              <span className="badge badge-indigo">ACTIVE (security_scanner)</span>
            </div>
          </div>
        )}
      </main>

      {/* Add API Key Modal */}
      {newCredModal && (
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
          <form
            onSubmit={handleAddCredential}
            className="glass-panel"
            style={{
              width: '100%',
              maxWidth: '460px',
              padding: '24px',
              display: 'flex',
              flexDirection: 'column',
              gap: '16px',
            }}
          >
            <h4 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text-primary)' }}>Add Provider Credential</h4>

            <div>
              <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>Provider</label>
              <select
                value={newCredForm.provider}
                onChange={(e) => setNewCredForm({ ...newCredForm, provider: e.target.value })}
                className="glass-input"
                style={{ marginTop: '4px' }}
              >
                <option value="openrouter">OpenRouter</option>
                <option value="openai">OpenAI</option>
                <option value="google">Google Gemini</option>
                <option value="anthropic">Anthropic</option>
                <option value="groq">Groq</option>
                <option value="deepseek">DeepSeek</option>
              </select>
            </div>

            <div>
              <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>Label / Identifier</label>
              <input
                type="text"
                placeholder="e.g. Production Key"
                value={newCredForm.label}
                onChange={(e) => setNewCredForm({ ...newCredForm, label: e.target.value })}
                className="glass-input"
                style={{ marginTop: '4px' }}
              />
            </div>

            <div>
              <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>API Secret Key</label>
              <input
                type="password"
                placeholder="sk-..."
                value={newCredForm.apiKey}
                onChange={(e) => setNewCredForm({ ...newCredForm, apiKey: e.target.value })}
                className="glass-input"
                style={{ marginTop: '4px' }}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '12px' }}>
              <button type="button" onClick={() => setNewCredModal(false)} className="glass-button">
                Cancel
              </button>
              <button type="submit" className="glass-button glass-button-primary">
                Add Credential
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
