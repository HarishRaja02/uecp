import { useState, useMemo } from 'react';
import { Search, Inbox } from 'lucide-react';

export default function Table({
  columns,
  rows = [],
  empty = 'No records found',
  searchable = false,
  searchPlaceholder = 'Search records...',
  filterKey = null,
}) {
  const [query, setQuery] = useState('');

  const filtered = useMemo(() => {
    if (!searchable || !query.trim()) return rows;
    const q = query.toLowerCase();
    return rows.filter((r) => {
      if (filterKey && r[filterKey]) {
        return String(r[filterKey]).toLowerCase().includes(q);
      }
      return Object.values(r).some((val) =>
        val && typeof val === 'string' && val.toLowerCase().includes(q)
      );
    });
  }, [rows, query, searchable, filterKey]);

  return (
    <div className="table-container">
      {searchable && (
        <div className="table-search-bar">
          <div className="search-input-wrap">
            <Search size={16} className="search-icon" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={searchPlaceholder}
            />
            {query && (
              <button className="search-clear" onClick={() => setQuery('')}>
                ×
              </button>
            )}
          </div>
          <span className="table-count">
            {filtered.length} of {rows.length} {rows.length === 1 ? 'item' : 'items'}
          </span>
        </div>
      )}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              {columns.map((c) => (
                <th key={c.key} style={c.style}>
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.length ? (
              filtered.map((r, i) => (
                <tr key={r.id || i}>
                  {columns.map((c) => (
                    <td key={c.key} style={c.style}>
                      {c.render ? c.render(r) : r[c.key] ?? '—'}
                    </td>
                  ))}
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={columns.length} className="empty-cell">
                  <div className="empty-state">
                    <Inbox size={32} className="empty-icon" />
                    <p>{query ? 'No matching records found' : empty}</p>
                    {query && (
                      <button className="secondary small" onClick={() => setQuery('')}>
                        Clear search
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
