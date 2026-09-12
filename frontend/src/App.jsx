import React, { useEffect } from 'react';
import { AuthProvider } from './core/authContext';
import { ThemeProvider } from './core/themeContext';
import { UISettingsProvider, useUISettings } from './core/uiSettingsContext';
import { initializeApps } from './apps';
import { getApp } from './apps/registry';
import TopBar from './shell/TopBar';
import Launchpad from './shell/Launchpad';
import Dock from './shell/Dock';
import CommandSearch from './shell/CommandSearch';

// Initialize modular apps into the registry
initializeApps();

function AppShell() {
  const { activeAppId } = useUISettings();
  const currentApp = getApp(activeAppId);
  const ActiveComponent = currentApp?.component || null;

  return (
    <div style={{ width: '100vw', height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* 1. Apple-Style Top Navigation Bar */}
      <TopBar />

      {/* 2. Main Active Application Workspace */}
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden', display: 'flex' }}>
        {ActiveComponent ? (
          <ActiveComponent />
        ) : (
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>
            Application not found
          </div>
        )}
      </div>

      {/* 3. Fullscreen Launchpad Springboard */}
      <Launchpad />

      {/* 4. Global Command Palette / Search (Cmd+K) */}
      <CommandSearch />

      {/* 5. Mac-Style Floating Bottom Dock */}
      <Dock />
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <ThemeProvider>
        <UISettingsProvider>
          <AppShell />
        </UISettingsProvider>
      </ThemeProvider>
    </AuthProvider>
  );
}
