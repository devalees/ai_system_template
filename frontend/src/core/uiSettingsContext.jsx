import React, { createContext, useContext, useState, useEffect } from 'react';

const UISettingsContext = createContext(null);

export function UISettingsProvider({ children }) {
  const [activeAppId, setActiveAppId] = useState('ai_studio');
  const [isLaunchpadOpen, setIsLaunchpadOpen] = useState(false);
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [isNotificationOpen, setIsNotificationOpen] = useState(false);

  // App order for Launchpad (reorderable by user)
  const [appOrder, setAppOrder] = useState(() => {
    try {
      const saved = localStorage.getItem('ui_app_order');
      return saved ? JSON.parse(saved) : ['ai_studio', 'clients', 'tasks', 'settings'];
    } catch {
      return ['ai_studio', 'clients', 'tasks', 'settings'];
    }
  });

  // Pinned apps for the bottom Dock
  const [pinnedApps, setPinnedApps] = useState(() => {
    try {
      const saved = localStorage.getItem('ui_pinned_apps');
      return saved ? JSON.parse(saved) : ['ai_studio', 'clients', 'tasks', 'settings'];
    } catch {
      return ['ai_studio', 'clients', 'tasks', 'settings'];
    }
  });

  const reorderApps = (newOrder) => {
    setAppOrder(newOrder);
    localStorage.setItem('ui_app_order', JSON.stringify(newOrder));
  };

  const togglePinApp = (appId) => {
    setPinnedApps((prev) => {
      const next = prev.includes(appId) ? prev.filter((id) => id !== appId) : [...prev, appId];
      localStorage.setItem('ui_pinned_apps', JSON.stringify(next));
      return next;
    });
  };

  const launchApp = (appId) => {
    setActiveAppId(appId);
    setIsLaunchpadOpen(false);
  };

  // Keyboard shortcut listener: Cmd+K / Ctrl+K for search, Escape for Launchpad
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setIsSearchOpen((prev) => !prev);
      } else if (e.key === 'Escape') {
        setIsLaunchpadOpen(false);
        setIsSearchOpen(false);
        setIsNotificationOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  return (
    <UISettingsContext.Provider
      value={{
        activeAppId,
        setActiveAppId,
        isLaunchpadOpen,
        setIsLaunchpadOpen,
        isSearchOpen,
        setIsSearchOpen,
        isNotificationOpen,
        setIsNotificationOpen,
        appOrder,
        reorderApps,
        pinnedApps,
        togglePinApp,
        launchApp,
      }}
    >
      {children}
    </UISettingsContext.Provider>
  );
}

export function useUISettings() {
  const ctx = useContext(UISettingsContext);
  if (!ctx) throw new Error('useUISettings must be used within UISettingsProvider');
  return ctx;
}
