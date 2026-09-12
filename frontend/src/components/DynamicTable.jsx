import React, { useState, useMemo } from 'react';
import { Search, ChevronLeft, ChevronRight, ArrowUpDown, Plus } from 'lucide-react';
import { useTheme } from '../core/themeContext';

export default function DynamicTable({
  title,
  subtitle,
  columns = [],
  data = [],
  onRowClick,
  onAddClick,
  actions = [],
  pageSize = 8,
}) {
  const { language } = useTheme();
  const [search, setSearch] = useState('');
  const [sortKey, setSortKey] = useState('');
  const [sortOrder, setSortOrder] = useState('asc');
  const [page, setPage] = useState(1);

  // If columns are not specified, introspect them from the first record
  const resolvedColumns = useMemo(() => {
    if (columns && columns.length > 0) return columns;
    if (data && data.length > 0) {
      return Object.keys(data[0])
        .filter((k) => !k.startsWith('_') && k !== 'id')
        .map((k) => ({
          key: k,
          label: k.replace(/_/g, ' ').toUpperCase(),
          sortable: true,
        }));
    }
    return [];
  }, [columns, data]);

  // Filtering
  const filteredData = useMemo(() => {
    if (!search.trim()) return data;
    const query = search.toLowerCase();
    return data.filter((row) =>
      Object.values(row).some((val) => String(val).toLowerCase().includes(query))
    );
  }, [data, search]);

  // Sorting
  const sortedData = useMemo(() => {
    if (!sortKey) return filteredData;
    return [...filteredData].sort((a, b) => {
      const valA = a[sortKey];
      const valB = b[sortKey];
      if (valA === valB) return 0;
      if (valA === null || valA === undefined) return 1;
      if (valB === null || valB === undefined) return -1;
      const res = valA > valB ? 1 : -1;
      return sortOrder === 'asc' ? res : -res;
    });
  }, [filteredData, sortKey, sortOrder]);

  // Pagination
  const totalPages = Math.ceil(sortedData.length / pageSize) || 1;
  const paginatedData = useMemo(() => {
    const start = (page - 1) * pageSize;
    return sortedData.slice(start, start + pageSize);
  }, [sortedData, page, pageSize]);

  const toggleSort = (key) => {
    if (sortKey === key) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortOrder('asc');
    }
  };

  return (
    <div className="glass-panel" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {/* Header with Title, Search, and Add Action */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h2 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-primary)' }}>{title}</h2>
          {subtitle && <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>{subtitle}</p>}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
            <Search size={14} style={{ position: 'absolute', left: '10px', color: 'var(--text-muted)' }} />
            <input
              type="text"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              placeholder={language === 'ar' ? 'بحث...' : 'Search records...'}
              className="glass-input"
              style={{ width: '220px', paddingLeft: '32px', height: '34px', fontSize: '12px' }}
            />
          </div>

          {onAddClick && (
            <button onClick={onAddClick} className="glass-button glass-button-primary" style={{ height: '34px' }}>
              <Plus size={14} />
              <span>{language === 'ar' ? 'إضافة جديد' : 'New Record'}</span>
            </button>
          )}
        </div>
      </div>

      {/* Responsive Table Container */}
      <div style={{ overflowX: 'auto', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: language === 'ar' ? 'right' : 'left' }}>
          <thead>
            <tr style={{ background: 'rgba(255, 255, 255, 0.03)', borderBottom: '1px solid var(--border-subtle)' }}>
              {resolvedColumns.map((col) => (
                <th
                  key={col.key}
                  onClick={() => col.sortable !== false && toggleSort(col.key)}
                  style={{
                    padding: '10px 14px',
                    fontSize: '11px',
                    fontWeight: 600,
                    color: 'var(--text-secondary)',
                    letterSpacing: '0.04em',
                    textTransform: 'uppercase',
                    cursor: col.sortable !== false ? 'pointer' : 'default',
                    userSelect: 'none',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span>{col.label}</span>
                    {col.sortable !== false && <ArrowUpDown size={11} color="var(--text-muted)" />}
                  </div>
                </th>
              ))}
              {actions && actions.length > 0 && (
                <th style={{ padding: '10px 14px', fontSize: '11px', fontWeight: 600, color: 'var(--text-secondary)', textAlign: 'center' }}>
                  {language === 'ar' ? 'الإجراءات' : 'ACTIONS'}
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {paginatedData.map((row, rowIdx) => (
              <tr
                key={row.id || rowIdx}
                onClick={() => onRowClick && onRowClick(row)}
                style={{
                  borderBottom: '1px solid var(--border-subtle)',
                  cursor: onRowClick ? 'pointer' : 'default',
                  transition: 'background 0.15s ease',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255, 255, 255, 0.02)')}
                onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
              >
                {resolvedColumns.map((col) => (
                  <td key={col.key} style={{ padding: '12px 14px', fontSize: '13px', color: 'var(--text-primary)' }}>
                    {col.render ? col.render(row[col.key], row) : String(row[col.key] ?? '—')}
                  </td>
                ))}

                {actions && actions.length > 0 && (
                  <td style={{ padding: '12px 14px', textAlign: 'center' }}>
                    <div style={{ display: 'flex', justifyContent: 'center', gap: '6px' }}>
                      {actions.map((act, actIdx) => (
                        <button
                          key={actIdx}
                          onClick={(e) => {
                            e.stopPropagation();
                            act.onClick(row);
                          }}
                          className="glass-button"
                          style={{ padding: '4px 8px', fontSize: '11px', height: '26px' }}
                        >
                          {act.label}
                        </button>
                      ))}
                    </div>
                  </td>
                )}
              </tr>
            ))}

            {paginatedData.length === 0 && (
              <tr>
                <td
                  colSpan={resolvedColumns.length + (actions?.length ? 1 : 0)}
                  style={{ padding: '32px', textAlign: 'center', color: 'var(--text-muted)' }}
                >
                  {language === 'ar' ? 'لا توجد بيانات متاحة' : 'No records found'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination Footer */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '12px', color: 'var(--text-muted)' }}>
        <span>
          {language === 'ar'
            ? `عرض ${paginatedData.length} من ${sortedData.length} سجل`
            : `Showing ${paginatedData.length} of ${sortedData.length} entries`}
        </span>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="glass-button"
            style={{ padding: '4px 8px', opacity: page === 1 ? 0.4 : 1 }}
          >
            <ChevronLeft size={14} />
          </button>
          <span>{page} / {totalPages}</span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="glass-button"
            style={{ padding: '4px 8px', opacity: page === totalPages ? 0.4 : 1 }}
          >
            <ChevronRight size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}
