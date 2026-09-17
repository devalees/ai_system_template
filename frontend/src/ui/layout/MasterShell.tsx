/**
 * Sovereign Master Shell (Production Layout Engine).
 * Implements the unified "1 Invariant Shell + 4 Polymorphic Canvases" architecture:
 * - Zone 1: Global App Header (48px) with App Launcher, Company Switcher, Cmd+K Command Bar, Theme Switcher.
 * - Zone 2: Module Sub-Navigation (40px) dynamically populated by backend `MenuItem` tree.
 * - Zone 3: Context & Action Control Bar (48px) with Breadcrumbs, Actions, Filter Hub, View Switchers.
 * - Zone 4: Polymorphic Viewport Canvas (Explorer Grid, Document Sheet with Splitter, Reporting, Settings).
 */

import React, { useState, useEffect, useRef } from 'react';
import { fetchUserMenus } from '../../api/menuApi';
import { MenuItemNode } from '../../types/menus';
import { useUITheme, VisualTheme } from '../../kernel/theme/ThemeContext';
import { useCompany } from '../../kernel/company/CompanyContext';
import { useAuth } from '../../kernel/auth/AuthContext';
import { CommandPalette } from './CommandPalette';
import { AppLauncherModal } from './AppLauncherModal';
import { CompanySwitcherModal } from './CompanySwitcherModal';
import {
  LayoutGrid,
  Building2,
  Search,
  Bell,
  Moon,
  Sun,
  ChevronDown,
  Plus,
  Printer,
  CheckCircle2,
  SlidersHorizontal,
  Table as TableIcon,
  FileText,
  BarChart3,
  Settings as SettingsIcon,
  MessageSquare,
  FileCheck,
  Send,
  Calendar,
  Sparkles,
  Eye,
} from 'lucide-react';

type CanvasType = 'explorer' | 'document' | 'reporting' | 'settings';

