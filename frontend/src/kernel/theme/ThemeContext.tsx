/**
 * Enterprise Theme Context & UIThemeSettings Token Engine.
 * Supports dynamic CSS variable injection and multi-theme switching with zero page reload.
 */

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';

export type VisualTheme = 'sovereign-dark' | 'enterprise-light' | 'high-density-erp' | 'nordic-minimal';
export type DisplayDensity = 'comfortable' | 'compact';

export interface UIThemeContextType {
  theme: VisualTheme;
  density: DisplayDensity;
  brandColor: string;
  wireframeMode: boolean;
  setTheme: (theme: VisualTheme) => void;
  toggleTheme: () => void;
  setDensity: (density: DisplayDensity) => void;
  setBrandColor: (color: string) => void;
  setWireframeMode: (enabled: boolean | ((prev: boolean) => boolean)) => void;
}

const UIThemeContext = createContext<UIThemeContextType | undefined>(undefined);

const THEME_STORAGE_KEY = 'sovereign_theme';
const DENSITY_STORAGE_KEY = 'sovereign_density';
const WIREFRAME_STORAGE_KEY = 'sovereign_wireframe';

export const UIThemeProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [theme, setThemeState] = useState<VisualTheme>(() => {
    const saved = localStorage.getItem(THEME_STORAGE_KEY);
    return (saved as VisualTheme) || 'sovereign-dark';
  });

  const [density, setDensityState] = useState<DisplayDensity>(() => {
    const saved = localStorage.getItem(DENSITY_STORAGE_KEY);
    return (saved as DisplayDensity) || 'comfortable';
  });

  const [brandColor, setBrandColorState] = useState<string>('#388bfd');

  const [wireframeMode, setWireframeModeState] = useState<boolean>(() => {
    const saved = localStorage.getItem(WIREFRAME_STORAGE_KEY);
    return saved === 'true';
  });

  // Synchronize CSS attributes on root HTML element
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    document.documentElement.setAttribute('data-density', density);
    document.documentElement.style.setProperty('--accent-primary', brandColor);
    localStorage.setItem(THEME_STORAGE_KEY, theme);
    localStorage.setItem(DENSITY_STORAGE_KEY, density);
    localStorage.setItem(WIREFRAME_STORAGE_KEY, String(wireframeMode));
  }, [theme, density, brandColor, wireframeMode]);

  const setTheme = (newTheme: VisualTheme) => {
    setThemeState(newTheme);
  };

  const toggleTheme = () => {
    setThemeState((prev) => (prev === 'sovereign-dark' ? 'enterprise-light' : 'sovereign-dark'));
  };

  const setDensity = (newDensity: DisplayDensity) => {
    setDensityState(newDensity);
  };

  const setBrandColor = (color: string) => {
    setBrandColorState(color);
  };

  const setWireframeMode = (enabled: boolean | ((prev: boolean) => boolean)) => {
    setWireframeModeState((prev) => (typeof enabled === 'function' ? enabled(prev) : enabled));
  };

  return (
    <UIThemeContext.Provider
      value={{
        theme,
        density,
        brandColor,
        wireframeMode,
        setTheme,
        toggleTheme,
        setDensity,
        setBrandColor,
        setWireframeMode,
      }}
    >
      {children}
    </UIThemeContext.Provider>
  );
};

export const useUITheme = (): UIThemeContextType => {
  const context = useContext(UIThemeContext);
  if (!context) {
    throw new Error('useUITheme must be used within a UIThemeProvider');
  }
  return context;
};
