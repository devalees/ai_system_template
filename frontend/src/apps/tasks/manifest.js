import TaskWorkspace from './TaskWorkspace';

export const tasksApp = {
  id: 'tasks',
  title: 'Task Registry',
  title_ar: 'سجل المهام والمراجعة',
  category: 'Intelligence',
  icon: 'CheckSquare',
  gradient: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
  description: 'Autonomous agent task registry, Kanban board, and QA review verdict gatekeeper.',
  description_ar: 'سجل مهام الوكلاء الأذكياء ولوحة كانبان وبوابة تدقيق الجودة والامتثال.',
  order: 30,
  menus: [
    {
      label: 'Tasks',
      label_ar: 'المهام',
      items: [
        { label: 'All Tasks', label_ar: 'جميع المهام', action: 'all_tasks' },
        { label: 'Pending QA Reviews', label_ar: 'مراجعات الجودة المعلقة', action: 'pending_reviews' },
        { label: 'Create Task', label_ar: 'إنشاء مهمة جديدة', action: 'create_task' },
      ],
    },
  ],
  component: TaskWorkspace,
};

export default tasksApp;
