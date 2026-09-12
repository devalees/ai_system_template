import React, { useState, useEffect } from 'react';
import { useTheme } from '../../core/themeContext';
import api from '../../core/api';
import {
  CheckSquare,
  Clock,
  PlayCircle,
  AlertCircle,
  CheckCircle2,
  Brain,
  DollarSign,
  Plus,
  ShieldCheck,
  RotateCcw,
} from 'lucide-react';

const INITIAL_TASKS = [
  {
    id: 't-101',
    name: 'Triage & Decompose Q3 Security Objectives',
    profile_name: 'orchestrator',
    status: 'completed',
    reasoning_effort: 'none',
    cost_usd: 0.0014,
    created_at: '2026-09-11 10:30',
  },
  {
    id: 't-102',
    name: 'Audit Session Token Telemetry & Budget Ceilings',
    profile_name: 'cost_controller',
    status: 'completed',
    reasoning_effort: 'low',
    cost_usd: 0.0038,
    created_at: '2026-09-11 11:15',
  },
  {
    id: 't-103',
    name: 'Regex Secret Leak & Tenant Perimeter Scan',
    profile_name: 'security_guard',
    status: 'review',
    reasoning_effort: 'high',
    cost_usd: 0.0082,
    created_at: '2026-09-11 12:45',
  },
  {
    id: 't-104',
    name: 'Dissect & Compile Python AST Syntactic Integrity',
    profile_name: 'qa_auditor',
    status: 'in_progress',
    reasoning_effort: 'high',
    cost_usd: 0.0041,
    created_at: '2026-09-12 01:20',
  },
  {
    id: 't-105',
    name: 'Outbound Client Spend Notification Dispatch',
    profile_name: 'comms_agent',
    status: 'pending',
    reasoning_effort: 'none',
    cost_usd: 0.0,
    created_at: '2026-09-12 02:00',
  },
];

const COLUMNS = [
  { id: 'pending', label: 'Pending Queue', label_ar: 'قيد الانتظار', icon: Clock, color: '#94a3b8' },
  { id: 'in_progress', label: 'In Progress', label_ar: 'جاري التنفيذ', icon: PlayCircle, color: '#38bdf8' },
  { id: 'review', label: 'QA Review Gate', label_ar: 'بوابة تدقيق الجودة', icon: AlertCircle, color: '#f59e0b' },
  { id: 'completed', label: 'Completed', label_ar: 'مكتمل بنجاح', icon: CheckCircle2, color: '#10b981' },
];

export default function TaskWorkspace() {
  const { language } = useTheme();
  const [tasks, setTasks] = useState(INITIAL_TASKS);
  const [verdictFeedback, setVerdictFeedback] = useState('');

  // Fetch live tasks from backend if reachable
  useEffect(() => {
    api.get('/api/tasks/').then((data) => {
      if (data && Array.isArray(data.results)) {
        setTasks(data.results);
      } else if (Array.isArray(data)) {
        setTasks(data);
      }
    }).catch(() => {});
  }, []);

  const handleReviewVerdict = (taskId, verdict) => {
    setTasks((prev) =>
      prev.map((t) => {
        if (t.id === taskId) {
          return {
            ...t,
            status: verdict === 'approved' ? 'completed' : 'in_progress',
          };
        }
        return t;
      })
    );
  };

  return (
    <div style={{ flex: 1, height: 'calc(100vh - 38px)', overflowY: 'auto', padding: '28px 36px 100px', background: 'var(--bg-primary)' }}>
      {/* Header Banner */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
        <div>
          <h2 style={{ fontSize: '20px', fontWeight: 800, color: 'var(--text-primary)' }}>
            {language === 'ar' ? 'لوحة كانبان لمهام الوكلاء الأذكياء' : 'Autonomous Agent Kanban Pipeline'}
          </h2>
          <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
            {language === 'ar'
              ? 'تتبع مهام الأقسام الوكيلة، وتدقيق الجودة، وأحكام الاعتماد الرسمية'
              : 'End-to-end task tracking, reasoning levels, spend accounting, and QA gate verdicts'}
          </p>
        </div>

        <div style={{ display: 'flex', gap: '8px' }}>
          <button className="glass-button glass-button-primary">
            <Plus size={14} />
            <span>{language === 'ar' ? 'إنشاء مهمة جديدة' : 'New Task'}</span>
          </button>
        </div>
      </div>

      {/* Kanban Board Columns */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, minmax(260px, 1fr))',
          gap: '16px',
          alignItems: 'start',
        }}
      >
        {COLUMNS.map((col) => {
          const colTasks = tasks.filter((t) => t.status === col.id);
          const Icon = col.icon;

          return (
            <div
              key={col.id}
              className="glass-panel"
              style={{
                padding: '16px',
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
                minHeight: '480px',
                background: 'rgba(15, 21, 35, 0.5)',
              }}
            >
              {/* Column Title */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Icon size={16} color={col.color} />
                  <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary)' }}>
                    {language === 'ar' ? col.label_ar : col.label}
                  </span>
                </div>
                <span className="badge" style={{ background: 'rgba(255,255,255,0.06)', color: 'var(--text-secondary)' }}>
                  {colTasks.length}
                </span>
              </div>

              {/* Tasks List */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {colTasks.map((task) => (
                  <div
                    key={task.id}
                    className="glass-card"
                    style={{
                      padding: '14px',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '8px',
                    }}
                  >
                    <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)', lineHeight: 1.4 }}>
                      {task.name}
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '11px' }}>
                      <span className="badge badge-indigo">{task.profile_name}</span>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '3px', color: 'var(--accent-purple)' }}>
                        <Brain size={12} />
                        <span style={{ textTransform: 'uppercase', fontWeight: 600 }}>{task.reasoning_effort}</span>
                      </div>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '11px', color: 'var(--text-muted)' }}>
                      <span>{task.created_at}</span>
                      <span style={{ color: 'var(--accent-emerald)', fontWeight: 600 }}>${Number(task.cost_usd || 0).toFixed(4)}</span>
                    </div>

                    {/* Interactive QA Gatekeeper Verdict buttons for tasks in 'review' */}
                    {task.status === 'review' && (
                      <div style={{ display: 'flex', gap: '6px', marginTop: '6px', borderTop: '1px solid var(--border-subtle)', paddingTop: '8px' }}>
                        <button
                          onClick={() => handleReviewVerdict(task.id, 'approved')}
                          className="glass-button"
                          style={{ flex: 1, padding: '4px', fontSize: '11px', background: 'rgba(16, 185, 129, 0.2)', color: '#6ee7b7' }}
                        >
                          <ShieldCheck size={12} />
                          <span>Approve</span>
                        </button>
                        <button
                          onClick={() => handleReviewVerdict(task.id, 'changes_requested')}
                          className="glass-button"
                          style={{ flex: 1, padding: '4px', fontSize: '11px', background: 'rgba(244, 63, 94, 0.2)', color: '#fda4af' }}
                        >
                          <RotateCcw size={12} />
                          <span>Changes</span>
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
