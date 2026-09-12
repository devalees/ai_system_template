import ChatStudio from './ChatStudio';

export const aiStudioApp = {
  id: 'ai_studio',
  title: 'AI Studio',
  title_ar: 'استوديو الذكاء الاصطناعي',
  category: 'Intelligence',
  icon: 'Bot',
  gradient: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #ec4899 100%)',
  description: 'Enterprise multi-modal AI workspace with live voice detection and real-time CLI telemetry.',
  description_ar: 'مساحة عمل متقدمة للذكاء الاصطناعي متعدد الوسائط مع كشف الصوت وقياسات الرموز والتكلفة.',
  order: 10,
  menus: [
    {
      label: 'Session',
      label_ar: 'الجلسة',
      items: [
        { label: 'New Chat Session', label_ar: 'جلسة محادثة جديدة', action: 'new_chat' },
        { label: 'Clear Message History', label_ar: 'مسح سجل الرسائل', action: 'clear_chat' },
        { label: 'Export Transcript (JSON)', label_ar: 'تصدير السجل (JSON)', action: 'export_json' },
      ],
    },
    {
      label: 'Agent Persona',
      label_ar: 'الشخصية الوكيلة',
      items: [
        { label: 'Orchestrator (Chief of Staff)', label_ar: 'المنسق (رئيس الأركان)', action: 'set_orchestrator' },
        { label: 'Cost Controller (Financials)', label_ar: 'مراقب التكاليف والميزانية', action: 'set_cost_controller' },
        { label: 'Security Guard (SecOps)', label_ar: 'الحارس الأمني ومكافحة التهديدات', action: 'set_security_guard' },
        { label: 'Comms Agent (Client Concierge)', label_ar: 'منسق خدمة العملاء والتواصل', action: 'set_comms_agent' },
        { label: 'QA Auditor (Review Gatekeeper)', label_ar: 'مدقق الجودة والامتثال', action: 'set_qa_auditor' },
      ],
    },
    {
      label: 'Telemetry',
      label_ar: 'القياسات',
      items: [
        { label: 'Reset Session Counters', label_ar: 'إعادة ضبط عدادات الجلسة', action: 'reset_telemetry' },
        { label: 'View Spending Breakdown', label_ar: 'عرض تفاصيل الإنفاق', action: 'view_spend' },
      ],
    },
  ],
  component: ChatStudio,
};

export default aiStudioApp;
