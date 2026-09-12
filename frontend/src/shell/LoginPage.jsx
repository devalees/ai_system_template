import React, { useState } from 'react';
import { useAuth } from '../core/authContext';
import { useTheme } from '../core/themeContext';
import { Lock, User, ShieldCheck, ArrowRight, AlertCircle } from 'lucide-react';

export default function LoginPage() {
  const { login } = useAuth();
  const { language, setLanguage, currentTheme, switchTheme, allThemes } = useTheme();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    if (!username.trim() || !password) {
      setError(language === 'ar' ? 'يرجى إدخال اسم المستخدم وكلمة المرور' : 'Please enter both username and password');
      return;
    }
    setLoading(true);
    setError('');

    const res = await login(username.trim(), password);
    if (!res.success) {
      setError(res.error || (language === 'ar' ? 'فشل تسجيل الدخول. تأكد من صحة البيانات.' : 'Login failed. Please check your credentials.'));
    }
    setLoading(false);
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        width: '100vw',
        background: 'var(--bg-base)',
        color: 'var(--text-primary)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '20px',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* Background Ambient Glow */}
      <div
        style={{
          position: 'absolute',
          top: '-15%',
          left: '50%',
          transform: 'translateX(-50%)',
          width: '700px',
          height: '400px',
          background: 'radial-gradient(circle, var(--accent-primary) 0%, transparent 70%)',
          opacity: 0.15,
          pointerEvents: 'none',
          filter: 'blur(60px)',
        }}
      />

      {/* Top Controls: Theme & Language Switchers */}
      <div
        style={{
          position: 'absolute',
          top: '20px',
          right: language === 'ar' ? 'auto' : '24px',
          left: language === 'ar' ? '24px' : 'auto',
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          zIndex: 10,
        }}
      >
        <button
          onClick={() => setLanguage(language === 'en' ? 'ar' : 'en')}
          className="glass-button"
          style={{ padding: '4px 10px', fontSize: '11px', fontWeight: 600 }}
        >
          {language === 'en' ? 'العربية' : 'EN'}
        </button>
      </div>

      {/* Login Card */}
      <div
        className="glass-panel"
        style={{
          width: '100%',
          maxWidth: '420px',
          padding: '36px 32px',
          borderRadius: '20px',
          boxShadow: 'var(--shadow-glass), 0 20px 40px rgba(0,0,0,0.3)',
          display: 'flex',
          flexDirection: 'column',
          gap: '24px',
          zIndex: 1,
          animation: 'fadeIn 0.25s ease',
        }}
      >
        {/* Brand Header */}
        <div style={{ textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
          <div
            style={{
              width: '48px',
              height: '48px',
              borderRadius: '14px',
              background: 'linear-gradient(135deg, var(--accent-primary) 0%, var(--accent-secondary, #3b82f6) 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 8px 20px rgba(0,0,0,0.25)',
            }}
          >
            <ShieldCheck size={26} color="#fff" />
          </div>
          <h1 style={{ fontSize: '20px', fontWeight: 700, margin: '8px 0 0', letterSpacing: '-0.02em' }}>
            {language === 'ar' ? 'بوابة المنصة المؤسسية' : 'Enterprise AI OS'}
          </h1>
          <p style={{ fontSize: '12px', color: 'var(--text-secondary)', margin: 0 }}>
            {language === 'ar' ? 'سجّل الدخول للوصول إلى بيئة العمل والخدمات' : 'Sign in to access your workspaces & agents'}
          </p>
        </div>

        {/* Error Alert */}
        {error && (
          <div
            style={{
              background: 'rgba(244, 63, 94, 0.12)',
              border: '1px solid var(--accent-rose, #f43f5e)',
              borderRadius: '10px',
              padding: '10px 14px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              fontSize: '12px',
              color: 'var(--accent-rose, #f43f5e)',
            }}
          >
            <AlertCircle size={16} />
            <span style={{ flex: 1 }}>{error}</span>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>
              {language === 'ar' ? 'اسم المستخدم' : 'Username'}
            </label>
            <div style={{ position: 'relative' }}>
              <User
                size={16}
                style={{
                  position: 'absolute',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  left: language === 'ar' ? 'auto' : '12px',
                  right: language === 'ar' ? '12px' : 'auto',
                  color: 'var(--text-muted)',
                }}
              />
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="admin"
                className="glass-input"
                style={{
                  width: '100%',
                  paddingLeft: language === 'ar' ? '12px' : '36px',
                  paddingRight: language === 'ar' ? '36px' : '12px',
                  boxSizing: 'border-box',
                }}
                disabled={loading}
              />
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>
              {language === 'ar' ? 'كلمة المرور' : 'Password'}
            </label>
            <div style={{ position: 'relative' }}>
              <Lock
                size={16}
                style={{
                  position: 'absolute',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  left: language === 'ar' ? 'auto' : '12px',
                  right: language === 'ar' ? '12px' : 'auto',
                  color: 'var(--text-muted)',
                }}
              />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="glass-input"
                style={{
                  width: '100%',
                  paddingLeft: language === 'ar' ? '12px' : '36px',
                  paddingRight: language === 'ar' ? '36px' : '12px',
                  boxSizing: 'border-box',
                }}
                disabled={loading}
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="glass-button glass-button-primary"
            style={{
              padding: '12px',
              fontSize: '13px',
              fontWeight: 600,
              justifyContent: 'center',
              marginTop: '6px',
            }}
          >
            {loading ? (
              <span>{language === 'ar' ? 'جاري التحقق...' : 'Signing in...'}</span>
            ) : (
              <>
                <span>{language === 'ar' ? 'تسجيل الدخول' : 'Sign In'}</span>
                <ArrowRight size={15} style={{ transform: language === 'ar' ? 'rotate(180deg)' : 'none' }} />
              </>
            )}
          </button>
        </form>

        {/* Footer info */}
        <div style={{ textAlign: 'center', fontSize: '11px', color: 'var(--text-muted)' }}>
          <span>Django REST API: </span>
          <span style={{ color: 'var(--accent-emerald, #10b981)', fontWeight: 600 }}>Connected</span>
        </div>
      </div>
    </div>
  );
}
