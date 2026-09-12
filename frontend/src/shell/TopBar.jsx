import React, { useState, useRef, useEffect } from 'react';
import { useTheme } from '../core/themeContext';
import { useAuth } from '../core/authContext';
import { useUISettings } from '../core/uiSettingsContext';
import { getApp, getAppMenus } from '../apps/registry';
import api from '../core/api';
import {
  LayoutGrid,
  Search,
  Palette,
  Bell,
  Sparkles,
  ChevronDown,
  Sliders,
  ExternalLink,
  LogOut,
  Home,
} from 'lucide-react';

export default function TopBar() {
  const { currentTheme, switchTheme, allThemes, language, setLanguage, t } = useTheme();
  const { user, logout } = useAuth();
  const { activeAppId, launchApp, setIsSearchOpen } = useUISettings();

  const [activeDropdown, setActiveDropdown] = useState(null);
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const dropdownRef = useRef(null);

  const isHome = activeAppId === 'home' || !activeAppId;
  const activeApp = !isHome ? getApp(activeAppId) : null;
  const appMenus = !isHome ? getAppMenus(activeAppId) : [];

  const loadNotifications = async () => {
    try {
      const countRes = await api.get('/api/v1/notifications/unread-count/').catch(() => null);
      if (countRes && typeof countRes.unread_count === 'number') {
        setUnreadCount(countRes.unread_count);
      }
      const listRes = await api.get('/api/v1/notifications/').catch(() => null);
      const list = Array.isArray(listRes?.results) ? listRes.results : Array.isArray(listRes) ? listRes : [];
      setNotifications(list);
    } catch {
      // Graceful fallback
    }
  };

  useEffect(() => {
    loadNotifications();
  }, []);

  const handleMarkAllRead = async () => {
    try {
      await api.post('/api/v1/notifications/mark-all-read/');
      setUnreadCount(0);
      loadNotifications();
    } catch {
      // Graceful fallback
    }
  };

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
      {/* Left: Odoo-Style App Switcher & Dynamic Breadcrumb */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
        {/* Odoo-Style 9-Dots / App Grid Button */}
        <button
          onClick={() => launchApp('home')}
          title={language === 'ar' ? 'الرجوع لقائمة التطبيقات (الرئيسية)' : 'Return to App Launcher (Home)'}
          style={{
            background: isHome ? 'var(--accent-primary)' : 'rgba(255, 255, 255, 0.08)',
            border: 'none',
            color: '#fff',
            padding: '5px 7px',
            borderRadius: '6px',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            transition: 'all 0.2s ease',
          }}
        >
          <LayoutGrid size={15} />
        </button>

        {/* System & App Breadcrumbs */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px' }}>
          <span
            onClick={() => launchApp('home')}
            style={{
              fontWeight: isHome ? 700 : 500,
              color: isHome ? 'var(--text-primary)' : 'var(--text-secondary)',
              cursor: 'pointer',
            }}
          >
            {t('system_name')}
          </span>

          {!isHome && activeApp && (
            <>
              <span style={{ color: 'var(--text-muted)', opacity: 0.5 }}>/</span>
              <span style={{ fontWeight: 700, color: 'var(--text-primary)' }}>
                {language === 'ar' ? activeApp.title_ar || activeApp.title : activeApp.title}
              </span>
            </>
          )}
        </div>

        {/* Dynamic Contextual Menus (Only shown when inside an application) */}
        {!isHome && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginInlineStart: '12px' }}>
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
        )}
      </div>

      {/* Center: Global Search Trigger */}
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

      {/* Right: Theme Engine Selector, Language Switcher & User Status */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        {/* Pluggable Theme Engine Selector Dropdown */}
        <div style={{ position: 'relative' }}>
          <button
            onClick={() => setActiveDropdown(activeDropdown === 'themes' ? null : 'themes')}
            title={t('themes')}
            style={{
              background: activeDropdown === 'themes' ? 'var(--bg-hover)' : 'transparent',
              border: '1px solid var(--border-subtle)',
              color: 'var(--text-secondary)',
              padding: '4px 8px',
              borderRadius: '6px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '5px',
              fontSize: '11px',
              fontWeight: 600,
            }}
          >
            <Palette size={13} color="var(--accent-glow)" />
            <span>{currentTheme?.name?.split(' ')[0] || 'Theme'}</span>
          </button>

          {activeDropdown === 'themes' && (
            <div
              style={{
                position: 'absolute',
                top: '32px',
                right: language === 'ar' ? 'auto' : '0',
                left: language === 'ar' ? '0' : 'auto',
                width: '240px',
                background: 'var(--bg-glass-card)',
                backdropFilter: 'var(--blur-glass)',
                border: '1px solid var(--border-glass)',
                borderRadius: '10px',
                boxShadow: 'var(--shadow-glass)',
                padding: '6px',
                display: 'flex',
                flexDirection: 'column',
                gap: '4px',
                zIndex: 100,
                animation: 'slideDown 0.15s ease',
              }}
            >
              <div style={{ padding: '6px 8px', fontSize: '11px', color: 'var(--text-muted)', fontWeight: 700 }}>
                {t('themes')}
              </div>
              {allThemes.map((th) => (
                <button
                  key={th.id}
                  onClick={() => {
                    switchTheme(th.id);
                    setActiveDropdown(null);
                  }}
                  className="glass-button"
                  style={{
                    justifyContent: 'flex-start',
                    border: 'none',
                    background: currentTheme.id === th.id ? 'var(--accent-primary)' : 'transparent',
                    color: currentTheme.id === th.id ? '#fff' : 'var(--text-primary)',
                    fontSize: '12px',
                  }}
                >
                  <div
                    style={{
                      width: '10px',
                      height: '10px',
                      borderRadius: '50%',
                      background: th.variables['--accent-primary'],
                    }}
                  />
                  <span>{language === 'ar' ? th.name_ar : th.name}</span>
                </button>
              ))}
            </div>
          )}
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

        {/* Notifications Bell */}
        <div style={{ position: 'relative' }}>
          <button
            onClick={() => {
              setActiveDropdown(activeDropdown === 'notifications' ? null : 'notifications');
              if (activeDropdown !== 'notifications') {
                loadNotifications();
              }
            }}
            title={language === 'ar' ? 'الإشعارات' : 'Notifications'}
            style={{
              background: activeDropdown === 'notifications' ? 'rgba(255, 255, 255, 0.12)' : 'transparent',
              border: 'none',
              color: 'var(--text-secondary)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '6px',
              borderRadius: '6px',
              position: 'relative',
              transition: 'all 0.15s ease',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--text-primary)')}
            onMouseLeave={(e) => (e.currentTarget.style.color = activeDropdown === 'notifications' ? 'var(--text-primary)' : 'var(--text-secondary)')}
          >
            <Bell size={15} />
            {unreadCount > 0 && (
              <span
                style={{
                  position: 'absolute',
                  top: '2px',
                  right: '2px',
                  width: '7px',
                  height: '7px',
                  borderRadius: '50%',
                  background: 'var(--accent-rose, #f43f5e)',
                  boxShadow: '0 0 6px var(--accent-rose, #f43f5e)',
                }}
              />
            )}
          </button>

          {activeDropdown === 'notifications' && (
            <div
              style={{
                position: 'absolute',
                top: '32px',
                right: language === 'ar' ? 'auto' : '0',
                left: language === 'ar' ? '0' : 'auto',
                width: '280px',
                maxHeight: '360px',
                background: 'var(--bg-glass-card)',
                backdropFilter: 'var(--blur-glass)',
                border: '1px solid var(--border-glass)',
                borderRadius: '10px',
                boxShadow: 'var(--shadow-glass)',
                display: 'flex',
                flexDirection: 'column',
                zIndex: 100,
                overflow: 'hidden',
                animation: 'slideDown 0.15s ease',
              }}
            >
              <div
                style={{
                  padding: '10px 12px',
                  borderBottom: '1px solid var(--border-subtle)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span style={{ fontWeight: 600, fontSize: '12px', color: 'var(--text-primary)' }}>
                    {language === 'ar' ? 'الإشعارات' : 'Notifications'}
                  </span>
                  {unreadCount > 0 && (
                    <span
                      style={{
                        background: 'rgba(244, 63, 94, 0.15)',
                        color: 'var(--accent-rose, #f43f5e)',
                        fontSize: '10px',
                        padding: '1px 5px',
                        borderRadius: '10px',
                        fontWeight: 600,
                      }}
                    >
                      {unreadCount}
                    </span>
                  )}
                </div>
                {unreadCount > 0 && (
                  <button
                    onClick={handleMarkAllRead}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: 'var(--accent-primary)',
                      fontSize: '11px',
                      cursor: 'pointer',
                      padding: 0,
                    }}
                  >
                    {language === 'ar' ? 'تحديد الكل كمقروء' : 'Mark all read'}
                  </button>
                )}
              </div>

              <div style={{ maxHeight: '280px', overflowY: 'auto', padding: '6px' }}>
                {notifications.length === 0 ? (
                  <div style={{ padding: '24px 12px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '11px' }}>
                    {language === 'ar' ? 'لا توجد إشعارات حالية' : 'No notifications'}
                  </div>
                ) : (
                  notifications.map((n) => (
                    <div
                      key={n.id}
                      style={{
                        padding: '8px 10px',
                        borderRadius: '6px',
                        marginBottom: '4px',
                        background: n.is_read ? 'transparent' : 'rgba(255, 255, 255, 0.04)',
                        borderLeft: n.is_read ? '2px solid transparent' : '2px solid var(--accent-primary)',
                        transition: 'background 0.15s ease',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '6px' }}>
                        <span style={{ fontWeight: 600, fontSize: '11px', color: 'var(--text-primary)' }}>
                          {n.title}
                        </span>
                        <span style={{ fontSize: '9px', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                          {new Date(n.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>
                      <p style={{ margin: '4px 0 0', fontSize: '11px', color: 'var(--text-secondary)', lineHeight: 1.3 }}>
                        {n.message}
                      </p>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        {/* User Pill / System Settings Menu */}
        <div style={{ position: 'relative' }}>
          <div
            onClick={() => setActiveDropdown(activeDropdown === 'user' ? null : 'user')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '2px 8px 2px 4px',
              background: 'rgba(255, 255, 255, 0.05)',
              border: '1px solid var(--border-subtle)',
              borderRadius: '20px',
              cursor: 'pointer',
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

          {activeDropdown === 'user' && (
            <div
              style={{
                position: 'absolute',
                top: '32px',
                right: language === 'ar' ? 'auto' : '0',
                left: language === 'ar' ? '0' : 'auto',
                width: '200px',
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
      </div>
    </header>
  );
}
