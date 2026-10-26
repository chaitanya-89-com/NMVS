import { AlertCircle, Check, LoaderCircle, RefreshCw } from 'lucide-react'
import { getApiError } from '../api/axios'

export function PageHeader({ eyebrow, title, description, actions }) {
  return (
    <div className="page-header">
      <div>
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {actions && <div className="header-actions">{actions}</div>}
    </div>
  )
}

export function Button({ children, variant = 'primary', className = '', ...props }) {
  return <button className={`button button-${variant} ${className}`} {...props}>{children}</button>
}

export function IconButton({ label, children, ...props }) {
  return <button className="icon-button" aria-label={label} title={label} {...props}>{children}</button>
}

export function RefreshButton({ onClick, loading }) {
  return (
    <Button variant="secondary" onClick={onClick} disabled={loading}>
      <RefreshCw size={16} className={loading ? 'spin' : ''} /> Refresh
    </Button>
  )
}

export function Spinner({ label = 'Loading data…' }) {
  return <div className="state-box"><LoaderCircle className="spin" size={22} />{label}</div>
}

export function ErrorState({ error, retry }) {
  return (
    <div className="state-box state-error">
      <AlertCircle size={19} />
      <span>{getApiError(error)}</span>
      {retry && <Button variant="ghost" onClick={retry}>Try again</Button>}
    </div>
  )
}

export function EmptyState({ title = 'No data available', children }) {
  return <div className="empty-state"><div className="empty-icon"><Check size={19} /></div><strong>{title}</strong>{children && <p>{children}</p>}</div>
}

export function MetricCard({ label, value, detail, icon: Icon, tone = 'cyan' }) {
  return (
    <article className="metric-card">
      <div className={`metric-icon tone-${tone}`}>{Icon && <Icon size={18} />}</div>
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value ?? '—'}</div>
      {detail && <div className="metric-detail">{detail}</div>}
    </article>
  )
}

export function StatusBadge({ status }) {
  const state = String(status || 'unknown').toLowerCase()
  const known = ['online', 'active', 'resolved', 'acknowledged'].includes(state) ? state : ['offline', 'critical'].includes(state) ? 'offline' : 'unknown'
  return <span className={`status-badge status-${known}`}><i />{status || 'Unknown'}</span>
}

export function DataTable({ columns, rows, rowKey = 'id', empty = 'No records found' }) {
  return (
    <div className="table-wrap">
      <table>
        <thead><tr>{columns.map((column) => <th key={column.key}>{column.label}</th>)}</tr></thead>
        <tbody>
          {rows?.map((row, index) => <tr key={row[rowKey] ?? index}>{columns.map((column) => <td key={column.key}>{column.render ? column.render(row) : (row[column.key] ?? '—')}</td>)}</tr>)}
        </tbody>
      </table>
      {!rows?.length && <EmptyState title={empty} />}
    </div>
  )
}

export function Notice({ type = 'info', children, onClose }) {
  return <div className={`notice notice-${type}`} role="status">{children}{onClose && <button onClick={onClose} aria-label="Dismiss">×</button>}</div>
}
