import React, { createContext, useContext, useState, useEffect } from 'react';
import { THEMES, applyTheme } from './themeEngine';

const ThemeContext = createContext(null);

const translations = {
  en: {
    system_name: 'Universal AI OS',
    home: 'Home',
    search_placeholder: 'Search apps, records, settings... (⌘K)',
    launchpad: 'App Launcher',
    settings: 'Settings',
    apps: 'Applications',
    notifications: 'Notifications',
    profile: 'Profile',
    logout: 'Log Out',
    themes: 'Theme Engine',
    language: 'Language',
    arabic: 'العربية',
    english: 'English',
    status_online: 'Online',
  },
  ar: {
    system_name: 'نظام الذكاء الاصطناعي الشامل',
    home: 'الرئيسية',
    search_placeholder: 'ابحث في التطبيقات، السجلات، الإعدادات... (⌘K)',
    launchpad: 'قائمة التطبيقات',
    settings: 'الإعدادات',
    apps: 'التطبيقات',
    notifications: 'الإشعارات',
    profile: 'الملف الشخصي',
    logout: 'تسجيل الخروج',
    themes: 'محرك السمات والمظهر',
    language: 'اللغة',
    arabic: 'العربية',
    english: 'English',
    status_online: 'متصل',
  },
};

export function ThemeProvider({ children }) {
  const [themeId, setThemeId] = useState(() => localStorage.getItem('app_theme_id') || 'twitter-lights-out');
  const [language, setLanguageState] = useState(() => localStorage.getItem('app_language') || 'en');

  useEffect(() => {
    applyTheme(themeId);
  }, [themeId]);

  useEffect(() => {
    document.documentElement.setAttribute('lang', language);
    document.documentElement.setAttribute('dir', language === 'ar' ? 'rtl' : 'ltr');
    localStorage.setItem('app_language', language);
  }, [language]);

  const switchTheme = (newThemeId) => {
    if (THEMES[newThemeId]) {
      setThemeId(newThemeId);
      applyTheme(newThemeId);
    }
  };

  const setLanguage = (lang) => {
    setLanguageState(lang);
  };

  const t = (key) => {
    return translations[language]?.[key] || translations['en']?.[key] || key;
  };

  return (
    <ThemeContext.Provider
      value={{
        themeId,
        currentTheme: THEMES[themeId] || THEMES['apple-obsidian'],
        switchTheme,
        allThemes: Object.values(THEMES),
        language,
        setLanguage,
        t,
      }}
    >
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider');
  return ctx;
}
