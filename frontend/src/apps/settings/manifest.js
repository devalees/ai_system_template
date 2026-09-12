import SettingsHub from './SettingsHub';

export const settingsApp = {
  id: 'settings',
  title: 'Settings',
  title_ar: 'الإعدادات الموحدة',
  category: 'Platform',
  icon: 'Sliders',
  gradient: 'linear-gradient(135deg, #475569 0%, #1e293b 100%)',
  description: 'Odoo-style single-screen configuration hub for general options, UI, AI credentials, and security.',
  description_ar: 'مركز إعدادات متكامل على غرار نظام أودو لإدارة الخيارات العامة والواجهة والمفاتيح المشفرة.',
  order: 90,
  menus: [
    {
      label: 'Preferences',
      label_ar: 'التفضيلات',
      items: [
        { label: 'Save All Settings', label_ar: 'حفظ جميع الإعدادات', action: 'save_settings' },
        { label: 'Reset to System Defaults', label_ar: 'استعادة الإعدادات الافتراضية', action: 'reset_defaults' },
      ],
    },
  ],
  component: SettingsHub,
};

export default settingsApp;
