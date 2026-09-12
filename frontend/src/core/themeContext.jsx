import React, { createContext, useContext, useState, useEffect } from 'react';

const ThemeContext = createContext(null);

const translations = {
  en: {
    system_name: 'Universal AI OS',
    search_placeholder: 'Search apps, tasks, settings... (⌘K)',
    launchpad: 'Launchpad',
    dock: 'Dock',
    settings: 'Settings',
    apps: 'Applications',
    notifications: 'Notifications',
    profile: 'Profile',
    logout: 'Log Out',
    dark_mode: 'Dark Mode',
    light_mode: 'Light Mode',
    language: 'Language',
    arabic: 'العربية',
    english: 'English',
    status_online: 'Online',
    tokens_today: 'Tokens Today',
    budget_remaining: 'Remaining',
  },
  ar: {
    system_name: 'نظام الذكاء الاصطناعي الشامل',
    search_placeholder: 'ابحث في التطبيقات، المهام، الإعدادات... (⌘K)',
    launchpad: 'لوحة التطبيقات',
    dock: 'شريط الوصول السريع',
    settings: 'الإعدادات',
    apps: 'التطبيقات',
    notifications: 'الإشعارات',
    profile: 'الملف الشخصي',
    logout: 'تسجيل الخروج',
    dark_mode: 'الوضع الداكن',
    light_mode: 'الوضع الفاتح',
    language: 'اللغة',
    arabic: 'العربية',
    english: 'English',
    status_online: 'متصل',
    tokens_today: 'رموز اليوم',
    budget_remaining: 'المتبقي',
  },
};

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(() => localStorage.getItem('app_theme') || 'dark');
  const [language, setLanguageState] = useState(() => localStorage.getItem('app_language') || 'en');

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('app_theme', theme);
  }, [theme]);

  useEffect(() => {
    document.documentElement.setAttribute('lang', language);
    document.documentElement.setAttribute('dir', language === 'ar' ? 'rtl' : 'ltr');
    localStorage.setItem('app_language', language);
  }, [language]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'));
  };

  const setLanguage = (lang) => {
    setLanguageState(lang);
  };

  const t = (key) => {
    return translations[language]?.[key] || translations['en']?.[key] || key;
  };

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme, language, setLanguage, t }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider');
  return ctx;
}
