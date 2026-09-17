import React, { useState, useEffect } from 'react';
import { fetchUserMenus } from '../../api/menuApi';
import { MenuItemNode } from '../../types/menus';

type CanvasType = 'explorer' | 'document' | 'reporting' | 'settings';

export const MasterShellWireframe: React.FC = () => {
  const [theme, setTheme] = useState<'sovereign-dark' | 'enterprise-light'>('sovereign-dark');
  const [activeCanvas, setActiveCanvas] = useState<CanvasType>('explorer');
  const [companyName, setCompanyName] = useState('Acme Corp HQ (Primary)');
  const [activeTab, setActiveTab] = useState<'lines' | 'accounting' | 'notes'>('lines');
  const [splitterRatio, setSplitterRatio] = useState<number>(65);

  // Dynamic Navigation Engine state
  const [menuTree, setMenuTree] = useState<MenuItemNode[]>([]);
  const [activeRootCode, setActiveRootCode] = useState<string>('sales.root');
  const [activeMenuItem, setActiveMenuItem] = useState<MenuItemNode | null>(null);
  const [isLiveBackend, setIsLiveBackend] = useState<boolean>(false);
  const [isAppLauncherOpen, setIsAppLauncherOpen] = useState<boolean>(false);
  const [openCategoryCode, setOpenCategoryCode] = useState<string | null>(null);
  const [isLoadingMenus, setIsLoadingMenus] = useState<boolean>(true);

  useEffect(() => {
    async function loadMenus() {
      setIsLoadingMenus(true);
      const res = await fetchUserMenus();
      setMenuTree(res.data);
      setIsLiveBackend(res.isLive);
      if (res.data.length > 0) {
        const root = res.data[0];
        setActiveRootCode(root.code);
        const firstCategory = root.children.find((c) => c.action_type === 'folder');
        const firstLeaf = firstCategory?.children[0] || root.children[0] || null;
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
    setIsAppLauncherOpen(false);
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

  // Helper to find category parent for active menu item
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

  const toggleCompany = () => {
    setCompanyName((prev) =>
      prev.includes('Primary') ? 'Acme Europe Logistics (Branch 2)' : 'Acme Corp HQ (Primary)'
    );
  };

  const toggleTheme = () => {
    const next = theme === 'sovereign-dark' ? 'enterprise-light' : 'sovereign-dark';
    setTheme(next);
    document.documentElement.setAttribute('data-theme', next);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', width: '100vw', overflow: 'hidden' }}>
      
      {/* ====================================================================
          TOP NOTIFICATION BAR (WIRE-FRAME BANNER)
          ==================================================================== */}
      <div style={{
        background: 'var(--bg-surface)',
        borderBottom: '1px solid var(--border-subtle)',
        padding: '6px 16px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        fontSize: '12px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span className="wf-badge" style={{ background: 'var(--accent-subtle)', color: 'var(--accent-primary)', borderColor: 'var(--accent-primary)' }}>
            📐 SKELETON WIREFRAME MODE
          </span>
          <span style={{ color: 'var(--text-secondary)' }}>
            Stage 51.2.1: Visual layout skeleton review — Pure lines & labels before CSS styling.
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            onClick={toggleTheme}
            style={{
              padding: '3px 10px',
              fontSize: '11px',
              background: 'var(--bg-card)',
              border: '1px solid var(--border-strong)',
              borderRadius: '4px',
              color: 'var(--text-primary)',
              cursor: 'pointer',
              fontWeight: 500,
            }}
          >
            🌓 Switch Theme ({theme === 'sovereign-dark' ? 'Sovereign Dark' : 'Enterprise Light'})
          </button>
        </div>
      </div>

      {/* ====================================================================
          ZONE 1: GLOBAL APP HEADER (48px)
          ==================================================================== */}
      <header className="wf-box" style={{
        height: '48px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 16px',
        borderLeft: 'none',
        borderRight: 'none',
        borderTop: 'none',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span className="wf-badge">Zone 1: Global Header (48px)</span>
          
          {/* 1.1 App Launcher */}
          <div
            onClick={() => setIsAppLauncherOpen(!isAppLauncherOpen)}
            className="wf-box"
            style={{
              padding: '4px 10px',
              borderRadius: '4px',
              cursor: 'pointer',
              background: isAppLauncherOpen ? 'var(--accent-subtle)' : 'transparent',
              borderColor: isAppLauncherOpen ? 'var(--accent-primary)' : 'var(--border-subtle)',
            }}
            title="Open Application Launcher"
          >
            <span className="wf-badge">1.1 App Launcher</span>
            <span style={{ marginLeft: '6px', fontSize: '12px', fontWeight: 600 }}>▦ Apps ▾</span>
          </div>

          {/* Engine Status Badge */}
          <span
            className="wf-badge"
            style={{
              background: isLiveBackend ? 'rgba(16, 185, 129, 0.15)' : 'rgba(245, 158, 11, 0.15)',
              color: isLiveBackend ? 'var(--success)' : '#f59e0b',
              borderColor: isLiveBackend ? 'var(--success)' : '#f59e0b',
            }}
          >
            {isLiveBackend ? '🟢 Live Menu Engine' : '🟡 System Fixtures'}
          </span>

          {/* 1.2 Company Context Switcher */}
          <div
            onClick={toggleCompany}
            className="wf-box"
            style={{ padding: '4px 10px', borderRadius: '4px', cursor: 'pointer' }}
            title="Click to toggle multi-company workspace context"
          >
            <span className="wf-badge">1.2 Company Switcher</span>
            <span style={{ marginLeft: '6px', fontSize: '12px', color: 'var(--accent-primary)', fontWeight: 600 }}>
              🏢 {companyName} ▾
            </span>
          </div>
        </div>

        {/* 1.3 Global Command Bar (Cmd+K) */}
        <div className="wf-box" style={{ padding: '4px 16px', borderRadius: '6px', width: '380px', textAlign: 'center' }}>
          <span className="wf-badge">1.3 Universal Command Bar</span>
          <span style={{ marginLeft: '8px', fontSize: '12px', color: 'var(--text-muted)' }}>
            🔍 Search everything... (Cmd+K)
          </span>
        </div>

        {/* 1.4 Utilities & Profile */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div className="wf-box" style={{ padding: '4px 8px', borderRadius: '4px' }}>
            <span className="wf-badge">1.4 Notifications</span>
            <span style={{ marginLeft: '4px', fontSize: '12px' }}>🔔 3</span>
          </div>
          <div className="wf-box" style={{ padding: '4px 8px', borderRadius: '4px' }}>
            <span className="wf-badge">1.5 User Profile</span>
            <span style={{ marginLeft: '4px', fontSize: '12px', fontWeight: 600 }}>👤 Super Admin</span>
          </div>
        </div>
      </header>

      {/* ====================================================================
          APP LAUNCHER MODAL / DRAWER (DYNAMIC ROOT APPS)
          ==================================================================== */}
      {isAppLauncherOpen && (
        <div
          style={{
            position: 'absolute',
            top: '86px',
            left: '16px',
            zIndex: 1000,
            background: 'var(--bg-card)',
            border: '2px solid var(--border-strong)',
            borderRadius: '8px',
            padding: '16px',
            boxShadow: '0 12px 32px rgba(0, 0, 0, 0.35)',
            width: '380px',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <span style={{ fontSize: '13px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              ▦ Application Launcher
            </span>
            <button
              onClick={() => setIsAppLauncherOpen(false)}
              style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '14px' }}
            >
              ✕
            </button>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '10px' }}>
            {menuTree.map((root) => {
              const isSelected = root.code === activeRootCode;
              return (
                <div
                  key={root.code}
                  onClick={() => handleSelectRoot(root.code)}
                  className="wf-box"
                  style={{
                    padding: '12px',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    background: isSelected ? 'var(--accent-subtle)' : 'var(--bg-surface)',
                    borderColor: isSelected ? 'var(--accent-primary)' : 'var(--border-subtle)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '4px',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span style={{ fontSize: '18px' }}>
                      {root.icon === 'trending-up' ? '📈' : root.icon === 'shopping-cart' ? '🛒' : root.icon === 'book-open' ? '📚' : '⚙️'}
                    </span>
                    <span className="wf-badge" style={{ fontSize: '9px' }}>seq: {root.sequence}</span>
                  </div>
                  <span style={{ fontSize: '13px', fontWeight: 700, color: isSelected ? 'var(--accent-primary)' : 'var(--text-primary)' }}>
                    {root.name}
                  </span>
                  <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
                    {root.children.length} Categories
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ====================================================================
          ZONE 2: MODULE SUB-NAVIGATION (40px) - DYNAMIC BACKEND ENGINE
          ==================================================================== */}
      <nav className="wf-box" style={{
        height: '40px',
        display: 'flex',
        alignItems: 'center',
        padding: '0 16px',
        gap: '8px',
        borderLeft: 'none',
        borderRight: 'none',
        borderTop: 'none',
        position: 'relative',
      }}>
        <span className="wf-badge">Zone 2: Dynamic Sub-Nav (40px)</span>

        {/* Dynamic Root App Switcher Pills */}
        <div style={{ display: 'flex', gap: '4px', marginRight: '16px' }}>
          {menuTree.map((root) => (
            <button
              key={root.code}
              onClick={() => handleSelectRoot(root.code)}
              style={{
                padding: '3px 8px',
                fontSize: '11px',
                textTransform: 'uppercase',
                fontWeight: activeRootCode === root.code ? 700 : 400,
                color: activeRootCode === root.code ? 'var(--accent-primary)' : 'var(--text-secondary)',
                background: activeRootCode === root.code ? 'var(--accent-subtle)' : 'transparent',
                border: activeRootCode === root.code ? '1px solid var(--accent-primary)' : '1px solid transparent',
                borderRadius: '4px',
                cursor: 'pointer',
              }}
            >
              {root.name}
            </button>
          ))}
        </div>

        {/* Dynamic Contextual Categories & Leaf Actions */}
        <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
          {isLoadingMenus && (
            <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Loading menu engine...</span>
          )}

          {activeRoot?.children.map((cat) => {
            const isCategoryOpen = openCategoryCode === cat.code;
            const hasActiveChild = cat.children.some((child) => child.code === activeMenuItem?.code);

            return (
              <div key={cat.code} style={{ position: 'relative' }}>
                <button
                  onClick={() => setOpenCategoryCode(isCategoryOpen ? null : cat.code)}
                  className="wf-box"
                  style={{
                    padding: '3px 8px',
                    fontSize: '12px',
                    fontWeight: hasActiveChild ? 700 : 500,
                    color: hasActiveChild ? 'var(--accent-primary)' : 'var(--text-secondary)',
                    background: hasActiveChild ? 'var(--accent-subtle)' : 'transparent',
                    borderColor: hasActiveChild ? 'var(--accent-primary)' : 'var(--border-subtle)',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                  }}
                >
                  {cat.name} <span style={{ fontSize: '9px' }}>▾</span>
                </button>

                {/* Dropdown Menu for Category */}
                {isCategoryOpen && (
                  <div
                    style={{
                      position: 'absolute',
                      top: '32px',
                      left: 0,
                      zIndex: 900,
                      background: 'var(--bg-card)',
                      border: '1px solid var(--border-strong)',
                      borderRadius: '6px',
                      padding: '4px',
                      minWidth: '180px',
                      boxShadow: '0 8px 24px rgba(0, 0, 0, 0.3)',
                    }}
                  >
                    <div style={{ padding: '4px 8px', fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>
                      {cat.name} Actions
                    </div>
                    {cat.children.map((item) => {
                      const isItemActive = activeMenuItem?.code === item.code;
                      return (
                        <div
                          key={item.code}
                          onClick={() => handleSelectMenuItem(item)}
                          style={{
                            padding: '6px 10px',
                            fontSize: '12px',
                            borderRadius: '4px',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            background: isItemActive ? 'var(--accent-subtle)' : 'transparent',
                            color: isItemActive ? 'var(--accent-primary)' : 'var(--text-primary)',
                            fontWeight: isItemActive ? 600 : 400,
                          }}
                        >
                          <span>{item.name}</span>
                          <span className="wf-badge" style={{ fontSize: '9px' }}>{item.default_view}</span>
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
      <div className="wf-box" style={{
        height: '48px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 16px',
        borderLeft: 'none',
        borderRight: 'none',
        borderTop: 'none',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span className="wf-badge">Zone 3: Control Bar (48px)</span>

          {/* 3.1 Hierarchical Breadcrumbs */}
          <div className="wf-box" style={{ padding: '4px 10px', borderRadius: '4px' }}>
            <span className="wf-badge">3.1 Breadcrumbs</span>
            <span style={{ marginLeft: '6px', fontSize: '12px', fontWeight: 600 }}>
              {activeRoot?.name || 'Sales'} / {activeCategory ? `${activeCategory.name} / ` : ''}{activeMenuItem?.name || 'Quotations'}
            </span>
          </div>

          {/* 3.2 Action Buttons */}
          <div className="wf-box" style={{ padding: '4px 8px', borderRadius: '4px', display: 'flex', gap: '6px' }}>
            <span className="wf-badge">3.2 Action Buttons</span>
            <button style={{ padding: '2px 8px', fontSize: '11px', background: 'var(--accent-primary)', color: '#fff', border: 'none', borderRadius: '3px', fontWeight: 600 }}>
              + New
            </button>
            <button style={{ padding: '2px 8px', fontSize: '11px', background: 'var(--bg-surface)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)', borderRadius: '3px' }}>
              Confirm
            </button>
            <button style={{ padding: '2px 8px', fontSize: '11px', background: 'var(--bg-surface)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)', borderRadius: '3px' }}>
              Print
            </button>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {/* 3.3 Universal Search & Filter */}
          <div className="wf-box" style={{ padding: '4px 10px', borderRadius: '4px', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span className="wf-badge">3.3 Universal Filter Hub</span>
            {activeMenuItem?.domain_filter && (
              <span className="wf-badge" style={{ background: 'var(--accent-subtle)', color: 'var(--accent-primary)', borderColor: 'var(--accent-primary)', fontSize: '10px' }}>
                ⚡ Filter: {JSON.stringify(activeMenuItem.domain_filter)}
              </span>
            )}
            <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
              🔍 Search... | Filters ▾ | Group By ▾
            </span>
          </div>

          {/* 3.4 View-Type Switcher */}
          <div className="wf-box" style={{ padding: '4px 8px', borderRadius: '4px', display: 'flex', gap: '4px' }}>
            <span className="wf-badge">3.4 View Switcher</span>
            <button
              onClick={() => setActiveCanvas('explorer')}
              style={{
                padding: '2px 6px',
                fontSize: '11px',
                background: activeCanvas === 'explorer' ? 'var(--accent-subtle)' : 'transparent',
                border: activeCanvas === 'explorer' ? '1px solid var(--accent-primary)' : '1px solid transparent',
                borderRadius: '3px',
                color: activeCanvas === 'explorer' ? 'var(--accent-primary)' : 'var(--text-secondary)',
                cursor: 'pointer',
              }}
            >
              ▦ List / Table
            </button>
            <button
              onClick={() => setActiveCanvas('document')}
              style={{
                padding: '2px 6px',
                fontSize: '11px',
                background: activeCanvas === 'document' ? 'var(--accent-subtle)' : 'transparent',
                border: activeCanvas === 'document' ? '1px solid var(--accent-primary)' : '1px solid transparent',
                borderRadius: '3px',
                color: activeCanvas === 'document' ? 'var(--accent-primary)' : 'var(--text-secondary)',
                cursor: 'pointer',
              }}
            >
              📄 Form / Sheet
            </button>
            <button
              onClick={() => setActiveCanvas('reporting')}
              style={{
                padding: '2px 6px',
                fontSize: '11px',
                background: activeCanvas === 'reporting' ? 'var(--accent-subtle)' : 'transparent',
                border: activeCanvas === 'reporting' ? '1px solid var(--accent-primary)' : '1px solid transparent',
                borderRadius: '3px',
                color: activeCanvas === 'reporting' ? 'var(--accent-primary)' : 'var(--text-secondary)',
                cursor: 'pointer',
              }}
            >
              ◫ Financial Report
            </button>
            <button
              onClick={() => setActiveCanvas('settings')}
              style={{
                padding: '2px 6px',
                fontSize: '11px',
                background: activeCanvas === 'settings' ? 'var(--accent-subtle)' : 'transparent',
                border: activeCanvas === 'settings' ? '1px solid var(--accent-primary)' : '1px solid transparent',
                borderRadius: '3px',
                color: activeCanvas === 'settings' ? 'var(--accent-primary)' : 'var(--text-secondary)',
                cursor: 'pointer',
              }}
            >
              ⚙ Settings
            </button>
          </div>
        </div>
      </div>

      {/* ====================================================================
          ZONE 4: THE POLYMORPHIC VIEWPORT CANVAS (FLEXIBLE HEIGHT)
          ==================================================================== */}
      <main style={{ flex: 1, overflow: 'hidden', padding: '16px', background: 'var(--bg-canvas)' }}>
        
        {/* ==================================================================
            CANVAS 1 WIREFRAME: EXPLORER CANVAS (LIST & DATA GRID)
            ================================================================== */}
        {activeCanvas === 'explorer' && (
          <div className="wf-box" style={{ height: '100%', display: 'flex', flexDirection: 'column', borderRadius: '8px', padding: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <span className="wf-badge" style={{ fontSize: '13px' }}>
                CANVAS 1: Explorer Canvas (List Table / Data Grid)
              </span>
              <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                [ Model: {activeMenuItem?.res_model || activeRoot?.name || 'SaleOrder'} | Records: 24 | Selection: 0 ]
              </span>
            </div>

            {/* Table Header Row Skeleton */}
            <div className="wf-box" style={{ padding: '8px 12px', display: 'grid', gridTemplateColumns: '40px 140px 220px 140px 120px 120px 1fr', gap: '8px', alignItems: 'center', fontWeight: 600, fontSize: '12px' }}>
              <span>[ ☑ ]</span>
              <span>[ Order # ⇅ ]</span>
              <span>[ Customer / Partner ]</span>
              <span>[ Order Date ]</span>
              <span>[ Total Amount ]</span>
              <span>[ Status Badge ]</span>
              <span style={{ textAlign: 'right' }}>[ Actions ]</span>
            </div>

            {/* Mock Data Rows Skeleton */}
            <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '6px' }}>
              {[
                { id: 'SO-0042', partner: 'Sovereign Holding Corp', date: '2026-09-17', total: '$14,250.00', status: 'Confirmed' },
                { id: 'SO-0041', partner: 'Delta Technologies Ltd', date: '2026-09-16', total: '$8,400.00', status: 'Draft' },
                { id: 'SO-0040', partner: 'Apex Global Logistics', date: '2026-09-15', total: '$32,100.00', status: 'Invoiced' },
                { id: 'SO-0039', partner: 'Zenith Health Systems', date: '2026-09-14', total: '$5,120.00', status: 'Done' },
              ].map((row, idx) => (
                <div
                  key={row.id}
                  onClick={() => setActiveCanvas('document')}
                  className="wf-box"
                  style={{
                    padding: '10px 12px',
                    display: 'grid',
                    gridTemplateColumns: '40px 140px 220px 140px 120px 120px 1fr',
                    gap: '8px',
                    alignItems: 'center',
                    fontSize: '12px',
                    cursor: 'pointer',
                    background: idx % 2 === 0 ? 'var(--bg-subtle)' : 'transparent',
                  }}
                >
                  <input type="checkbox" />
                  <span style={{ color: 'var(--accent-primary)', fontWeight: 600 }}>{row.id}</span>
                  <span>{row.partner}</span>
                  <span style={{ color: 'var(--text-secondary)' }}>{row.date}</span>
                  <span style={{ fontWeight: 600 }}>{row.total}</span>
                  <span className="wf-badge" style={{ width: 'fit-content' }}>{row.status}</span>
                  <span style={{ textAlign: 'right', color: 'var(--text-muted)' }}>[ Click to Open Document ➔ ]</span>
                </div>
              ))}
            </div>

            {/* Pagination Footer Skeleton */}
            <div className="wf-box" style={{ marginTop: '12px', padding: '8px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '12px' }}>
              <span>[ 1-4 of 24 Records ]</span>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button style={{ padding: '2px 8px', fontSize: '11px', background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', borderRadius: '3px' }}>◀ Previous</button>
                <button style={{ padding: '2px 8px', fontSize: '11px', background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', borderRadius: '3px' }}>Next ▶</button>
              </div>
            </div>
          </div>
        )}

        {/* ==================================================================
            CANVAS 2 WIREFRAME: DOCUMENT CANVAS (FORM SHEET + SPLITTER + CHATTER)
            ================================================================== */}
        {activeCanvas === 'document' && (
          <div style={{ height: '100%', display: 'flex', gap: '12px' }}>
            
            {/* Left: Primary Document Sheet */}
            <div
              className="wf-box"
              style={{
                width: `${splitterRatio}%`,
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                borderRadius: '8px',
                padding: '16px',
                overflowY: 'auto',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                <span className="wf-badge" style={{ fontSize: '13px' }}>
                  CANVAS 2: Document Canvas (Primary Form Sheet — {splitterRatio}% Width)
                </span>
                <span className="wf-badge" style={{ color: 'var(--success)' }}>
                  State: Confirmed
                </span>
              </div>

              {/* Status Bar Ribbon Skeleton */}
              <div className="wf-box" style={{ padding: '8px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button style={{ padding: '4px 10px', fontSize: '12px', background: 'var(--accent-primary)', color: '#fff', border: 'none', borderRadius: '4px' }}>
                    Create Invoice
                  </button>
                  <button style={{ padding: '4px 10px', fontSize: '12px', background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', borderRadius: '4px' }}>
                    Send by Email
                  </button>
                  <button style={{ padding: '4px 10px', fontSize: '12px', background: 'var(--bg-surface)', border: '1px solid var(--danger)', color: 'var(--danger)', borderRadius: '4px' }}>
                    Cancel
                  </button>
                </div>

                {/* State Ribbon Arrow Pipeline */}
                <div style={{ display: 'flex', gap: '4px', fontSize: '11px', fontWeight: 600 }}>
                  <span className="wf-badge" style={{ opacity: 0.5 }}>Draft ➔</span>
                  <span className="wf-badge" style={{ opacity: 0.5 }}>Sent ➔</span>
                  <span className="wf-badge" style={{ borderColor: 'var(--accent-primary)', color: 'var(--accent-primary)' }}>Confirmed ➔</span>
                  <span className="wf-badge" style={{ opacity: 0.5 }}>Done</span>
                </div>
              </div>

              {/* Document Header Fields Skeleton (2-Column Grid) */}
              <div className="wf-box" style={{ padding: '16px', marginBottom: '16px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                <div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '4px' }}>[ Customer / Partner ]</div>
                  <div className="wf-box" style={{ padding: '8px', fontSize: '13px', fontWeight: 600 }}>
                    Sovereign Holding Corp (US-8492)
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '4px' }}>[ Order Date ]</div>
                  <div className="wf-box" style={{ padding: '8px', fontSize: '13px' }}>
                    2026-09-17
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '4px' }}>[ Payment Terms ]</div>
                  <div className="wf-box" style={{ padding: '8px', fontSize: '13px' }}>
                    Net 30 Days (Immediate Delivery)
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '4px' }}>[ Currency ]</div>
                  <div className="wf-box" style={{ padding: '8px', fontSize: '13px' }}>
                    USD ($)
                  </div>
                </div>
              </div>

              {/* Tabbed Notebook Skeleton */}
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                <div style={{ display: 'flex', gap: '8px', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '6px', marginBottom: '12px' }}>
                  <button
                    onClick={() => setActiveTab('lines')}
                    style={{
                      padding: '4px 12px',
                      fontSize: '12px',
                      fontWeight: activeTab === 'lines' ? 700 : 400,
                      color: activeTab === 'lines' ? 'var(--accent-primary)' : 'var(--text-secondary)',
                      background: 'transparent',
                      border: 'none',
                      borderBottom: activeTab === 'lines' ? '2px solid var(--accent-primary)' : 'none',
                      cursor: 'pointer',
                    }}
                  >
                    [ Order Lines (3) ]
                  </button>
                  <button
                    onClick={() => setActiveTab('accounting')}
                    style={{
                      padding: '4px 12px',
                      fontSize: '12px',
                      fontWeight: activeTab === 'accounting' ? 700 : 400,
                      color: activeTab === 'accounting' ? 'var(--accent-primary)' : 'var(--text-secondary)',
                      background: 'transparent',
                      border: 'none',
                      borderBottom: activeTab === 'accounting' ? '2px solid var(--accent-primary)' : 'none',
                      cursor: 'pointer',
                    }}
                  >
                    [ Accounting & Invoicing ]
                  </button>
                  <button
                    onClick={() => setActiveTab('notes')}
                    style={{
                      padding: '4px 12px',
                      fontSize: '12px',
                      fontWeight: activeTab === 'notes' ? 700 : 400,
                      color: activeTab === 'notes' ? 'var(--accent-primary)' : 'var(--text-secondary)',
                      background: 'transparent',
                      border: 'none',
                      borderBottom: activeTab === 'notes' ? '2px solid var(--accent-primary)' : 'none',
                      cursor: 'pointer',
                    }}
                  >
                    [ Internal Notes ]
                  </button>
                </div>

                {/* Tab 1: Line Items Table Skeleton */}
                {activeTab === 'lines' && (
                  <div className="wf-box" style={{ flex: 1, padding: '12px', display: 'flex', flexDirection: 'column' }}>
                    <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 1fr 1fr', gap: '8px', fontWeight: 600, fontSize: '11px', marginBottom: '8px' }}>
                      <span>[ Product ]</span>
                      <span>[ Qty ]</span>
                      <span>[ Unit Price ]</span>
                      <span>[ Taxes ]</span>
                      <span style={{ textAlign: 'right' }}>[ Subtotal ]</span>
                    </div>
                    {[
                      { item: 'Industrial Cloud Server Rack', qty: '2 Units', price: '$4,500.00', tax: '15% VAT', subtotal: '$9,000.00' },
                      { item: 'High-Density Switch 48-Port', qty: '3 Units', price: '$1,200.00', tax: '15% VAT', subtotal: '$3,600.00' },
                      { item: 'Deployment & Setup Service', qty: '1 Eng.', price: '$1,650.00', tax: '0%', subtotal: '$1,650.00' },
                    ].map((line, lidx) => (
                      <div key={lidx} className="wf-box" style={{ padding: '6px 8px', display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 1fr 1fr', gap: '8px', fontSize: '12px', marginBottom: '4px' }}>
                        <span>{line.item}</span>
                        <span>{line.qty}</span>
                        <span>{line.price}</span>
                        <span>{line.tax}</span>
                        <span style={{ textAlign: 'right', fontWeight: 600 }}>{line.subtotal}</span>
                      </div>
                    ))}
                    <div style={{ marginTop: 'auto', textAlign: 'right', fontSize: '13px', fontWeight: 700, paddingTop: '12px' }}>
                      Untaxed: $14,250.00 | Tax: $1,890.00 | <span style={{ color: 'var(--accent-primary)' }}>Total: $16,140.00</span>
                    </div>
                  </div>
                )}

                {activeTab === 'accounting' && (
                  <div className="wf-box" style={{ flex: 1, padding: '16px', fontSize: '12px' }}>
                    <div>[ Fiscal Position: Standard Domestic ]</div>
                    <div style={{ marginTop: '8px' }}>[ Analytic Cost Center: {companyName} / Operations ]</div>
                    <div style={{ marginTop: '8px' }}>[ Revenue Account: 400000 Product Sales ]</div>
                  </div>
                )}

                {activeTab === 'notes' && (
                  <div className="wf-box" style={{ flex: 1, padding: '16px', fontSize: '12px' }}>
                    <textarea style={{ width: '100%', height: '100px', background: 'transparent', border: '1px solid var(--border-subtle)', color: 'inherit', padding: '8px' }} defaultValue="Customer requested expedited dispatch before end of fiscal quarter." />
                  </div>
                )}
              </div>
            </div>

            {/* Native Resizable Splitter Line Indicator */}
            <div
              onClick={() => setSplitterRatio((r) => (r === 65 ? 80 : r === 80 ? 50 : 65))}
              className="wf-box"
              style={{
                width: '16px',
                height: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'col-resize',
                userSelect: 'none',
                background: 'var(--bg-surface)',
              }}
              title="Click to cycle splitter ratio (50% / 65% / 80%)"
            >
              <span style={{ writingMode: 'vertical-rl', fontSize: '9px', color: 'var(--wf-label)', letterSpacing: '1px' }}>
                SPLIT ⇄
              </span>
            </div>

            {/* Right: Docked Chatter & Activity Feed Skeleton */}
            <div
              className="wf-box"
              style={{
                width: `${100 - splitterRatio}%`,
                height: '100%',
                borderRadius: '8px',
                padding: '16px',
                display: 'flex',
                flexDirection: 'column',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                <span className="wf-badge" style={{ fontSize: '12px' }}>
                  Docked Chatter & Activity Feed ({100 - splitterRatio}%)
                </span>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>[ Collapsible ]</span>
              </div>

              <div style={{ display: 'flex', gap: '6px', marginBottom: '12px' }}>
                <button style={{ flex: 1, padding: '4px', fontSize: '11px', background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', borderRadius: '3px' }}>
                  ✉ Send Message
                </button>
                <button style={{ flex: 1, padding: '4px', fontSize: '11px', background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', borderRadius: '3px' }}>
                  📝 Log Note
                </button>
                <button style={{ flex: 1, padding: '4px', fontSize: '11px', background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', borderRadius: '3px' }}>
                  📅 Activity
                </button>
              </div>

              {/* Chatter History Messages Skeleton */}
              <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <div className="wf-box" style={{ padding: '8px', fontSize: '11px' }}>
                  <div style={{ fontWeight: 600, color: 'var(--accent-primary)' }}>👤 System Automator</div>
                  <div style={{ color: 'var(--text-secondary)' }}>Order state shifted from Draft ➔ Confirmed.</div>
                  <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '2px' }}>Today 02:15 AM</div>
                </div>
                <div className="wf-box" style={{ padding: '8px', fontSize: '11px' }}>
                  <div style={{ fontWeight: 600, color: 'var(--accent-primary)' }}>👤 Super Admin</div>
                  <div style={{ color: 'var(--text-secondary)' }}>Discount 5% approved for Sovereign Holding Corp.</div>
                  <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '2px' }}>Yesterday 11:42 PM</div>
                </div>
              </div>
            </div>

          </div>
        )}

        {/* ==================================================================
            CANVAS 3 WIREFRAME: REPORTING & FINANCIAL LEDGER
            ================================================================== */}
        {activeCanvas === 'reporting' && (
          <div className="wf-box" style={{ height: '100%', borderRadius: '8px', padding: '16px', display: 'flex', flexDirection: 'column' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <span className="wf-badge" style={{ fontSize: '13px' }}>
                CANVAS 3: Financial & Reporting Canvas (Trial Balance / P&L / Balance Sheet)
              </span>
              <div style={{ display: 'flex', gap: '8px' }}>
                <span className="wf-box" style={{ padding: '4px 10px', fontSize: '12px' }}>[ Period: Fiscal Year 2026 ]</span>
                <span className="wf-box" style={{ padding: '4px 10px', fontSize: '12px' }}>[ Comparison: Previous Period ]</span>
                <button style={{ padding: '4px 10px', fontSize: '12px', background: 'var(--accent-primary)', color: '#fff', border: 'none', borderRadius: '4px' }}>Export to Excel</button>
              </div>
            </div>

            {/* Hierarchical Ledger Table Skeleton */}
            <div style={{ flex: 1, overflowY: 'auto' }}>
              <div className="wf-box" style={{ padding: '8px 12px', display: 'grid', gridTemplateColumns: '140px 2fr 1fr 1fr 1fr', fontWeight: 600, fontSize: '12px', marginBottom: '6px' }}>
                <span>[ Account Code ]</span>
                <span>[ Account Name / Group ]</span>
                <span style={{ textAlign: 'right' }}>[ Initial Balance ]</span>
                <span style={{ textAlign: 'right' }}>[ Debit / Credit ]</span>
                <span style={{ textAlign: 'right' }}>[ Ending Balance ]</span>
              </div>

              {[
                { code: '100000', name: '▶ Assets (Current & Fixed)', initial: '$450,000.00', movement: '+$84,200.00', ending: '$534,200.00' },
                { code: '200000', name: '▶ Liabilities (Current & Long-Term)', initial: '$180,000.00', movement: '-$12,000.00', ending: '$168,000.00' },
                { code: '300000', name: '▶ Equity & Retained Earnings', initial: '$270,000.00', movement: '+$96,200.00', ending: '$366,200.00' },
                { code: '400000', name: '▶ Revenue (Operating)', initial: '$0.00', movement: '+$342,000.00', ending: '$342,000.00' },
                { code: '500000', name: '▶ Cost of Goods Sold (COGS)', initial: '$0.00', movement: '+$182,000.00', ending: '$182,000.00' },
              ].map((acc, aidx) => (
                <div key={aidx} className="wf-box" style={{ padding: '10px 12px', display: 'grid', gridTemplateColumns: '140px 2fr 1fr 1fr 1fr', fontSize: '12px', marginBottom: '4px' }}>
                  <span style={{ color: 'var(--accent-primary)', fontWeight: 600 }}>{acc.code}</span>
                  <span style={{ fontWeight: 600 }}>{acc.name}</span>
                  <span style={{ textAlign: 'right', color: 'var(--text-secondary)' }}>{acc.initial}</span>
                  <span style={{ textAlign: 'right' }}>{acc.movement}</span>
                  <span style={{ textAlign: 'right', fontWeight: 700 }}>{acc.ending}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ==================================================================
            CANVAS 4 WIREFRAME: SETTINGS & CONFIGURATION HUB
            ================================================================== */}
        {activeCanvas === 'settings' && (
          <div style={{ height: '100%', display: 'flex', gap: '16px' }}>
            {/* Left Category Index */}
            <div className="wf-box" style={{ width: '240px', borderRadius: '8px', padding: '16px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <span className="wf-badge" style={{ marginBottom: '8px' }}>Category Index</span>
              <div className="wf-box" style={{ padding: '8px', fontSize: '12px', fontWeight: 600, color: 'var(--accent-primary)' }}>● User Onboarding</div>
              <div className="wf-box" style={{ padding: '8px', fontSize: '12px', color: 'var(--text-secondary)' }}>○ Security & 2FA Policy</div>
              <div className="wf-box" style={{ padding: '8px', fontSize: '12px', color: 'var(--text-secondary)' }}>○ Invoicing & Taxes</div>
              <div className="wf-box" style={{ padding: '8px', fontSize: '12px', color: 'var(--text-secondary)' }}>○ Visual Themes & UI</div>
            </div>

            {/* Right Settings Cards (Section 6.7 ModuleSettings) */}
            <div className="wf-box" style={{ flex: 1, borderRadius: '8px', padding: '16px', overflowY: 'auto' }}>
              <span className="wf-badge" style={{ fontSize: '13px', marginBottom: '16px' }}>
                CANVAS 4: Typed ModuleSettings Hub (Section 6.7 Compliant)
              </span>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '12px' }}>
                <div className="wf-box" style={{ padding: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: '13px' }}>Allow Public Self-Registration</div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Allow external users to create accounts without administrator invitation.</div>
                  </div>
                  <input type="checkbox" defaultChecked={false} />
                </div>

                <div className="wf-box" style={{ padding: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: '13px' }}>Enforce Two-Factor Authentication (2FA)</div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Require all company members to configure RFC 6238 TOTP.</div>
                  </div>
                  <input type="checkbox" defaultChecked={false} />
                </div>

                <div className="wf-box" style={{ padding: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: '13px' }}>Default Visual Theme</div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Sets the organization default appearance mode.</div>
                  </div>
                  <select style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', color: 'inherit', padding: '4px 8px', borderRadius: '4px' }}>
                    <option>Sovereign Dark</option>
                    <option>Enterprise Light</option>
                    <option>High-Density ERP</option>
                    <option>Nordic Minimal</option>
                  </select>
                </div>
              </div>
            </div>
          </div>
        )}

      </main>

    </div>
  );
};
