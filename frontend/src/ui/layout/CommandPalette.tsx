/**
 * Universal Command Palette (Cmd+K / Ctrl+K).
 * Instant fuzzy search and keyboard navigation across all modules, menus, views, and actions.
 */

import React, { useState, useEffect, useRef } from 'react';
import { MenuItemNode } from '../../types/menus';
import { Search, Command, ArrowRight, CornerDownLeft, X } from 'lucide-react';

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  menuTree: MenuItemNode[];
  onSelectMenuItem: (item: MenuItemNode) => void;
  onSelectRoot: (rootCode: string) => void;
}

interface SearchableItem {
  id: string;
  title: string;
  subtitle: string;
  category: string;
  iconName?: string | null;
  node: MenuItemNode;
  type: 'action' | 'app';
}

export const CommandPalette: React.FC<CommandPaletteProps> = ({
  isOpen,
  onClose,
  menuTree,
  onSelectMenuItem,
  onSelectRoot,
}) => {
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  // Flatten searchable items from the recursive menu tree
  const items: SearchableItem[] = [];
  menuTree.forEach((root) => {
    items.push({
      id: root.code,
      title: root.name,
      subtitle: `Application (${root.children.length} categories)`,
      category: 'Applications',
      iconName: root.icon,
      node: root,
      type: 'app',
    });

    root.children.forEach((cat) => {
      cat.children.forEach((leaf) => {
        items.push({
          id: leaf.code,
          title: leaf.name,
          subtitle: `${root.name} / ${cat.name} (${leaf.default_view})`,
          category: root.name,
          iconName: leaf.icon,
          node: leaf,
          type: 'action',
        });
      });
    });
  });

  const filteredItems = query.trim()
    ? items.filter(
        (i) =>
          i.title.toLowerCase().includes(query.toLowerCase()) ||
          i.subtitle.toLowerCase().includes(query.toLowerCase())
      )
    : items.slice(0, 10);

  useEffect(() => {
    if (isOpen) {
      setQuery('');
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  // Global keyboard shortcuts (Cmd+K / Ctrl+K and Escape)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        if (isOpen) {
          onClose();
        } else {
          // Open triggered by parent or caller
        }
      } else if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev + 1) % Math.max(1, filteredItems.length));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev - 1 + filteredItems.length) % Math.max(1, filteredItems.length));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const selected = filteredItems[selectedIndex];
      if (selected) {
        if (selected.type === 'app') {
          onSelectRoot(selected.node.code);
        } else {
          onSelectMenuItem(selected.node);
        }
        onClose();
      }
    }
  };

  if (!isOpen) return null;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal-card"
        style={{
          width: '600px',
          maxWidth: '92vw',
          maxHeight: '480px',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search Header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            padding: '14px 16px',
            borderBottom: '1px solid var(--border-subtle)',
          }}
        >
          <Search size={18} color="var(--text-muted)" />
          <input
            ref={inputRef}
            type="text"
            placeholder="Type a command, module, or search query..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            style={{
              flex: 1,
              background: 'transparent',
              border: 'none',
              outline: 'none',
              color: 'var(--text-primary)',
              fontSize: '14px',
              fontFamily: 'inherit',
            }}
          />
          <span
            className="badge badge-neutral"
            style={{ fontSize: '10px', fontFamily: 'var(--font-mono)' }}
          >
            ESC to exit
          </span>
          <button
            onClick={onClose}
            className="btn btn-ghost btn-icon"
            style={{ padding: '2px', color: 'var(--text-muted)' }}
          >
            <X size={16} />
          </button>
        </div>

        {/* Search Results List */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '8px' }}>
          {filteredItems.length === 0 ? (
            <div
              style={{
                padding: '32px 16px',
                textAlign: 'center',
                color: 'var(--text-muted)',
                fontSize: '13px',
              }}
            >
              No matching commands or navigation paths found for "{query}"
            </div>
          ) : (
            filteredItems.map((item, index) => {
              const isSelected = index === selectedIndex;
              return (
                <div
                  key={item.id}
                  onClick={() => {
                    if (item.type === 'app') {
                      onSelectRoot(item.node.code);
                    } else {
                      onSelectMenuItem(item.node);
                    }
                    onClose();
                  }}
                  onMouseEnter={() => setSelectedIndex(index)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '8px 12px',
                    borderRadius: 'var(--radius-md)',
                    background: isSelected ? 'var(--accent-subtle)' : 'transparent',
                    color: isSelected ? 'var(--accent-primary)' : 'var(--text-primary)',
                    cursor: 'pointer',
                    transition: 'var(--transition-fast)',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <div
                      style={{
                        width: '28px',
                        height: '28px',
                        borderRadius: 'var(--radius-sm)',
                        background: 'var(--bg-surface)',
                        border: '1px solid var(--border-subtle)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '12px',
                      }}
                    >
                      {item.type === 'app' ? <Command size={14} /> : <ArrowRight size={14} />}
                    </div>
                    <div>
                      <div style={{ fontSize: '13px', fontWeight: isSelected ? 600 : 500 }}>
                        {item.title}
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                        {item.subtitle}
                      </div>
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span className="badge badge-neutral" style={{ fontSize: '10px' }}>
                      {item.category}
                    </span>
                    {isSelected && <CornerDownLeft size={14} color="var(--accent-primary)" />}
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Footer Shortcut Hints */}
        <div
          style={{
            padding: '8px 16px',
            background: 'var(--bg-surface)',
            borderTop: '1px solid var(--border-subtle)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            fontSize: '11px',
            color: 'var(--text-muted)',
          }}
        >
          <div style={{ display: 'flex', gap: '12px' }}>
            <span>↑↓ Navigate</span>
            <span>↵ Select</span>
            <span>ESC Close</span>
          </div>
          <span>Sovereign Universal Shell</span>
        </div>
      </div>
    </div>
  );
};
