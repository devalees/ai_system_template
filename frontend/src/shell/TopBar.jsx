import React, { useState, useRef, useEffect } from 'react';
import { useTheme } from '../core/themeContext';
import { useAuth } from '../core/authContext';
import { useUISettings } from '../core/uiSettingsContext';
import { getApp, getAppMenus } from '../apps/registry';
import {
  LayoutGrid,
  Search,
  Moon,
  Sun,
  Bell,
  Sparkles,
  ChevronDown,
  ShieldCheck,
  LogOut,
  Sliders,
  ExternalLink,
} from 'lucide-react';

export default function TopBar() {
  const { theme, toggleTheme, language, setLanguage, t } = useTheme();
  const { user, logout } = useAuth();
  const { activeAppId, launchApp, isLaunchpadOpen, setIsLaunchpadOpen, setIsSearchOpen } = useUISettings();

  const [activeDropdown, setActiveDropdown] = useState(null);
  const dropdownRef = useRef(null);

  const activeApp = getApp(activeAppId) || { title: 'Universal AI OS', title_ar: 'نظام الذكاء الاصطناعي' };
  const appMenus = getAppMenus(activeAppId);

  // Close dropdowns when clicking outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setActiveDropdown(null);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <header
      ref={dropdownRef}
      style={{
        height: '38px',
        background: 'var(--bg-glass-heavy)',
        backdropFilter: 'var(--blur-glass)',
        WebkitBackdropFilter: 'var(--blur-glass)',
        borderBottom: '1px solid var(--border-subtle)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 12px',
        userSelect: 'none',
        zIndex: 50,
        fontSize: '13px',
      }}
    >
      {/* Left: Apple / Brand Menu & Dynamic App Submenus */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
        {/* System Logo Dropdown */}
        <div style={{ position: 'relative' }}>
          <button
            onClick={() => setActiveDropdown(activeDropdown === 'system' ? null : 'system')}
            style={{
              background: activeDropdown === 'system' ? 'var(--bg-hover)' : 'transparent',
              border: 'none',
              color: 'var(--text-primary)',
              padding: '4px 8px',
              borderRadius: '6px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontWeight: 700,
            }}
          >
            <div
              style={{
                width: '18px',
                height: '18px',
                borderRadius: '5px',
                background: 'var(--gradient-brand)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#fff',
                fontSize: '10px',
              }}
            >
              ✦
            </div>
          </button>

          {activeDropdown === 'system' && (
            <div
              style={{
                position: 'absolute',
                top: '32px',
                left: language === 'ar' ? 'auto' : '0',
                right: language === 'ar' ? '0' : 'auto',
                width: '210px',
                background: 'var(--bg-glass-card)',
                backdropFilter: 'var(--blur-glass)',
                border: '1px solid var(--border-glass)',
                borderRadius: '10px',
                boxShadow: 'var(--shadow-glass)',
                padding: '6px',
                display: 'flex',
                flexDirection: 'column',
                gap: '2px',
                zIndex: 100,
                animation: 'slideDown 0.15s ease',
              }}
            >
              <div style={{ padding: '6px 10px', fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>
                {t('system_name')}
              </div>
              <button
                onClick={() => {
                  launchApp('settings');
                  setActiveDropdown(null);
                }}
                className="glass-button"
                style={{ justifyContent: 'flex-start', border: 'none', background: 'transparent' }}
              >
                <Sliders size={14} />
                <span>{t('settings')}</span>
              </button>
              <a
                href="/admin/"
                target="_blank"
                rel="noreferrer"
                className="glass-button"
                style={{ justifyContent: 'flex-start', border: 'none', background: 'transparent' }}
              >
                <ExternalLink size={14} />
                <span>Django Admin</span>
              </a>
              <div style={{ height: '1px', background: 'var(--border-subtle)', margin: '4px 0' }} />
              <button
                onClick={logout}
                className="glass-button"
                style={{ justifyContent: 'flex-start', border: 'none', background: 'transparent', color: 'var(--accent-rose)' }}
              >
                <LogOut size={14} />
                <span>{t('logout')}</span>
              </button>
            </div>
          )}
        </div>

        {/* Active Application Name */}
        <span style={{ fontWeight: 700, color: 'var(--text-primary)', padding: '0 6px' }}>
          {language === 'ar' ? activeApp.title_ar || activeApp.title : activeApp.title}
        </span>

        {/* Dynamic Injected App Menus & Submenus */}
        {appMenus.map((menu, idx) => (
          <div key={idx} style={{ position: 'relative' }}>
            <button
              onClick={() => setActiveDropdown(activeDropdown === `app_menu_${idx}` ? null : `app_menu_${idx}`)}
              style={{
                background: activeDropdown === `app_menu_${idx}` ? 'var(--bg-hover)' : 'transparent',
                border: 'none',
                color: 'var(--text-secondary)',
                padding: '4px 8px',
                borderRadius: '6px',
                cursor: 'pointer',
                fontWeight: 500,
              }}
            >
              {language === 'ar' ? menu.label_ar || menu.label : menu.label}
            </button>

            {activeDropdown === `app_menu_${idx}` && menu.items && (
              <div
                style={{
                  position: 'absolute',
                  top: '32px',
                  left: language === 'ar' ? 'auto' : '0',
                  right: language === 'ar' ? '0' : 'auto',
                  minWidth: '180px',
                  background: 'var(--bg-glass-card)',
                  backdropFilter: 'var(--blur-glass)',
                  border: '1px solid var(--border-glass)',
                  borderRadius: '10px',
                  boxShadow: 'var(--shadow-glass)',
                  padding: '6px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '2px',
                  zIndex: 100,
                  animation: 'slideDown 0.15s ease',
                }}
              >
                {menu.items.map((item, itemIdx) => (
                  <button
                    key={itemIdx}
                    onClick={() => {
                      if (item.action) {
                        window.dispatchEvent(new CustomEvent(`app_action_${item.action}`));
                      }
                      setActiveDropdown(null);
                    }}
                    className="glass-button"
                    style={{ justifyContent: 'flex-start', border: 'none', background: 'transparent' }}
                  >
                    <span>{language === 'ar' ? item.label_ar || item.label : item.label}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Center: Global Search Bar Trigger */}
      <button
        onClick={() => setIsSearchOpen(true)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '4px 14px',
          background: 'rgba(255, 255, 255, 0.05)',
          border: '1px solid var(--border-subtle)',
          borderRadius: '20px',
          color: 'var(--text-muted)',
          cursor: 'pointer',
          fontSize: '12px',
          minWidth: '220px',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Search size={12} />
          <span>{t('search_placeholder')}</span>
        </div>
        <kbd style={{ background: 'rgba(255,255,255,0.08)', padding: '1px 5px', borderRadius: '4px', fontSize: '10px' }}>
          ⌘K
        </kbd>
      </button>

      {/* Right: Telemetry, Toggles & User Status */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        {/* Launchpad Trigger Button */}
        <button
          onClick={() => setIsLaunchpadOpen(!isLaunchpadOpen)}
          title={t('launchpad')}
          style={{
            background: isLaunchpadOpen ? 'var(--accent-primary)' : 'rgba(255, 255, 255, 0.06)',
            border: '1px solid var(--border-subtle)',
            color: '#fff',
            width: '28px',
            height: '28px',
            borderRadius: '7px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            transition: 'all 0.2s ease',
          }}
        >
          <LayoutGrid size={15} />
        </button>

        {/* Live Token & Budget Telemetry Pill */}
        <div
          title="Daily Token Spend Telemetry"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '3px 9px',
            background: 'rgba(99, 102, 241, 0.12)',
            border: '1px solid rgba(99, 102, 241, 0.25)',
            borderRadius: '20px',
            fontSize: '11px',
            fontWeight: 600,
            color: '#a5b4fc',
          }}
        >
          <Sparkles size={12} color="#818cf8" />
          <span>$0.024</span>
          <span style={{ opacity: 0.5 }}>|</span>
          <span>42.1k tok</span>
        </div>

        {/* Language Switcher Pill */}
        <button
          onClick={() => setLanguage(language === 'en' ? 'ar' : 'en')}
          style={{
            background: 'transparent',
            border: '1px solid var(--border-subtle)',
            color: 'var(--text-secondary)',
            padding: '3px 8px',
            borderRadius: '6px',
            cursor: 'pointer',
            fontSize: '11px',
            fontWeight: 600,
          }}
        >
          {language === 'en' ? 'العربية' : 'EN'}
        </button>

        {/* Dark/Light Theme Toggle */}
        <button
          onClick={toggleTheme}
          title={theme === 'dark' ? t('light_mode') : t('dark_mode')}
          style={{
            background: 'transparent',
            border: 'none',
            color: 'var(--text-secondary)',
            cursor: 'pointer',
            padding: '4px',
            display: 'flex',
            alignItems: 'center',
          }}
        >
          {theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
        </button>

        {/* User Pill */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '2px 8px 2px 4px',
            background: 'rgba(255, 255, 255, 0.05)',
            border: '1px solid var(--border-subtle)',
            borderRadius: '20px',
          }}
        >
          <div
            style={{
              width: '20px',
              height: '20px',
              borderRadius: '50%',
              background: 'linear-gradient(135deg, #10b981 0%, #06b6d4 100%)',
              color: '#fff',
              fontSize: '10px',
              fontWeight: 700,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            {user?.username?.[0]?.toUpperCase() || 'A'}
          </div>
          <span style={{ fontSize: '12px', fontWeight: 500, color: 'var(--text-primary)' }}>
            {user?.username || 'admin'}
          </span>
        </div>
      </div>
    </header>
  );
}
