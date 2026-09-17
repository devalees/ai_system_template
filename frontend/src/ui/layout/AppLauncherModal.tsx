/**
 * Application Launcher Grid Modal / Popover.
 * Provides rapid switching between Root System Applications (Sales, Purchases, Accounting, Settings).
 */

import React from 'react';
import { MenuItemNode } from '../../types/menus';
import { TrendingUp, ShoppingCart, BookOpen, Settings, LayoutGrid, X } from 'lucide-react';

interface AppLauncherModalProps {
  isOpen: boolean;
  onClose: () => void;
  menuTree: MenuItemNode[];
  activeRootCode: string;
  onSelectRoot: (rootCode: string) => void;
}

export const AppLauncherModal: React.FC<AppLauncherModalProps> = ({
  isOpen,
  onClose,
  menuTree,
  activeRootCode,
  onSelectRoot,
}) => {
  if (!isOpen) return null;

  const getAppIcon = (iconName?: string | null) => {
    switch (iconName) {
      case 'trending-up':
        return <TrendingUp size={24} color="var(--accent-primary)" />;
      case 'shopping-cart':
        return <ShoppingCart size={24} color="#10b981" />;
      case 'book-open':
        return <BookOpen size={24} color="#f59e0b" />;
      case 'settings':
      default:
        return <Settings size={24} color="#8b5cf6" />;
    }
  };

  const getAppColorGradient = (moduleName: string) => {
    switch (moduleName) {
      case 'sales':
        return 'linear-gradient(135deg, rgba(56, 139, 253, 0.2) 0%, rgba(56, 139, 253, 0.05) 100%)';
      case 'purchases':
        return 'linear-gradient(135deg, rgba(16, 185, 129, 0.2) 0%, rgba(16, 185, 129, 0.05) 100%)';
      case 'accounting':
        return 'linear-gradient(135deg, rgba(245, 158, 11, 0.2) 0%, rgba(245, 158, 11, 0.05) 100%)';
      case 'settings':
      default:
        return 'linear-gradient(135deg, rgba(139, 92, 246, 0.2) 0%, rgba(139, 92, 246, 0.05) 100%)';
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal-card"
        style={{
          width: '520px',
          maxWidth: '92vw',
          padding: '20px',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '16px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <LayoutGrid size={18} color="var(--accent-primary)" />
            <span style={{ fontSize: '15px', fontWeight: 600 }}>Application Launcher</span>
          </div>
          <button
            onClick={onClose}
            className="btn btn-ghost btn-icon"
            style={{ padding: '4px', color: 'var(--text-muted)' }}
          >
            <X size={16} />
          </button>
        </div>

        {/* 2x2 App Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '12px' }}>
          {menuTree.map((root) => {
            const isSelected = root.code === activeRootCode;
            return (
              <div
                key={root.code}
                onClick={() => {
                  onSelectRoot(root.code);
                  onClose();
                }}
                style={{
                  padding: '16px',
                  borderRadius: 'var(--radius-lg)',
                  cursor: 'pointer',
                  background: isSelected ? 'var(--accent-subtle)' : 'var(--bg-surface)',
                  border: `1.5px solid ${isSelected ? 'var(--accent-primary)' : 'var(--border-subtle)'}`,
                  boxShadow: isSelected ? '0 0 0 1px var(--accent-primary)' : 'var(--shadow-sm)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px',
                  transition: 'var(--transition-fast)',
                }}
                onMouseEnter={(e) => {
                  if (!isSelected) e.currentTarget.style.borderColor = 'var(--border-strong)';
                }}
                onMouseLeave={(e) => {
                  if (!isSelected) e.currentTarget.style.borderColor = 'var(--border-subtle)';
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div
                    style={{
                      width: '42px',
                      height: '42px',
                      borderRadius: '10px',
                      background: getAppColorGradient(root.module_name),
                      border: '1px solid var(--border-subtle)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    {getAppIcon(root.icon)}
                  </div>
                  <span
                    className="badge badge-neutral"
                    style={{ fontSize: '10px', fontFamily: 'var(--font-mono)' }}
                  >
                    seq: {root.sequence}
                  </span>
                </div>

                <div>
                  <div
                    style={{
                      fontSize: '14px',
                      fontWeight: 600,
                      color: isSelected ? 'var(--accent-primary)' : 'var(--text-primary)',
                    }}
                  >
                    {root.name}
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                    {root.children.length} Contextual Categories
                  </div>
                </div>

                <div
                  style={{
                    display: 'flex',
                    flexWrap: 'wrap',
                    gap: '4px',
                    marginTop: '4px',
                  }}
                >
                  {root.children.slice(0, 3).map((cat) => (
                    <span
                      key={cat.code}
                      className="badge badge-neutral"
                      style={{ fontSize: '9px', padding: '1px 5px' }}
                    >
                      {cat.name}
                    </span>
                  ))}
                  {root.children.length > 3 && (
                    <span style={{ fontSize: '9px', color: 'var(--text-muted)' }}>
                      +{root.children.length - 3} more
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Footer Hint */}
        <div
          style={{
            marginTop: '16px',
            textAlign: 'center',
            fontSize: '11px',
            color: 'var(--text-muted)',
          }}
        >
          Dynamic RBAC navigation tree loaded via <code>GET /api/v1/ui/menus</code>
        </div>
      </div>
    </div>
  );
};
