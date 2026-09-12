import React, { useState, useEffect } from 'react';
import { useUISettings } from '../core/uiSettingsContext';
import { useTheme } from '../core/themeContext';
import { getAllApps } from '../apps/registry';
import { Search, X, Bot, ArrowRight } from 'lucide-react';

export default function CommandSearch() {
  const { isSearchOpen, setIsSearchOpen, launchApp } = useUISettings();
  const { language } = useTheme();
  const [query, setQuery] = useState('');

  if (!isSearchOpen) return null;

  const apps = getAllApps();
  const filtered = apps.filter((app) => {
    const title = language === 'ar' ? app.title_ar || app.title : app.title;
    return title.toLowerCase().includes(query.toLowerCase()) || app.id.toLowerCase().includes(query.toLowerCase());
  });

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 1100,
        background: 'rgba(0,0,0,0.6)',
        backdropFilter: 'blur(16px)',
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'center',
        paddingTop: '15vh',
        animation: 'fadeIn 0.15s ease',
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) setIsSearchOpen(false);
      }}
    >
      <div
        className="glass-panel"
        style={{
          width: '100%',
          maxWidth: '560px',
          background: 'var(--bg-glass-card)',
          borderRadius: '16px',
          overflow: 'hidden',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.7)',
          animation: 'scaleIn 0.18s cubic-bezier(0.16, 1, 0.3, 1)',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            padding: '14px 18px',
            borderBottom: '1px solid var(--border-subtle)',
          }}
        >
          <Search size={18} color="var(--accent-glow)" />
          <input
            type="text"
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={language === 'ar' ? 'ابحث في النظام أو اختر تطبيقاً...' : 'Search system, apps, or commands...'}
            style={{
              flex: 1,
              background: 'transparent',
              border: 'none',
              outline: 'none',
              fontSize: '15px',
              color: 'var(--text-primary)',
              fontFamily: 'var(--font-sans)',
            }}
          />
          <button
            onClick={() => setIsSearchOpen(false)}
            style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
          >
            <X size={18} />
          </button>
        </div>

        <div style={{ maxHeight: '320px', overflowY: 'auto', padding: '8px' }}>
          <div style={{ padding: '6px 12px', fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)' }}>
            {language === 'ar' ? 'التطبيقات المتاحة' : 'APPLICATIONS'}
          </div>

          {filtered.map((app) => (
            <div
              key={app.id}
              onClick={() => {
                launchApp(app.id);
                setIsSearchOpen(false);
              }}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '10px 12px',
                borderRadius: '8px',
                cursor: 'pointer',
                transition: 'background 0.15s ease',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--bg-hover)')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
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
                  <Bot size={18} />
                </div>
                <div>
                  <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
                    {language === 'ar' ? app.title_ar || app.title : app.title}
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                    {language === 'ar' ? app.description_ar : app.description}
                  </div>
                </div>
              </div>
              <ArrowRight size={14} color="var(--text-muted)" />
            </div>
          ))}

          {filtered.length === 0 && (
            <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px' }}>
              {language === 'ar' ? 'لا توجد نتائج مطابقة' : 'No matching items found'}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
