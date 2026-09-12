/**
 * Pluggable Theme Engine
 * Defines visual themes that can be dynamically switched and extended in the future.
 */

export const THEMES = {
  'apple-obsidian': {
    id: 'apple-obsidian',
    name: 'Apple Obsidian Glass (Default)',
    name_ar: 'زجاج أوبسيديان أبل (الافتراضي)',
    type: 'dark',
    variables: {
      '--bg-space': '#06080e',
      '--bg-primary': '#090d16',
      '--bg-secondary': '#0f1523',
      '--bg-elevated': '#161e31',
      '--bg-hover': '#1c263d',
      '--bg-glass': 'rgba(15, 21, 35, 0.72)',
      '--bg-glass-heavy': 'rgba(9, 13, 22, 0.88)',
      '--bg-glass-card': 'rgba(22, 30, 49, 0.65)',
      '--text-primary': '#f8fafc',
      '--text-secondary': '#94a3b8',
      '--text-muted': '#64748b',
      '--accent-primary': '#6366f1',
      '--accent-primary-hover': '#4f46e5',
      '--accent-glow': 'rgba(99, 102, 241, 0.3)',
      '--border-subtle': 'rgba(255, 255, 255, 0.08)',
      '--border-glass': 'rgba(255, 255, 255, 0.14)',
      '--radius-squircle': '22px',
      '--radius-card': '14px',
      '--radius-button': '8px',
      '--blur-glass': 'blur(24px) saturate(190%)',
    },
  },
  'apple-frosted-light': {
    id: 'apple-frosted-light',
    name: 'Apple Frosted Light',
    name_ar: 'أبل أبيض ثلجي',
    type: 'light',
    variables: {
      '--bg-space': '#f1f5f9',
      '--bg-primary': '#f8fafc',
      '--bg-secondary': '#ffffff',
      '--bg-elevated': '#f1f5f9',
      '--bg-hover': '#e2e8f0',
      '--bg-glass': 'rgba(255, 255, 255, 0.82)',
      '--bg-glass-heavy': 'rgba(248, 250, 252, 0.94)',
      '--bg-glass-card': 'rgba(255, 255, 255, 0.88)',
      '--text-primary': '#0f172a',
      '--text-secondary': '#475569',
      '--text-muted': '#94a3b8',
      '--accent-primary': '#4f46e5',
      '--accent-primary-hover': '#4338ca',
      '--accent-glow': 'rgba(79, 70, 229, 0.2)',
      '--border-subtle': 'rgba(0, 0, 0, 0.08)',
      '--border-glass': 'rgba(0, 0, 0, 0.12)',
      '--radius-squircle': '22px',
      '--radius-card': '14px',
      '--radius-button': '8px',
      '--blur-glass': 'blur(24px) saturate(190%)',
    },
  },
  'odoo-enterprise': {
    id: 'odoo-enterprise',
    name: 'Odoo Enterprise Purple',
    name_ar: 'أودو إنتربرايز البنفسجي',
    type: 'dark',
    variables: {
      '--bg-space': '#11121d',
      '--bg-primary': '#161726',
      '--bg-secondary': '#1e1f33',
      '--bg-elevated': '#252740',
      '--bg-hover': '#2f314f',
      '--bg-glass': 'rgba(22, 23, 38, 0.85)',
      '--bg-glass-heavy': 'rgba(17, 18, 29, 0.95)',
      '--bg-glass-card': 'rgba(30, 31, 51, 0.8)',
      '--text-primary': '#ffffff',
      '--text-secondary': '#a5a8c7',
      '--text-muted': '#727599',
      '--accent-primary': '#714B67',
      '--accent-primary-hover': '#895B7D',
      '--accent-glow': 'rgba(113, 75, 103, 0.35)',
      '--border-subtle': 'rgba(255, 255, 255, 0.07)',
      '--border-glass': 'rgba(255, 255, 255, 0.12)',
      '--radius-squircle': '16px',
      '--radius-card': '10px',
      '--radius-button': '6px',
      '--blur-glass': 'blur(16px)',
    },
  },
  'cyber-emerald': {
    id: 'cyber-emerald',
    name: 'Cyber Emerald Pro',
    name_ar: 'سايبر الزمرد التقني',
    type: 'dark',
    variables: {
      '--bg-space': '#050c0a',
      '--bg-primary': '#081411',
      '--bg-secondary': '#0c201b',
      '--bg-elevated': '#122c26',
      '--bg-hover': '#183b33',
      '--bg-glass': 'rgba(12, 32, 27, 0.8)',
      '--bg-glass-heavy': 'rgba(5, 12, 10, 0.92)',
      '--bg-glass-card': 'rgba(18, 44, 38, 0.7)',
      '--text-primary': '#ecfdf5',
      '--text-secondary': '#a7f3d0',
      '--text-muted': '#34d399',
      '--accent-primary': '#10b981',
      '--accent-primary-hover': '#059669',
      '--accent-glow': 'rgba(16, 185, 129, 0.35)',
      '--border-subtle': 'rgba(16, 185, 129, 0.15)',
      '--border-glass': 'rgba(16, 185, 129, 0.25)',
      '--radius-squircle': '18px',
      '--radius-card': '12px',
      '--radius-button': '8px',
      '--blur-glass': 'blur(20px)',
    },
  },
};

export function applyTheme(themeId) {
  const theme = THEMES[themeId] || THEMES['apple-obsidian'];
  const root = document.documentElement;

  root.setAttribute('data-theme', theme.type);
  root.setAttribute('data-theme-id', theme.id);

  Object.entries(theme.variables).forEach(([key, val]) => {
    root.style.setProperty(key, val);
  });

  localStorage.setItem('app_theme_id', theme.id);
  return theme;
}