export const MasterShell: React.FC = () => {
  const { theme, setTheme, wireframeMode, setWireframeMode } = useUITheme();
  const { activeCompany } = useCompany();
  const { user } = useAuth();

  // Navigation & Menu Engine State
  const [menuTree, setMenuTree] = useState<MenuItemNode[]>([]);
  const [activeRootCode, setActiveRootCode] = useState<string>('sales.root');
  const [activeMenuItem, setActiveMenuItem] = useState<MenuItemNode | null>(null);
  const [isLiveBackend, setIsLiveBackend] = useState<boolean>(false);
  const [isLoadingMenus, setIsLoadingMenus] = useState<boolean>(true);

  // Modals & Popovers
  const [isAppLauncherOpen, setIsAppLauncherOpen] = useState<boolean>(false);
  const [isCompanyModalOpen, setIsCompanyModalOpen] = useState<boolean>(false);
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState<boolean>(false);
  const [openCategoryCode, setOpenCategoryCode] = useState<string | null>(null);
  const [isNotificationsOpen, setIsNotificationsOpen] = useState<boolean>(false);
  const [isUserMenuOpen, setIsUserMenuOpen] = useState<boolean>(false);

  // Viewport Canvas State
  const [activeCanvas, setActiveCanvas] = useState<CanvasType>('explorer');
  const [activeTab, setActiveTab] = useState<'lines' | 'accounting' | 'notes'>('lines');
  const [splitterRatio, setSplitterRatio] = useState<number>(65);
  const [isDraggingSplitter, setIsDraggingSplitter] = useState<boolean>(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Load menu hierarchy on mount
  useEffect(() => {
    async function loadMenus() {
      setIsLoadingMenus(true);
      const res = await fetchUserMenus();
      setMenuTree(res.data);
      setIsLiveBackend(res.isLive);
      if (res.data.length > 0) {
        const root = res.data[0];
        setActiveRootCode(root.code);
        const firstCat = root.children.find((c) => c.action_type === 'folder');
        const firstLeaf = firstCat?.children[0] || root.children[0] || null;
        setActiveMenuItem(firstLeaf);
      }
      setIsLoadingMenus(false);
    }
    loadMenus();
  }, []);

  const activeRoot = menuTree.find((r) => r.code === activeRootCode) || menuTree[0];

  const handleSelectRoot = (rootCode: string) => {
    setActiveRootCode(rootCode);
    const root = menuTree.find((r) => r.code === rootCode);
    if (root) {
      const firstCat = root.children.find((c) => c.action_type === 'folder');
      const firstLeaf = firstCat?.children[0] || root.children[0] || null;
      if (firstLeaf) {
        handleSelectMenuItem(firstLeaf);
      } else {
        setActiveMenuItem(null);
      }
    }
    setOpenCategoryCode(null);
  };

  const handleSelectMenuItem = (item: MenuItemNode) => {
    setActiveMenuItem(item);
    setOpenCategoryCode(null);
    if (item.action_type === 'settings' || item.module_name === 'settings') {
      setActiveCanvas('settings');
    } else if (item.action_type === 'report' || item.default_view === 'pivot') {
      setActiveCanvas('reporting');
    } else if (item.default_view === 'form') {
      setActiveCanvas('document');
    } else {
      setActiveCanvas('explorer');
    }
  };

  const findParentCategory = (root: MenuItemNode | undefined, item: MenuItemNode | null) => {
    if (!root || !item) return null;
    for (const cat of root.children) {
      if (cat.children.some((child) => child.code === item.code)) {
        return cat;
      }
    }
    return null;
  };

  const activeCategory = findParentCategory(activeRoot, activeMenuItem);

  // Cycle Visual Themes (UIThemeSettings compliant)
  const cycleTheme = () => {
    const themeSequence: VisualTheme[] = [
      'sovereign-dark',
      'enterprise-light',
      'high-density-erp',
      'nordic-minimal',
    ];
    const currentIndex = themeSequence.indexOf(theme);
    const nextTheme = themeSequence[(currentIndex + 1) % themeSequence.length];
    setTheme(nextTheme);
  };

  // Fluid Splitter Drag Interaction
  const handleSplitterPointerDown = (e: React.PointerEvent) => {
    e.preventDefault();
    setIsDraggingSplitter(true);

    const handlePointerMove = (moveEvent: PointerEvent) => {
      if (!containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const relativeX = moveEvent.clientX - rect.left;
      const percentage = (relativeX / rect.width) * 100;
      // Clamp splitter bounds between 35% and 85%
      const clamped = Math.min(Math.max(percentage, 35), 85);
      setSplitterRatio(Math.round(clamped));
    };

    const handlePointerUp = () => {
      setIsDraggingSplitter(false);
      window.removeEventListener('pointermove', handlePointerMove);
      window.removeEventListener('pointerup', handlePointerUp);
    };

    window.addEventListener('pointermove', handlePointerMove);
    window.addEventListener('pointerup', handlePointerUp);
  };

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        width: '100vw',
        overflow: 'hidden',
        background: 'var(--bg-app)',
        color: 'var(--text-primary)',
      }}
    >
      {/* Top Banner (Wireframe Indicator & Theme Bar) */}
      <div
        style={{
          background: wireframeMode ? 'var(--wf-bg)' : 'var(--bg-surface)',
          borderBottom: '1px solid var(--border-subtle)',
          padding: '4px 16px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          fontSize: '11px',
          transition: 'var(--transition-fast)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {wireframeMode ? (
            <span className="wf-badge" style={{ borderColor: 'var(--accent-primary)', color: 'var(--accent-primary)' }}>
              📐 SKELETON WIREFRAME ACTIVE
            </span>
          ) : (
            <span className="badge badge-primary">
              <Sparkles size={11} /> SOVEREIGN PLATFORM v1.0
            </span>
          )}
          <span style={{ color: 'var(--text-secondary)' }}>
            {wireframeMode
              ? 'Inspecting layout lines and structural zones (Stage 51.2.1)'
              : 'Enterprise metadata-driven UI runtime active (Stage 51.2.2)'}
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            onClick={() => setWireframeMode((prev) => !prev)}
            className="btn btn-secondary btn-sm"
            style={{ fontSize: '11px', padding: '2px 8px' }}
          >
            <Eye size={12} />
            {wireframeMode ? 'Switch to Polished View' : 'Inspect Wireframe Skeleton'}
          </button>
          <button
            onClick={cycleTheme}
            className="btn btn-secondary btn-sm"
            style={{ fontSize: '11px', padding: '2px 8px' }}
          >
            {theme === 'enterprise-light' ? <Sun size={12} /> : <Moon size={12} />}
            Theme: <span style={{ textTransform: 'capitalize' }}>{theme.replace('-', ' ')}</span>
          </button>
        </div>
      </div>

      {/* ====================================================================
          ZONE 1: GLOBAL APP HEADER (48px)
          ==================================================================== */}
      <header
        className={wireframeMode ? 'wf-box' : 'glass-header'}
        style={{
          height: 'var(--header-height)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 16px',
          borderLeft: 'none',
          borderRight: 'none',
          borderTop: 'none',
          zIndex: 50,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {wireframeMode && <span className="wf-badge">Zone 1: Global Header</span>}

          {/* 1.1 App Launcher */}
          <button
            onClick={() => setIsAppLauncherOpen(true)}
            className="btn btn-secondary"
            style={{
              gap: '8px',
              padding: '6px 10px',
              fontWeight: 600,
            }}
            title="Open Application Launcher"
          >
            <LayoutGrid size={15} color="var(--accent-primary)" />
            <span>Applications</span>
            <ChevronDown size={12} color="var(--text-muted)" />
          </button>

          {/* Live Engine Status Badge */}
          <span
            className="badge"
            style={{
              background: isLiveBackend ? 'var(--success-subtle)' : 'var(--warning-subtle)',
              color: isLiveBackend ? 'var(--success)' : 'var(--warning)',
              borderColor: isLiveBackend ? 'var(--success)' : 'var(--warning)',
              fontSize: '10px',
            }}
          >
            {isLiveBackend ? '🟢 Live Menu Engine' : '🟡 System Fixtures'}
          </span>

          {/* 1.2 Company Switcher */}
          <button
            onClick={() => setIsCompanyModalOpen(true)}
            className="btn btn-ghost"
            style={{
              gap: '6px',
              border: '1px solid var(--border-subtle)',
              padding: '5px 10px',
            }}
            title="Switch multi-company tenant context"
          >
            <Building2 size={14} color="var(--accent-primary)" />
            <span style={{ fontWeight: 600, fontSize: '12px' }}>{activeCompany.name}</span>
            <span className="badge badge-neutral" style={{ fontSize: '9px', padding: '1px 5px' }}>
              {activeCompany.currency}
            </span>
            <ChevronDown size={12} color="var(--text-muted)" />
          </button>
        </div>

        {/* 1.3 Universal Command Bar (Cmd+K) */}
        <div
          onClick={() => setIsCommandPaletteOpen(true)}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            width: '380px',
            padding: '6px 12px',
            background: 'var(--bg-card)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-full)',
            cursor: 'pointer',
            boxShadow: 'var(--shadow-sm)',
            transition: 'var(--transition-fast)',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'var(--border-strong)')}
          onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'var(--border-subtle)')}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Search size={14} color="var(--text-muted)" />
            <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
              Search apps, views, documents...
            </span>
          </div>
          <span
            className="badge badge-neutral"
            style={{
              fontSize: '10px',
              fontFamily: 'var(--font-mono)',
              padding: '1px 6px',
            }}
          >
            ⌘K
          </span>
        </div>

        {/* 1.4 Utilities & User Profile */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {/* Notifications */}
          <div style={{ position: 'relative' }}>
            <button
              onClick={() => setIsNotificationsOpen(!isNotificationsOpen)}
              className="btn btn-ghost btn-icon"
              style={{ position: 'relative' }}
              title="Notifications & Activity"
            >
              <Bell size={16} />
              <span
                style={{
                  position: 'absolute',
                  top: '4px',
                  right: '4px',
                  width: '7px',
                  height: '7px',
                  background: 'var(--accent-primary)',
                  borderRadius: '50%',
                }}
              />
            </button>

            {isNotificationsOpen && (
              <div
                className="modal-card"
                style={{
                  position: 'absolute',
                  top: '40px',
                  right: 0,
                  width: '280px',
                  padding: '12px',
                  zIndex: 200,
                }}
              >
                <div style={{ fontSize: '12px', fontWeight: 600, marginBottom: '8px' }}>
                  Notifications (2)
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <div style={{ padding: '6px 8px', background: 'var(--bg-surface)', borderRadius: '4px', fontSize: '11px' }}>
                    <div style={{ fontWeight: 600, color: 'var(--accent-primary)' }}>Order Confirmed</div>
                    <div style={{ color: 'var(--text-muted)' }}>SO-0042 state moved to Confirmed.</div>
                  </div>
                  <div style={{ padding: '6px 8px', background: 'var(--bg-surface)', borderRadius: '4px', fontSize: '11px' }}>
                    <div style={{ fontWeight: 600, color: 'var(--success)' }}>Backup Completed</div>
                    <div style={{ color: 'var(--text-muted)' }}>Nightly database snapshot verified.</div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* User Profile Avatar */}
          <div style={{ position: 'relative' }}>
            <button
              onClick={() => setIsUserMenuOpen(!isUserMenuOpen)}
              className="btn btn-ghost"
              style={{ gap: '8px', padding: '4px 8px' }}
            >
              <div
                style={{
                  width: '26px',
                  height: '26px',
                  borderRadius: '50%',
                  background: 'var(--accent-primary)',
                  color: '#ffffff',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '11px',
                  fontWeight: 700,
                }}
              >
                SA
              </div>
              <span style={{ fontSize: '12px', fontWeight: 600 }}>{user?.full_name || 'Super Admin'}</span>
              <ChevronDown size={12} color="var(--text-muted)" />
            </button>

            {isUserMenuOpen && (
              <div
                className="modal-card"
                style={{
                  position: 'absolute',
                  top: '40px',
                  right: 0,
                  width: '220px',
                  padding: '8px',
                  zIndex: 200,
                }}
              >
                <div style={{ padding: '6px 8px', borderBottom: '1px solid var(--border-subtle)', marginBottom: '4px' }}>
                  <div style={{ fontSize: '12px', fontWeight: 600 }}>{user?.full_name}</div>
                  <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>{user?.email}</div>
                  <span className="badge badge-primary" style={{ fontSize: '9px', marginTop: '4px' }}>
                    Administrator
                  </span>
                </div>
                <button
                  onClick={() => {
                    setActiveCanvas('settings');
                    setIsUserMenuOpen(false);
                  }}
                  className="btn btn-ghost"
                  style={{ width: '100%', justifyContent: 'flex-start', fontSize: '12px' }}
                >
                  <SettingsIcon size={14} /> Profile & Settings
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* ====================================================================
          ZONE 2: MODULE SUB-NAVIGATION (40px)
          ==================================================================== */}
      <nav
        className={wireframeMode ? 'wf-box' : ''}
        style={{
          height: 'var(--subnav-height)',
          display: 'flex',
          alignItems: 'center',
          padding: '0 16px',
          gap: '12px',
          background: 'var(--bg-surface)',
          borderBottom: '1px solid var(--border-subtle)',
          position: 'relative',
        }}
      >
        {wireframeMode && <span className="wf-badge">Zone 2: Dynamic Sub-Nav</span>}

        {/* Root App Switcher Tabs */}
        <div style={{ display: 'flex', gap: '4px', marginRight: '12px' }}>
          {menuTree.map((root) => {
            const isSelected = root.code === activeRootCode;
            return (
              <button
                key={root.code}
                onClick={() => handleSelectRoot(root.code)}
                style={{
                  padding: '4px 10px',
                  fontSize: '12px',
                  fontWeight: isSelected ? 600 : 500,
                  color: isSelected ? 'var(--accent-primary)' : 'var(--text-secondary)',
                  background: isSelected ? 'var(--accent-subtle)' : 'transparent',
                  border: 'none',
                  borderBottom: isSelected ? '2px solid var(--accent-primary)' : '2px solid transparent',
                  borderRadius: 'var(--radius-sm) var(--radius-sm) 0 0',
                  cursor: 'pointer',
                  transition: 'var(--transition-fast)',
                }}
              >
                {root.name}
              </button>
            );
          })}
        </div>

        <div style={{ width: '1px', height: '18px', background: 'var(--border-subtle)' }} />

        {/* Contextual Categories & Leaf Actions */}
        <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
          {isLoadingMenus && (
            <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Loading navigation...</span>
          )}

          {activeRoot?.children.map((cat) => {
            const isCategoryOpen = openCategoryCode === cat.code;
            const hasActiveChild = cat.children.some((child) => child.code === activeMenuItem?.code);

            return (
              <div key={cat.code} style={{ position: 'relative' }}>
                <button
                  onClick={() => setOpenCategoryCode(isCategoryOpen ? null : cat.code)}
                  className="btn btn-ghost"
                  style={{
                    padding: '4px 8px',
                    fontSize: '12px',
                    fontWeight: hasActiveChild ? 600 : 400,
                    color: hasActiveChild ? 'var(--accent-primary)' : 'var(--text-primary)',
                    background: isCategoryOpen || hasActiveChild ? 'var(--bg-hover)' : 'transparent',
                  }}
                >
                  {cat.name} <ChevronDown size={11} />
                </button>

                {/* Dropdown Menu */}
                {isCategoryOpen && (
                  <div
                    className="modal-card"
                    style={{
                      position: 'absolute',
                      top: '34px',
                      left: 0,
                      zIndex: 200,
                      minWidth: '200px',
                      padding: '4px',
                    }}
                  >
                    <div
                      style={{
                        padding: '4px 8px',
                        fontSize: '10px',
                        color: 'var(--text-muted)',
                        textTransform: 'uppercase',
                        fontWeight: 600,
                        letterSpacing: '0.04em',
                      }}
                    >
                      {cat.name} Actions
                    </div>
                    {cat.children.map((leaf) => {
                      const isLeafActive = activeMenuItem?.code === leaf.code;
                      return (
                        <div
                          key={leaf.code}
                          onClick={() => handleSelectMenuItem(leaf)}
                          style={{
                            padding: '6px 10px',
                            fontSize: '12px',
                            borderRadius: 'var(--radius-sm)',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            background: isLeafActive ? 'var(--accent-subtle)' : 'transparent',
                            color: isLeafActive ? 'var(--accent-primary)' : 'var(--text-primary)',
                            fontWeight: isLeafActive ? 600 : 400,
                          }}
                          onMouseEnter={(e) => {
                            if (!isLeafActive) e.currentTarget.style.background = 'var(--bg-hover)';
                          }}
                          onMouseLeave={(e) => {
                            if (!isLeafActive) e.currentTarget.style.background = 'transparent';
                          }}
                        >
                          <span>{leaf.name}</span>
                          <span
                            className="badge badge-neutral"
                            style={{ fontSize: '9px', fontFamily: 'var(--font-mono)' }}
                          >
                            {leaf.default_view}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </nav>

      {/* ====================================================================
          ZONE 3: CONTEXT & ACTION CONTROL BAR (48px)
          ==================================================================== */}
      <div
        className={wireframeMode ? 'wf-box' : ''}
        style={{
          height: 'var(--controlbar-height)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 16px',
          background: 'var(--bg-surface)',
          borderBottom: '1px solid var(--border-subtle)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {wireframeMode && <span className="wf-badge">Zone 3: Control Bar</span>}

          {/* 3.1 Hierarchical Breadcrumbs */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px' }}>
            <span style={{ color: 'var(--text-muted)' }}>{activeRoot?.name || 'Sales'}</span>
            <span style={{ color: 'var(--border-strong)' }}>/</span>
            {activeCategory && (
              <>
                <span style={{ color: 'var(--text-muted)' }}>{activeCategory.name}</span>
                <span style={{ color: 'var(--border-strong)' }}>/</span>
              </>
            )}
            <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
              {activeMenuItem?.name || 'Quotations'}
            </span>
          </div>

          {/* 3.2 Primary Actions */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginLeft: '12px' }}>
            <button className="btn btn-primary btn-sm">
              <Plus size={13} /> New
            </button>
            <button className="btn btn-secondary btn-sm">
              <CheckCircle2 size={13} /> Confirm
            </button>
            <button className="btn btn-secondary btn-sm">
              <Printer size={13} /> Print
            </button>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {/* 3.3 Universal Filter Hub */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            {activeMenuItem?.domain_filter && (
              <span className="badge badge-primary" style={{ fontSize: '11px', fontFamily: 'var(--font-mono)' }}>
                ⚡ Filter: {JSON.stringify(activeMenuItem.domain_filter)}
              </span>
            )}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '4px 8px',
                background: 'var(--bg-card)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-md)',
                fontSize: '12px',
                color: 'var(--text-muted)',
              }}
            >
              <Search size={13} />
              <span>Filter records...</span>
              <SlidersHorizontal size={12} color="var(--text-muted)" />
            </div>
          </div>

          {/* 3.4 Polymorphic View Switcher */}
          <div
            style={{
              display: 'flex',
              padding: '2px',
              background: 'var(--bg-card)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-md)',
              gap: '2px',
            }}
          >
            <button
              onClick={() => setActiveCanvas('explorer')}
              className={`btn btn-sm ${activeCanvas === 'explorer' ? 'btn-primary' : 'btn-ghost'}`}
              style={{ padding: '4px 8px' }}
              title="Table / Data Grid"
            >
              <TableIcon size={13} /> List
            </button>
            <button
              onClick={() => setActiveCanvas('document')}
              className={`btn btn-sm ${activeCanvas === 'document' ? 'btn-primary' : 'btn-ghost'}`}
              style={{ padding: '4px 8px' }}
              title="Document Form Sheet & Splitter"
            >
              <FileText size={13} /> Form
            </button>
            <button
              onClick={() => setActiveCanvas('reporting')}
              className={`btn btn-sm ${activeCanvas === 'reporting' ? 'btn-primary' : 'btn-ghost'}`}
              style={{ padding: '4px 8px' }}
              title="Financial Reporting Ledgers"
            >
              <BarChart3 size={13} /> Reports
            </button>
            <button
              onClick={() => setActiveCanvas('settings')}
              className={`btn btn-sm ${activeCanvas === 'settings' ? 'btn-primary' : 'btn-ghost'}`}
              style={{ padding: '4px 8px' }}
              title="Settings & Configuration"
            >
              <SettingsIcon size={13} /> Settings
            </button>
          </div>
        </div>
      </div>

      {/* ====================================================================
          ZONE 4: THE POLYMORPHIC VIEWPORT CANVAS
          ==================================================================== */}
      <main
        ref={containerRef}
        style={{
          flex: 1,
          overflow: 'hidden',
          padding: '16px',
          background: 'var(--bg-canvas)',
          display: 'flex',
          flexDirection: 'column',
          position: 'relative',
        }}
      >
        {/* CANVAS 1: EXPLORER CANVAS (DATA GRID) */}
        {activeCanvas === 'explorer' && (
          <div
            className={wireframeMode ? 'wf-box' : 'modal-card'}
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              borderRadius: 'var(--radius-lg)',
              overflow: 'hidden',
              background: 'var(--bg-surface)',
            }}
          >
            {/* Grid Header Info */}
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '12px 16px',
                borderBottom: '1px solid var(--border-subtle)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '14px', fontWeight: 600 }}>
                  {activeMenuItem?.name || 'Quotations'}
                </span>
                <span className="badge badge-neutral" style={{ fontSize: '10px' }}>
                  Model: {activeMenuItem?.res_model || 'SaleOrder'}
                </span>
              </div>
              <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                Showing 4 of 24 records | 0 selected
              </span>
            </div>

            {/* Table Header Row */}
            <div
              style={{
                padding: '8px 16px',
                display: 'grid',
                gridTemplateColumns: '40px 140px 240px 140px 130px 120px 1fr',
                gap: '8px',
                alignItems: 'center',
                fontWeight: 600,
                fontSize: '12px',
                color: 'var(--text-secondary)',
                background: 'var(--bg-surface-elevated)',
                borderBottom: '1px solid var(--border-subtle)',
              }}
            >
              <input type="checkbox" />
              <span>Order #</span>
              <span>Customer / Partner</span>
              <span>Order Date</span>
              <span>Total Amount</span>
              <span>Status</span>
              <span style={{ textAlign: 'right' }}>Actions</span>
            </div>

            {/* Mock Data Rows */}
            <div style={{ flex: 1, overflowY: 'auto' }}>
              {[
                { id: 'SO-0042', partner: 'Sovereign Holding Corp', date: '2026-09-17', total: '$14,250.00', status: 'Confirmed', badge: 'badge-success' },
                { id: 'SO-0041', partner: 'Delta Technologies Ltd', date: '2026-09-16', total: '$8,400.00', status: 'Draft', badge: 'badge-neutral' },
                { id: 'SO-0040', partner: 'Apex Global Logistics', date: '2026-09-15', total: '$32,100.00', status: 'Invoiced', badge: 'badge-primary' },
                { id: 'SO-0039', partner: 'Zenith Health Systems', date: '2026-09-14', total: '$5,120.00', status: 'Done', badge: 'badge-success' },
              ].map((row, idx) => (
                <div
                  key={row.id}
                  onClick={() => setActiveCanvas('document')}
                  style={{
                    padding: '10px 16px',
                    display: 'grid',
                    gridTemplateColumns: '40px 140px 240px 140px 130px 120px 1fr',
                    gap: '8px',
                    alignItems: 'center',
                    fontSize: '13px',
                    cursor: 'pointer',
                    background: idx % 2 === 0 ? 'var(--bg-surface)' : 'var(--bg-canvas)',
                    borderBottom: '1px solid var(--border-subtle)',
                    transition: 'var(--transition-fast)',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--bg-hover)')}
                  onMouseLeave={(e) =>
                    (e.currentTarget.style.background = idx % 2 === 0 ? 'var(--bg-surface)' : 'var(--bg-canvas)')
                  }
                >
                  <input type="checkbox" onClick={(e) => e.stopPropagation()} />
                  <span style={{ color: 'var(--accent-primary)', fontWeight: 600 }}>{row.id}</span>
                  <span style={{ fontWeight: 500 }}>{row.partner}</span>
                  <span style={{ color: 'var(--text-secondary)' }}>{row.date}</span>
                  <span style={{ fontWeight: 600, fontFamily: 'var(--font-mono)' }}>{row.total}</span>
                  <span className={`badge ${row.badge}`} style={{ width: 'fit-content' }}>
                    {row.status}
                  </span>
                  <span style={{ textAlign: 'right', color: 'var(--text-muted)', fontSize: '11px' }}>
                    Open Form ➔
                  </span>
                </div>
              ))}
            </div>

            {/* Pagination Footer */}
            <div
              style={{
                padding: '8px 16px',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                fontSize: '12px',
                borderTop: '1px solid var(--border-subtle)',
                background: 'var(--bg-surface)',
              }}
            >
              <span style={{ color: 'var(--text-secondary)' }}>Page 1 of 6 (24 records)</span>
              <div style={{ display: 'flex', gap: '6px' }}>
                <button className="btn btn-secondary btn-sm" disabled>
                  Previous
                </button>
                <button className="btn btn-secondary btn-sm">Next</button>
              </div>
            </div>
          </div>
        )}

        {/* CANVAS 2: DOCUMENT CANVAS (FORM SHEET + FLUID SPLITTER + DOCKED CHATTER) */}
        {activeCanvas === 'document' && (
          <div style={{ flex: 1, display: 'flex', gap: '10px', height: '100%', overflow: 'hidden' }}>
            {/* Primary Document Sheet (Left) */}
            <div
              className={wireframeMode ? 'wf-box' : 'modal-card'}
              style={{
                width: `${splitterRatio}%`,
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                overflowY: 'auto',
                background: 'var(--bg-surface)',
                borderRadius: 'var(--radius-lg)',
                padding: '16px',
              }}
            >
              {/* Document Header & State */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginBottom: '16px',
                }}
              >
                <div>
                  <h1 style={{ fontSize: '18px', fontWeight: 700 }}>SO-0042</h1>
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                    Sales Order & Quotation Sheet
                  </span>
                </div>
                <div style={{ display: 'flex', gap: '6px' }}>
                  <span className="badge badge-success">State: Confirmed</span>
                  <span className="badge badge-primary">Invoice Status: To Invoice</span>
                </div>
              </div>

              {/* Document Action Ribbon */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '8px 12px',
                  background: 'var(--bg-card)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-md)',
                  marginBottom: '16px',
                }}
              >
                <div style={{ display: 'flex', gap: '6px' }}>
                  <button className="btn btn-primary btn-sm">Create Invoice</button>
                  <button className="btn btn-secondary btn-sm">Send by Email</button>
                  <button className="btn btn-danger btn-sm">Cancel Order</button>
                </div>

                {/* Pipeline Arrow Progression */}
                <div style={{ display: 'flex', gap: '4px', fontSize: '11px', fontWeight: 600 }}>
                  <span className="badge badge-neutral" style={{ opacity: 0.5 }}>
                    Draft ➔
                  </span>
                  <span className="badge badge-neutral" style={{ opacity: 0.5 }}>
                    Sent ➔
                  </span>
                  <span className="badge badge-primary">Confirmed ➔</span>
                  <span className="badge badge-neutral" style={{ opacity: 0.5 }}>
                    Done
                  </span>
                </div>
              </div>

              {/* 2-Column Header Fields */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 1fr',
                  gap: '16px',
                  padding: '16px',
                  background: 'var(--bg-card)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-md)',
                  marginBottom: '16px',
                }}
              >
                <div>
                  <label style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Customer</label>
                  <div style={{ fontSize: '14px', fontWeight: 600 }}>Sovereign Holding Corp (US-8492)</div>
                </div>
                <div>
                  <label style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Order Date</label>
                  <div style={{ fontSize: '13px' }}>2026-09-17</div>
                </div>
                <div>
                  <label style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Payment Terms</label>
                  <div style={{ fontSize: '13px' }}>Net 30 Days</div>
                </div>
                <div>
                  <label style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Operating Currency</label>
                  <div style={{ fontSize: '13px', fontWeight: 600 }}>USD ($)</div>
                </div>
              </div>

              {/* Tabbed Notebook */}
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                <div
                  style={{
                    display: 'flex',
                    gap: '12px',
                    borderBottom: '1px solid var(--border-subtle)',
                    marginBottom: '12px',
                  }}
                >
                  <button
                    onClick={() => setActiveTab('lines')}
                    style={{
                      padding: '6px 12px',
                      fontSize: '12px',
                      fontWeight: activeTab === 'lines' ? 600 : 400,
                      color: activeTab === 'lines' ? 'var(--accent-primary)' : 'var(--text-secondary)',
                      background: 'transparent',
                      border: 'none',
                      borderBottom: activeTab === 'lines' ? '2px solid var(--accent-primary)' : 'none',
                      cursor: 'pointer',
                    }}
                  >
                    Order Lines (3)
                  </button>
                  <button
                    onClick={() => setActiveTab('accounting')}
                    style={{
                      padding: '6px 12px',
                      fontSize: '12px',
                      fontWeight: activeTab === 'accounting' ? 600 : 400,
                      color: activeTab === 'accounting' ? 'var(--accent-primary)' : 'var(--text-secondary)',
                      background: 'transparent',
                      border: 'none',
                      borderBottom: activeTab === 'accounting' ? '2px solid var(--accent-primary)' : 'none',
                      cursor: 'pointer',
                    }}
                  >
                    Accounting & Taxes
                  </button>
                  <button
                    onClick={() => setActiveTab('notes')}
                    style={{
                      padding: '6px 12px',
                      fontSize: '12px',
                      fontWeight: activeTab === 'notes' ? 600 : 400,
                      color: activeTab === 'notes' ? 'var(--accent-primary)' : 'var(--text-secondary)',
                      background: 'transparent',
                      border: 'none',
                      borderBottom: activeTab === 'notes' ? '2px solid var(--accent-primary)' : 'none',
                      cursor: 'pointer',
                    }}
                  >
                    Internal Notes
                  </button>
                </div>

                {activeTab === 'lines' && (
                  <div
                    style={{
                      flex: 1,
                      display: 'flex',
                      flexDirection: 'column',
                      background: 'var(--bg-card)',
                      border: '1px solid var(--border-subtle)',
                      borderRadius: 'var(--radius-md)',
                      padding: '12px',
                    }}
                  >
                    <div
                      style={{
                        display: 'grid',
                        gridTemplateColumns: '2fr 1fr 1fr 1fr 1fr',
                        gap: '8px',
                        fontWeight: 600,
                        fontSize: '11px',
                        color: 'var(--text-secondary)',
                        marginBottom: '8px',
                      }}
                    >
                      <span>Product</span>
                      <span>Quantity</span>
                      <span>Unit Price</span>
                      <span>Taxes</span>
                      <span style={{ textAlign: 'right' }}>Subtotal</span>
                    </div>

                    {[
                      { item: 'Industrial Cloud Server Rack', qty: '2 Units', price: '$4,500.00', tax: '15% VAT', subtotal: '$9,000.00' },
                      { item: 'High-Density Switch 48-Port', qty: '3 Units', price: '$1,200.00', tax: '15% VAT', subtotal: '$3,600.00' },
                      { item: 'Deployment & Setup Service', qty: '1 Eng.', price: '$1,650.00', tax: '0%', subtotal: '$1,650.00' },
                    ].map((line, lidx) => (
                      <div
                        key={lidx}
                        style={{
                          display: 'grid',
                          gridTemplateColumns: '2fr 1fr 1fr 1fr 1fr',
                          gap: '8px',
                          fontSize: '12px',
                          padding: '6px 0',
                          borderBottom: '1px solid var(--border-subtle)',
                        }}
                      >
                        <span style={{ fontWeight: 500 }}>{line.item}</span>
                        <span>{line.qty}</span>
                        <span style={{ fontFamily: 'var(--font-mono)' }}>{line.price}</span>
                        <span>{line.tax}</span>
                        <span style={{ textAlign: 'right', fontWeight: 600, fontFamily: 'var(--font-mono)' }}>
                          {line.subtotal}
                        </span>
                      </div>
                    ))}

                    <div
                      style={{
                        marginTop: 'auto',
                        textAlign: 'right',
                        paddingTop: '16px',
                        fontSize: '13px',
                      }}
                    >
                      <span style={{ color: 'var(--text-secondary)' }}>Untaxed: $14,250.00 | Tax: $1,890.00 | </span>
                      <span style={{ fontWeight: 700, color: 'var(--accent-primary)', fontSize: '15px' }}>
                        Total: $16,140.00
                      </span>
                    </div>
                  </div>
                )}

                {activeTab === 'accounting' && (
                  <div style={{ padding: '16px', background: 'var(--bg-card)', borderRadius: 'var(--radius-md)', fontSize: '12px' }}>
                    <div><strong>Fiscal Position:</strong> Standard Domestic Enterprise</div>
                    <div style={{ marginTop: '8px' }}><strong>Analytic Account:</strong> {activeCompany.name} / Operations</div>
                    <div style={{ marginTop: '8px' }}><strong>Revenue Account:</strong> 400000 Product Sales</div>
                  </div>
                )}

                {activeTab === 'notes' && (
                  <div style={{ padding: '16px', background: 'var(--bg-card)', borderRadius: 'var(--radius-md)' }}>
                    <textarea
                      className="input-control"
                      rows={4}
                      defaultValue="Customer requested expedited dispatch before end of fiscal quarter."
                    />
                  </div>
                )}
              </div>
            </div>

            {/* Native Pointer-Drag Fluid Splitter Bar */}
            <div
              onPointerDown={handleSplitterPointerDown}
              style={{
                width: '12px',
                height: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'col-resize',
                userSelect: 'none',
                background: isDraggingSplitter ? 'var(--accent-subtle)' : 'transparent',
                borderRadius: 'var(--radius-sm)',
                transition: 'background 120ms',
              }}
              title="Drag or click to adjust layout splitter ratio"
            >
              <div
                style={{
                  width: '4px',
                  height: '32px',
                  borderRadius: '2px',
                  background: isDraggingSplitter ? 'var(--accent-primary)' : 'var(--border-strong)',
                }}
              />
            </div>

            {/* Right: Docked Chatter & Activity Feed */}
            <div
              className={wireframeMode ? 'wf-box' : 'modal-card'}
              style={{
                width: `${100 - splitterRatio}%`,
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                background: 'var(--bg-surface)',
                borderRadius: 'var(--radius-lg)',
                padding: '16px',
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginBottom: '12px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <MessageSquare size={16} color="var(--accent-primary)" />
                  <span style={{ fontSize: '13px', fontWeight: 600 }}>Docked Chatter</span>
                </div>
                <span className="badge badge-neutral" style={{ fontSize: '10px' }}>
                  {100 - splitterRatio}% Dock
                </span>
              </div>

              <div style={{ display: 'flex', gap: '6px', marginBottom: '12px' }}>
                <button className="btn btn-secondary btn-sm" style={{ flex: 1 }}>
                  <Send size={12} /> Message
                </button>
                <button className="btn btn-secondary btn-sm" style={{ flex: 1 }}>
                  <FileCheck size={12} /> Note
                </button>
                <button className="btn btn-secondary btn-sm" style={{ flex: 1 }}>
                  <Calendar size={12} /> Activity
                </button>
              </div>

              {/* History Messages */}
              <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <div
                  style={{
                    padding: '10px',
                    background: 'var(--bg-card)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-md)',
                    fontSize: '12px',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                    <span style={{ fontWeight: 600, color: 'var(--accent-primary)' }}>System Automator</span>
                    <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>02:15 AM</span>
                  </div>
                  <div style={{ color: 'var(--text-secondary)', fontSize: '11px' }}>
                    State transitioned: Draft ➔ Confirmed. Inventory allocation reserved.
                  </div>
                </div>

                <div
                  style={{
                    padding: '10px',
                    background: 'var(--bg-card)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-md)',
                    fontSize: '12px',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                    <span style={{ fontWeight: 600 }}>Super Admin</span>
                    <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>Yesterday 11:42 PM</span>
                  </div>
                  <div style={{ color: 'var(--text-secondary)', fontSize: '11px' }}>
                    Special corporate discount 5% approved for Sovereign Holding Corp.
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* CANVAS 3: FINANCIAL REPORTING CANVAS */}
        {activeCanvas === 'reporting' && (
          <div
            className={wireframeMode ? 'wf-box' : 'modal-card'}
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              borderRadius: 'var(--radius-lg)',
              background: 'var(--bg-surface)',
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '12px 16px',
                borderBottom: '1px solid var(--border-subtle)',
              }}
            >
              <div>
                <span style={{ fontSize: '15px', fontWeight: 600 }}>
                  Consolidated Financial Ledger (Balance Sheet & P&L)
                </span>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                  Multi-Company Scope: {activeCompany.name} ({activeCompany.currency})
                </div>
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <span className="badge badge-neutral">Fiscal Period: 2026</span>
                <button className="btn btn-primary btn-sm">Export to Excel</button>
              </div>
            </div>

            <div style={{ flex: 1, overflowY: 'auto', padding: '16px' }}>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: '140px 2fr 1fr 1fr 1fr',
                  padding: '8px 12px',
                  fontWeight: 600,
                  fontSize: '12px',
                  color: 'var(--text-secondary)',
                  background: 'var(--bg-surface-elevated)',
                  borderBottom: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-sm)',
                }}
              >
                <span>Account Code</span>
                <span>Account Group</span>
                <span style={{ textAlign: 'right' }}>Initial Balance</span>
                <span style={{ textAlign: 'right' }}>Debit / Credit</span>
                <span style={{ textAlign: 'right' }}>Ending Balance</span>
              </div>

              {[
                { code: '100000', name: '▶ Assets (Current & Fixed Assets)', initial: '$450,000.00', movement: '+$84,200.00', ending: '$534,200.00' },
                { code: '200000', name: '▶ Liabilities (Current & Long-Term)', initial: '$180,000.00', movement: '-$12,000.00', ending: '$168,000.00' },
                { code: '300000', name: '▶ Equity & Retained Earnings', initial: '$270,000.00', movement: '+$96,200.00', ending: '$366,200.00' },
                { code: '400000', name: '▶ Operating Revenue', initial: '$0.00', movement: '+$342,000.00', ending: '$342,000.00' },
                { code: '500000', name: '▶ Cost of Goods Sold (COGS)', initial: '$0.00', movement: '+$182,000.00', ending: '$182,000.00' },
              ].map((acc, aidx) => (
                <div
                  key={aidx}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '140px 2fr 1fr 1fr 1fr',
                    padding: '10px 12px',
                    fontSize: '13px',
                    borderBottom: '1px solid var(--border-subtle)',
                    fontFamily: 'var(--font-mono)',
                  }}
                >
                  <span style={{ color: 'var(--accent-primary)', fontWeight: 600 }}>{acc.code}</span>
                  <span style={{ fontFamily: 'var(--font-sans)', fontWeight: 600 }}>{acc.name}</span>
                  <span style={{ textAlign: 'right', color: 'var(--text-secondary)' }}>{acc.initial}</span>
                  <span style={{ textAlign: 'right' }}>{acc.movement}</span>
                  <span style={{ textAlign: 'right', fontWeight: 700 }}>{acc.ending}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* CANVAS 4: SETTINGS HUB CANVAS (SECTION 6.7 TYPED SETTINGS) */}
        {activeCanvas === 'settings' && (
          <div style={{ flex: 1, display: 'flex', gap: '16px', height: '100%' }}>
            {/* Settings Category Index */}
            <div
              className={wireframeMode ? 'wf-box' : 'modal-card'}
              style={{
                width: '240px',
                padding: '16px',
                borderRadius: 'var(--radius-lg)',
                background: 'var(--bg-surface)',
                display: 'flex',
                flexDirection: 'column',
                gap: '6px',
              }}
            >
              <div style={{ fontSize: '13px', fontWeight: 700, marginBottom: '8px' }}>
                Settings Hub
              </div>
              <div
                style={{
                  padding: '8px 10px',
                  borderRadius: 'var(--radius-md)',
                  background: 'var(--accent-subtle)',
                  color: 'var(--accent-primary)',
                  fontWeight: 600,
                  fontSize: '12px',
                }}
              >
                ● Visual Appearance & UI
              </div>
              <div style={{ padding: '8px 10px', fontSize: '12px', color: 'var(--text-secondary)' }}>
                ○ Security & 2FA Policy
              </div>
              <div style={{ padding: '8px 10px', fontSize: '12px', color: 'var(--text-secondary)' }}>
                ○ Invoicing & Taxes
              </div>
              <div style={{ padding: '8px 10px', fontSize: '12px', color: 'var(--text-secondary)' }}>
                ○ Automated Actions & Hooks
              </div>
            </div>

            {/* Right Settings Form Cards */}
            <div
              className={wireframeMode ? 'wf-box' : 'modal-card'}
              style={{
                flex: 1,
                padding: '20px',
                borderRadius: 'var(--radius-lg)',
                background: 'var(--bg-surface)',
                overflowY: 'auto',
              }}
            >
              <div style={{ marginBottom: '16px' }}>
                <h2 style={{ fontSize: '16px', fontWeight: 700 }}>
                  Section 6.7 Typed ModuleSettings (ui_schema)
                </h2>
                <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                  Declares operational policies and visual appearance via typed Redis JSONB.
                </p>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                <div
                  style={{
                    padding: '14px',
                    background: 'var(--bg-card)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-md)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 600, fontSize: '13px' }}>Default Visual Theme</div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                      Configures the company-wide visual theme preset.
                    </div>
                  </div>
                  <select
                    className="select-control"
                    value={theme}
                    onChange={(e) => setTheme(e.target.value as VisualTheme)}
                  >
                    <option value="sovereign-dark">Sovereign Dark</option>
                    <option value="enterprise-light">Enterprise Light</option>
                    <option value="high-density-erp">High-Density ERP</option>
                    <option value="nordic-minimal">Nordic Minimal</option>
                  </select>
                </div>

                <div
                  style={{
                    padding: '14px',
                    background: 'var(--bg-card)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-md)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 600, fontSize: '13px' }}>Allow User Theme Overrides</div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                      Permit individual users to toggle between dark/light modes independently.
                    </div>
                  </div>
                  <input type="checkbox" defaultChecked={true} />
                </div>

                <div
                  style={{
                    padding: '14px',
                    background: 'var(--bg-card)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-md)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 600, fontSize: '13px' }}>Enforce Two-Factor Authentication (2FA)</div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                      Require all company members to configure RFC 6238 TOTP before accessing financial models.
                    </div>
                  </div>
                  <input type="checkbox" defaultChecked={false} />
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Interactive Modals */}
      <CommandPalette
        isOpen={isCommandPaletteOpen}
        onClose={() => setIsCommandPaletteOpen(false)}
        menuTree={menuTree}
        onSelectMenuItem={handleSelectMenuItem}
        onSelectRoot={handleSelectRoot}
      />

      <AppLauncherModal
        isOpen={isAppLauncherOpen}
        onClose={() => setIsAppLauncherOpen(false)}
        menuTree={menuTree}
        activeRootCode={activeRootCode}
        onSelectRoot={handleSelectRoot}
      />

      <CompanySwitcherModal
        isOpen={isCompanyModalOpen}
        onClose={() => setIsCompanyModalOpen(false)}
      />
    </div>
  );
};

export default MasterShell;
