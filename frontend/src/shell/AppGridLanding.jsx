import React, { useState } from 'react';
import { useUISettings } from '../core/uiSettingsContext';
import { useTheme } from '../core/themeContext';
import { getAllApps } from '../apps/registry';
import {
  Search,
  Bot,
  Users,
  CheckSquare,
  Sliders,
  FolderLock,
  FileText,
  Zap,
  ShieldAlert,
  ArrowRight,
  Sparkles,
} from 'lucide-react';

const iconMap = {
  Bot,
  Users,
  CheckSquare,
  Sliders,
  FolderLock,
  FileText,
  Zap,
  ShieldAlert,
};

export default function AppGridLanding() {
  const { language, t } = useTheme();
  const { appOrder, launchApp } = useUISettings();
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('All');

  const allApps = getAllApps(appOrder);

  const filteredApps = allApps.filter((app) => {
    const title = language === 'ar' ? app.title_ar || app.title : app.title;
    const desc = language === 'ar' ? app.description_ar || '' : app.description || '';
    const matchesQuery =
      title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      desc.toLowerCase().includes(searchQuery.toLowerCase()) ||
      app.id.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesCategory = selectedCategory === 'All' || app.category === selectedCategory;
    return matchesQuery && matchesCategory;
  });

  const categories = [
    { id: 'All', label: 'All Applications', label_ar: 'جميع التطبيقات' },
    { id: 'Business', label: 'Business & CRM', label_ar: 'الأعمال والعملاء' },
    { id: 'Intelligence', label: 'AI & Intelligence', label_ar: 'الذكاء الاصطناعي والمهام' },
    { id: 'Platform', label: 'System & Platform', label_ar: 'النظام والمنصة' },
  ];

  return (
    <div
      style={{
        flex: 1,
        height: 'calc(100vh - 38px)',
        overflowY: 'auto',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        padding: '50px 24px 80px',
        background: 'var(--bg-primary)',
        animation: 'fadeIn 0.25s ease',
      }}
    >
      {/* Central Hero Header & Search (Odoo Structure) */}
      <div
        style={{
          width: '100%',
          maxWidth: '740px',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '18px',
          marginBottom: '46px',
        }}
      >
        <div style={{ textAlign: 'center' }}>
          <h1
            style={{
              fontSize: '28px',
              fontWeight: 800,
              fontFamily: 'var(--font-display)',
              color: 'var(--text-primary)',
              letterSpacing: '-0.02em',
            }}
          >
            {language === 'ar' ? 'منظومة التطبيقات المؤسسية' : 'Enterprise Application Hub'}
          </h1>
          <p style={{ fontSize: '14px', color: 'var(--text-muted)', marginTop: '6px' }}>
            {language === 'ar'
              ? 'اختر التطبيق أو القسم لبدء العمل والتشغيل'
              : 'Select an application or department workspace to launch'}
          </p>
        </div>

        {/* Central Search Bar */}
        <div
          style={{
            width: '100%',
            maxWidth: '560px',
            position: 'relative',
            display: 'flex',
            alignItems: 'center',
          }}
        >
          <Search
            size={18}
            style={{
              position: 'absolute',
              left: language === 'ar' ? 'auto' : '18px',
              right: language === 'ar' ? '18px' : 'auto',
              color: 'var(--accent-glow)',
            }}
          />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={
              language === 'ar'
                ? 'ابحث في التطبيقات والوحدات البرمجية...'
                : 'Search applications, modules, workflows...'
            }
            className="glass-input"
            style={{
              height: '48px',
              borderRadius: '24px',
              paddingLeft: language === 'ar' ? '20px' : '48px',
              paddingRight: language === 'ar' ? '48px' : '20px',
              fontSize: '15px',
              background: 'var(--bg-glass-card)',
              border: '1px solid var(--border-glass)',
              boxShadow: '0 8px 32px rgba(0,0,0,0.35)',
            }}
          />
        </div>

        {/* Category Filter Pills */}
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', justifyContent: 'center' }}>
          {categories.map((cat) => (
            <button
              key={cat.id}
              onClick={() => setSelectedCategory(cat.id)}
              className="glass-button"
              style={{
                borderRadius: '20px',
                padding: '6px 16px',
                fontSize: '12px',
                fontWeight: 600,
                background: selectedCategory === cat.id ? 'var(--accent-primary)' : 'rgba(255, 255, 255, 0.05)',
                borderColor: selectedCategory === cat.id ? 'var(--accent-primary)' : 'transparent',
                color: selectedCategory === cat.id ? '#fff' : 'var(--text-secondary)',
                transition: 'all 0.2s ease',
              }}
            >
              {language === 'ar' ? cat.label_ar : cat.label}
            </button>
          ))}
        </div>
      </div>

      {/* Central Application Grid (Apple Squircles & Cards) */}
      <div
        style={{
          width: '100%',
          maxWidth: '920px',
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
          gap: '24px',
          justifyContent: 'center',
        }}
      >
        {filteredApps.map((app) => {
          const IconComponent = iconMap[app.icon] || Bot;

          return (
            <div
              key={app.id}
              onClick={() => launchApp(app.id)}
              className="glass-card"
              style={{
                padding: '24px',
                display: 'flex',
                flexDirection: 'column',
                gap: '16px',
                cursor: 'pointer',
                borderRadius: 'var(--radius-card, 16px)',
                position: 'relative',
                overflow: 'hidden',
              }}
            >
              {/* Card Top: Squircle Icon & Category Badge */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div
                  style={{
                    width: '64px',
                    height: '64px',
                    borderRadius: 'var(--radius-squircle, 20px)',
                    background: app.gradient || 'var(--gradient-brand)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#fff',
                    boxShadow: '0 8px 20px rgba(0,0,0,0.35), inset 0 1px 1px rgba(255,255,255,0.3)',
                    transition: 'transform 0.25s cubic-bezier(0.175, 0.885, 0.32, 1.275)',
                  }}
                >
                  <IconComponent size={32} strokeWidth={1.8} />
                </div>

                <span className="badge badge-indigo" style={{ fontSize: '10px' }}>
                  {app.category}
                </span>
              </div>

              {/* Title & Description */}
              <div>
                <h3 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text-primary)' }}>
                  {language === 'ar' ? app.title_ar || app.title : app.title}
                </h3>
                <p
                  style={{
                    fontSize: '12px',
                    color: 'var(--text-muted)',
                    marginTop: '6px',
                    lineHeight: '1.5',
                    minHeight: '36px',
                  }}
                >
                  {language === 'ar' ? app.description_ar : app.description}
                </p>
              </div>

              {/* Card Action Link */}
              <div
                style={{
                  marginTop: 'auto',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  fontSize: '12px',
                  fontWeight: 600,
                  color: 'var(--accent-glow)',
                }}
              >
                <span>{language === 'ar' ? 'فتح التطبيق' : 'Launch Module'}</span>
                <ArrowRight size={13} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
