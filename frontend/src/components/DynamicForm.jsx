import React, { useState } from 'react';
import { useTheme } from '../core/themeContext';

export default function DynamicForm({
  title,
  fields = [],
  initialValues = {},
  onSubmit,
  onCancel,
  loading = false,
}) {
  const { language } = useTheme();
  const [formData, setFormData] = useState(() => {
    const initial = { ...initialValues };
    fields.forEach((f) => {
      if (initial[f.name] === undefined && f.defaultValue !== undefined) {
        initial[f.name] = f.defaultValue;
      }
    });
    return initial;
  });
  const [errors, setErrors] = useState({});

  const handleChange = (name, value) => {
    setFormData((prev) => ({ ...prev, [name]: value }));
    if (errors[name]) {
      setErrors((prev) => ({ ...prev, [name]: null }));
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    const newErrors = {};
    fields.forEach((field) => {
      if (field.required && (formData[field.name] === undefined || formData[field.name] === '')) {
        newErrors[field.name] = language === 'ar' ? 'هذا الحقل مطلوب' : 'This field is required';
      }
    });

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    if (onSubmit) {
      onSubmit(formData);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '18px' }}>
      {title && <h3 style={{ fontSize: '17px', fontWeight: 700, color: 'var(--text-primary)' }}>{title}</h3>}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
        {fields.map((field) => {
          const val = formData[field.name] ?? '';
          const hasError = !!errors[field.name];

          return (
            <div key={field.name} style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>
                {field.label}
                {field.required && <span style={{ color: 'var(--accent-rose)', marginInlineStart: '3px' }}>*</span>}
              </label>

              {/* Text / Number / Email / Password */}
              {['text', 'number', 'email', 'password', 'url'].includes(field.type || 'text') && (
                <input
                  type={field.type || 'text'}
                  value={val}
                  placeholder={field.placeholder || ''}
                  onChange={(e) => handleChange(field.name, field.type === 'number' ? Number(e.target.value) : e.target.value)}
                  className="glass-input"
                  style={{ borderColor: hasError ? 'var(--accent-rose)' : undefined }}
                />
              )}

              {/* Textarea */}
              {field.type === 'textarea' && (
                <textarea
                  rows={4}
                  value={val}
                  placeholder={field.placeholder || ''}
                  onChange={(e) => handleChange(field.name, e.target.value)}
                  className="glass-input"
                  style={{ resize: 'vertical', borderColor: hasError ? 'var(--accent-rose)' : undefined }}
                />
              )}

              {/* Select Dropdown */}
              {field.type === 'select' && (
                <select
                  value={val}
                  onChange={(e) => handleChange(field.name, e.target.value)}
                  className="glass-input"
                  style={{ borderColor: hasError ? 'var(--accent-rose)' : undefined }}
                >
                  <option value="">{language === 'ar' ? '-- اختر --' : '-- Select --'}</option>
                  {(field.options || []).map((opt) => (
                    <option key={opt.value ?? opt} value={opt.value ?? opt}>
                      {opt.label ?? opt}
                    </option>
                  ))}
                </select>
              )}

              {/* Checkbox / Toggle */}
              {field.type === 'checkbox' && (
                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', marginTop: '4px' }}>
                  <input
                    type="checkbox"
                    checked={!!val}
                    onChange={(e) => handleChange(field.name, e.target.checked)}
                    style={{ accentColor: 'var(--accent-primary)', width: '16px', height: '16px' }}
                  />
                  <span style={{ fontSize: '13px', color: 'var(--text-primary)' }}>{field.description || field.label}</span>
                </label>
              )}

              {hasError && (
                <span style={{ fontSize: '11px', color: 'var(--accent-rose)' }}>{errors[field.name]}</span>
              )}
            </div>
          );
        })}
      </div>

      {/* Buttons */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '10px', marginTop: '12px' }}>
        {onCancel && (
          <button type="button" onClick={onCancel} className="glass-button">
            {language === 'ar' ? 'إلغاء' : 'Cancel'}
          </button>
        )}
        <button type="submit" disabled={loading} className="glass-button glass-button-primary">
          {loading ? (language === 'ar' ? 'جاري الحفظ...' : 'Saving...') : (language === 'ar' ? 'حفظ التغييرات' : 'Save Changes')}
        </button>
      </div>
    </form>
  );
}
