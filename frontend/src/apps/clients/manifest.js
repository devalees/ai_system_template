import ClientWorkspace from './ClientWorkspace';

export const clientsApp = {
  id: 'clients',
  title: 'Client Management',
  title_ar: 'إدارة حسابات العملاء',
  category: 'Business',
  icon: 'Users',
  gradient: 'linear-gradient(135deg, #0ea5e9 0%, #2563eb 100%)',
  description: 'Enterprise 3-tier client CRM with AI budget progress gauges, 1-to-many users, and document storage.',
  description_ar: 'نظام إدارة حسابات العملاء مع مقاييس ميزانية الذكاء الاصطناعي والمستخدمين وخزينة الملفات.',
  order: 20,
  menus: [
    {
      label: 'Clients',
      label_ar: 'العملاء',
      items: [
        { label: 'All Accounts', label_ar: 'جميع الحسابات', action: 'all_clients' },
        { label: 'Add New Client', label_ar: 'إضافة عميل جديد', action: 'add_client' },
        { label: 'Export Client Roster', label_ar: 'تصدير قائمة العملاء', action: 'export_clients' },
      ],
    },
    {
      label: 'AI Governance',
      label_ar: 'حوكمة الذكاء الاصطناعي',
      items: [
        { label: 'Budget Milestones Audit', label_ar: 'تدقيق محطات الميزانية', action: 'audit_budgets' },
        { label: 'Enable AI for All', label_ar: 'تفعيل الذكاء الاصطناعي للجميع', action: 'enable_ai_all' },
      ],
    },
  ],
  component: ClientWorkspace,
};

export default clientsApp;
