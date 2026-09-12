import React, { useState } from 'react';
import { useUISettings } from '../core/uiSettingsContext';
import { useTheme } from '../core/themeContext';
import { getApp } from '../apps/registry';
import {
  LayoutGrid,
  Bot,
  Users,
  CheckSquare,
  Sliders,
  FolderLock,
  FileText,
  Zap,
  ShieldAlert,
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

export default function Dock() {
  const { language, t } = useTheme();
  const { pinnedApps, activeAppId, launchApp, setIsLaunchpadOpen } = useUISettings();
  const [hoveredApp, setHoveredApp] = useState(null);

  return (
    <div
      style={{
        position: 'fixed',
        bottom: '12px',
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 40,
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
        padding: '6px 12px',
        background: 'rgba(15, 21, 35, 0.65)',
        backdropFilter: 'var(--blur-glass)',
        WebkitBackdropFilter: 'var(--blur-glass)',
        border: '1px solid rgba(255, 255, 255, 0.12)',
        borderRadius: '20px',
        boxShadow: 'var(--shadow-dock)',
      }}
    >
      {/* Launchpad Quick Trigger in Dock */}
      <div
        style={{ position: 'relative', display: 'flex', flexDirection: 'column', alignItems: 'center' }}
        onMouseEnter={() => setHoveredApp('launchpad')}
        onMouseLeave={() => setHoveredApp(null)}
      >
        <button
          onClick={() => setIsLaunchpadOpen(true)}
          style={{
            width: '44px',
            height: '44px',
            borderRadius: '12px',
            background: 'linear-gradient(135deg, #334155 0%, #1e293b 100%)',
            border: '1px solid rgba(255,255,255,0.15)',
            color: '#fff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            transition: 'transform 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275)',
            transform: hoveredApp === 'launchpad' ? 'scale(1.15) translateY(-4px)' : 'scale(1)',
          }}
        >
          <LayoutGrid size={22} />
        </button>

        {hoveredApp === 'launchpad' && (
          <div
            style={{
              position: 'absolute',
              top: '-32px',
              padding: '3px 8px',
              background: 'rgba(0,0,0,0.8)',
              borderRadius: '6px',
              fontSize: '11px',
              fontWeight: 600,
              color: '#fff',
              whiteSpace: 'nowrap',
              pointerEvents: 'none',
              animation: 'fadeIn 0.15s ease',
            }}
          >
            {t('launchpad')}
          </div>
        )}
      </div>

      <div style={{ width: '1px', height: '28px', background: 'rgba(255,255,255,0.1)' }} />

      {/* Pinned Applications */}
      {pinnedApps.map((appId) => {
        const app = getApp(appId);
        if (!app) return null;
        const IconComponent = iconMap[app.icon] || Bot;
        const isActive = activeAppId === appId;
        const isHovered = hoveredApp === appId;

        return (
          <div
            key={appId}
            style={{ position: 'relative', display: 'flex', flexDirection: 'column', alignItems: 'center' }}
            onMouseEnter={() => setHoveredApp(appId)}
            onMouseLeave={() => setHoveredApp(null)}
          >
            <button
              onClick={() => launchApp(appId)}
              style={{
                width: '44px',
                height: '44px',
                borderRadius: '12px',
                background: app.gradient || 'var(--gradient-brand)',
                border: '1px solid rgba(255,255,255,0.2)',
                color: '#fff',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer',
                transition: 'transform 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275)',
                transform: isHovered ? 'scale(1.18) translateY(-6px)' : 'scale(1)',
                boxShadow: isActive ? '0 4px 15px rgba(99, 102, 241, 0.4)' : 'none',
              }}
            >
              <IconComponent size={22} />
            </button>

            {/* Active Running Indicator Dot */}
            {isActive && (
              <div
                style={{
                  width: '4px',
                  height: '4px',
                  borderRadius: '50%',
                  background: 'var(--accent-glow)',
                  marginTop: '3px',
                  boxShadow: '0 0 6px var(--accent-primary)',
                }}
              />
            )}

            {/* Tooltip on Hover */}
            {isHovered && (
              <div
                style={{
                  position: 'absolute',
                  top: '-32px',
                  padding: '3px 8px',
                  background: 'rgba(0,0,0,0.85)',
                  backdropFilter: 'blur(8px)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: '6px',
                  fontSize: '11px',
                  fontWeight: 600,
                  color: '#fff',
                  whiteSpace: 'nowrap',
                  pointerEvents: 'none',
                  animation: 'fadeIn 0.15s ease',
                }}
              >
                {language === 'ar' ? app.title_ar || app.title : app.title}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
