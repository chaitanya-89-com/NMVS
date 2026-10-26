import { useCallback, useState } from 'react'
import { Bell, CheckCheck, CircleAlert, Trash2 } from 'lucide-react'
import { acknowledgeAlert, deleteAlert, getAlerts, getAlertsSummary, resolveAlert } from '../api/alerts'
import { getApiError } from '../api/axios'
import { useRemote } from '../hooks/useRemote'
import { Button, ErrorState, MetricCard, Notice, PageHeader, RefreshButton, Spinner, StatusBadge } from '../components/common'

export default function Alerts() {
  const [status, setStatus] = useState('')
  const [severity, setSeverity] = useState('')
  const alertsLoader = useCallback(() => getAlerts({ limit: 200, ...(status ? { status } : {}), ...(severity ? { severity } : {}) }), [status, severity])
  const summaryLoader = useCallback(() => getAlertsSummary(), [])
  const list = useRemote(alertsLoader, [alertsLoader], 30_000)
  const summary = useRemote(summaryLoader, [], 30_000)
  const [notice, setNotice] = useState('')
  async function action(id, callback, description) {
    try { await callback(id); setNotice(description); list.reload(); summary.reload() }
    catch (e) { setNotice(getApiError(e)) }
  }
  function remove(alert) {
    if (window.confirm(`Delete alert #${alert.id}?`)) action(alert.id, deleteAlert, 'Alert deleted.')
  }
  return <>
    <PageHeader eyebrow="EVENT RESPONSE" title="Alerts" description="Review alert records, acknowledge incidents and resolve completed events." actions={<RefreshButton onClick={() => { list.reload(); summary.reload() }} loading={list.loading || summary.loading} />} />
    {notice && <Notice onClose={() => setNotice('')}>{notice}</Notice>}
    {summary.error && !summary.data ? <ErrorState error={summary.error} retry={summary.reload} /> : <>{summary.error && <ErrorState error={summary.error} retry={summary.reload} />}<div className="metrics-grid metrics-grid-small">
      <MetricCard label="Total alerts" value={summary.data?.total_alerts ?? '—'} icon={Bell} tone="cyan" />
      <MetricCard label="Active alerts" value={summary.data?.active_alerts ?? '—'} icon={CircleAlert} tone="red" />
      <MetricCard label="Critical" value={summary.data?.critical_alerts ?? '—'} icon={CircleAlert} tone="amber" />
      <MetricCard label="Resolved" value={summary.data?.resolved_alerts ?? '—'} icon={CheckCheck} tone="green" />
    </div></>}
    <section className="panel table-panel"><div className="table-toolbar"><div><h2>Alert feed</h2><p>New alert records refresh every 30 seconds; active incident popups poll every 10 seconds.</p></div><div className="table-filters"><select aria-label="Filter by status" value={status} onChange={(e) => setStatus(e.target.value)}><option value="">Any status</option><option value="active">Active</option><option value="acknowledged">Acknowledged</option><option value="resolved">Resolved</option></select><select aria-label="Filter by severity" value={severity} onChange={(e) => setSeverity(e.target.value)}><option value="">Any severity</option><option value="critical">Critical</option><option value="warning">Warning</option><option value="info">Info</option></select></div></div>
      {list.loading && !list.data ? <Spinner /> : list.error && !list.data ? <ErrorState error={list.error} retry={list.reload} /> : <>{list.error && <ErrorState error={list.error} retry={list.reload} />}<div className="alerts-list">{(list.data || []).map((alert) => <article className="alert-row" key={alert.id}><div className={`alert-severity-icon severity-${String(alert.severity).toLowerCase()}`}><CircleAlert size={18} /></div><div className="alert-content"><div className="alert-title-line"><strong>{alert.title || alert.alert_type}</strong><span className={`severity-label severity-text-${String(alert.severity).toLowerCase()}`}>{alert.severity}</span><StatusBadge status={alert.status} /></div><p>{alert.message}</p><div className="alert-meta"><span>{alert.device_name || alert.device_ip}</span><span>{alert.device_ip}</span><span>{alert.created_at ? new Date(alert.created_at).toLocaleString() : '—'}</span></div></div><div className="alert-actions">{alert.status === 'active' && <Button variant="secondary" onClick={() => action(alert.id, acknowledgeAlert, 'Alert acknowledged.')}>Acknowledge</Button>}{['active', 'acknowledged'].includes(String(alert.status).toLowerCase()) && <Button variant="ghost" onClick={() => action(alert.id, resolveAlert, 'Alert resolved.')}>Resolve</Button>}<button className="table-icon-action danger-action" title="Delete alert" onClick={() => remove(alert)}><Trash2 size={15} /></button></div></article>)}{!list.data?.length && <div className="chart-empty">No alerts match these filters.</div>}</div></>}
    </section>
  </>
}
