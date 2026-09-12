import React from 'react';
import { AuthProvider, useAuth } from './core/authContext';
import { ThemeProvider } from './core/themeContext';
import { UISettingsProvider, useUISettings } from './core/uiSettingsContext';
import { initializeApps } from './apps';
import { getApp } from './apps/registry';
import TopBar from './shell/TopBar';
import AppGridLanding from './shell/AppGridLanding';
import CommandSearch from './shell/CommandSearch';
import LoginPage from './shell/LoginPage';

// Initialize modular apps into the registry
initializeApps();

function AppShell() {
  const { activeAppId } = useUISettings();
  const isHome = activeAppId === 'home' || !activeAppId;
  const currentApp = !isHome ? getApp(activeAppId) : null;
  const ActiveComponent = currentApp?.component || null;

  return (
    <div style={{ width: '100vw', height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* 1. Odoo-Style Top Navigation Bar */}
      <TopBar />

      {/* 2. Main Canvas: Central App Grid (Home) OR Active App Module */}
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden', display: 'flex' }}>
        {isHome ? (
          <AppGridLanding />
        ) : ActiveComponent ? (
          <ActiveComponent />
        ) : (
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>
            Application not found
          </div>
        )}
      </div>

      {/* 3. Global Command Palette / Search (Cmd+K) */}
      <CommandSearch />
    </div>
  );
}

function RootContent() {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div
        style={{
          width: '100vw',
          height: '100vh',
          background: 'var(--bg-base)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '12px',
          color: 'var(--text-secondary)',
          fontSize: '13px',
        }}
      >
        <div
          style={{
            width: '28px',
            height: '28px',
            border: '2px solid var(--border-glass)',
            borderTopColor: 'var(--accent-primary)',
            borderRadius: '50%',
            animation: 'spin 0.8s linear infinite',
          }}
        />
        <span>Initializing Workspace...</span>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <LoginPage />;
  }

  return (
    <UISettingsProvider>
      <AppShell />
    </UISettingsProvider>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <ThemeProvider>
        <RootContent />
      </ThemeProvider>
    </AuthProvider>
  );
}
