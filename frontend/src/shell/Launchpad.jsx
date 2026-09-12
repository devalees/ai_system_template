import React, { useState } from 'react';
import { useUISettings } from '../core/uiSettingsContext';
import { useTheme } from '../core/themeContext';
import { getAllApps } from '../apps/registry';
import {
  Search,
  X,
  Bot,
  Users,
  CheckSquare,
  Sliders,
  FolderLock,
  FileText,
  Zap,
  ShieldAlert,
  Pin,
  PinOff,
  ArrowLeft,
  ArrowRight,
} from 'lucide-react';

// Icon map helper for Lucide icons
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

export default function Launchpad() {
  const { language, t } = useTheme();
  const {
    isLaunchpadOpen,
    setIsLaunchpadOpen,
    appOrder,
    reorderApps,
    pinnedApps,
    togglePinApp,
    launchApp,
  } = useUISettings();

  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('All');

  if (!isLaunchpadOpen) return null;

  const allApps = getAllApps(appOrder);

  // Filter apps based on search query and category
  const filteredApps = allApps.filter((app) => {
    const title = language === 'ar' ? app.title_ar || app.title : app.title;
    const matchesSearch = title.toLowerCase().includes(searchQuery.toLowerCase()) ||
                          app.id.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesCategory = selectedCategory === 'All' || app.category === selectedCategory;
    return matchesSearch && matchesCategory;
  });

  const categories = ['All', 'Intelligence', 'Business', 'Platform'];

  // App reordering helper (move left / move right in order)
  const moveApp = (appId, direction) => {
    const currentIndex = appOrder.indexOf(appId);
    if (currentIndex === -1) return;
    const newIndex = currentIndex + direction;
    if (newIndex < 0 || newIndex >= appOrder.length) return;

    const newOrder = [...appOrder];
    const [moved] = newOrder.splice(currentIndex, 1);
    newOrder.splice(newIndex, 0, moved);
    reorderApps(newOrder);
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 1000,
        background: 'rgba(6, 8, 14, 0.82)',
        backdropFilter: 'var(--blur-launchpad)',
        WebkitBackdropFilter: 'var(--blur-launchpad)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        padding: '60px 40px 40px',
        animation: 'launchpadZoomIn 0.22s cubic-bezier(0.16, 1, 0.3, 1)',
        overflowY: 'auto',
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) setIsLaunchpadOpen(false);
      }}
    >
      {/* Top Search & Filter Bar */}
      <div
        style={{
          width: '100%',
          maxWidth: '520px',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '16px',
          marginBottom: '40px',
        }}
      >
        <div
          style={{
            width: '100%',
            position: 'relative',
            display: 'flex',
            alignItems: 'center',
          }}
        >
          <Search
            size={18}
            style={{
              position: 'absolute',
              left: language === 'ar' ? 'auto' : '16px',
              right: language === 'ar' ? '16px' : 'auto',
              color: 'var(--text-muted)',
            }}
          />
          <input
            type="text"
            autoFocus
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={t('search_placeholder')}
            className="glass-input"
            style={{
              height: '46px',
              borderRadius: '23px',
              paddingLeft: language === 'ar' ? '18px' : '46px',
              paddingRight: language === 'ar' ? '46px' : '18px',
              fontSize: '15px',
              background: 'rgba(255, 255, 255, 0.08)',
              border: '1px solid rgba(255, 255, 255, 0.15)',
              boxShadow: '0 8px 30px rgba(0,0,0,0.3)',
            }}
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              style={{
                position: 'absolute',
                right: language === 'ar' ? 'auto' : '14px',
                left: language === 'ar' ? '14px' : 'auto',
                background: 'transparent',
                border: 'none',
                color: 'var(--text-muted)',
                cursor: 'pointer',
              }}
            >
              <X size={16} />
            </button>
          )}
        </div>

        {/* Category Pills */}
        <div style={{ display: 'flex', gap: '8px' }}>
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className="glass-button"
              style={{
                borderRadius: '20px',
                padding: '4px 14px',
                fontSize: '12px',
                background: selectedCategory === cat ? 'var(--accent-primary)' : 'rgba(255,255,255,0.06)',
                borderColor: selectedCategory === cat ? 'var(--accent-primary)' : 'transparent',
                color: selectedCategory === cat ? '#fff' : 'var(--text-secondary)',
              }}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      {/* App Grid: Apple-Style Rounded Squircles */}
      <div
        style={{
          width: '100%',
          maxWidth: '860px',
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(130px, 1fr))',
          gap: '32px 24px',
          justifyItems: 'center',
        }}
      >
        {filteredApps.map((app) => {
          const IconComponent = iconMap[app.icon] || Bot;
          const isPinned = pinnedApps.includes(app.id);

          return (
            <div
              key={app.id}
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                width: '110px',
                position: 'relative',
                group: 'app-card',
              }}
            >
              {/* App Icon Squircle */}
              <div
                onClick={() => launchApp(app.id)}
                style={{
                  width: '84px',
                  height: '84px',
                  borderRadius: '22px',
                  background: app.gradient || 'var(--gradient-brand)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#fff',
                  cursor: 'pointer',
                  boxShadow: '0 12px 28px rgba(0,0,0,0.45), inset 0 1px 1px rgba(255,255,255,0.3)',
                  transition: 'all 0.25s cubic-bezier(0.175, 0.885, 0.32, 1.275)',
                  transform: 'scale(1)',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.transform = 'scale(1.08) translateY(-4px)';
                  e.currentTarget.style.boxShadow = '0 18px 36px rgba(0,0,0,0.55), inset 0 1px 1px rgba(255,255,255,0.4)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.transform = 'scale(1)';
                  e.currentTarget.style.boxShadow = '0 12px 28px rgba(0,0,0,0.45), inset 0 1px 1px rgba(255,255,255,0.3)';
                }}
              >
                <IconComponent size={40} strokeWidth={1.8} />
              </div>

              {/* App Title */}
              <span
                onClick={() => launchApp(app.id)}
                style={{
                  marginTop: '10px',
                  fontSize: '13px',
                  fontWeight: 600,
                  color: 'var(--text-primary)',
                  textAlign: 'center',
                  cursor: 'pointer',
                  textShadow: '0 2px 4px rgba(0,0,0,0.6)',
                  maxWidth: '110px',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {language === 'ar' ? app.title_ar || app.title : app.title}
              </span>

              {/* Dynamic Reordering Controls (Hover Toolbar) */}
              <div
                style={{
                  display: 'flex',
                  gap: '4px',
                  marginTop: '6px',
                  opacity: 0.7,
                  transition: 'opacity 0.2s ease',
                }}
              >
                <button
                  onClick={() => moveApp(app.id, -1)}
                  title="Move backward"
                  style={{
                    background: 'rgba(255,255,255,0.1)',
                    border: 'none',
                    borderRadius: '4px',
                    color: '#fff',
                    padding: '2px 4px',
                    cursor: 'pointer',
                  }}
                >
                  <ArrowLeft size={10} />
                </button>
                <button
                  onClick={() => togglePinApp(app.id)}
                  title={isPinned ? 'Unpin from Dock' : 'Pin to Dock'}
                  style={{
                    background: isPinned ? 'var(--accent-primary)' : 'rgba(255,255,255,0.1)',
                    border: 'none',
                    borderRadius: '4px',
                    color: '#fff',
                    padding: '2px 4px',
                    cursor: 'pointer',
                  }}
                >
                  {isPinned ? <Pin size={10} /> : <PinOff size={10} />}
                </button>
                <button
                  onClick={() => moveApp(app.id, 1)}
                  title="Move forward"
                  style={{
                    background: 'rgba(255,255,255,0.1)',
                    border: 'none',
                    borderRadius: '4px',
                    color: '#fff',
                    padding: '2px 4px',
                    cursor: 'pointer',
                  }}
                >
                  <ArrowRight size={10} />
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Dismiss Button */}
      <button
        onClick={() => setIsLaunchpadOpen(false)}
        style={{
          marginTop: 'auto',
          background: 'rgba(255,255,255,0.08)',
          border: '1px solid rgba(255,255,255,0.15)',
          color: 'var(--text-secondary)',
          width: '36px',
          height: '36px',
          borderRadius: '50%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: 'pointer',
          transition: 'all 0.2s ease',
        }}
        onMouseEnter={(e) => (e.currentTarget.style.color = '#fff')}
      >
        <X size={18} />
      </button>
    </div>
  );
}
