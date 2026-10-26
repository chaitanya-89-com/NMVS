import { useCallback } from 'react'
import { Activity, ArrowUpRight, Bell, Boxes, CheckCircle2, Clock3, Gauge, Signal, WifiOff } from 'lucide-react'
import { Area, AreaChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { getDashboardOverview } from '../api/dashboard'
import { getAlerts, getAlertsSummary } from '../api/alerts'
import { useRemote } from '../hooks/useRemote'
import { DataTable, ErrorState, MetricCard, PageHeader, RefreshButton, Spinner, StatusBadge } from '../components/common'
import { Link } from 'react-router-dom'

function dateLabel(value) {
  if (!value) return '—'
  return new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export default function Dashboard() {
  const loader = useCallback(() => getDashboardOverview(), [])
  const { data, loading, error, reload } = useRemote(loader, [loader], 30_000)
  const alertsSummaryLoader = useCallback(() => getAlertsSummary(), [])
  const recentAlertsLoader = useCallback(() => getAlerts({ limit: 4 }), [])
  const alertsSummary = useRemote(alertsSummaryLoader, [], 30_000)
  const recentAlerts = useRemote(recentAlertsLoader, [], 30_000)
  const stats = data?.stats
  const history = data?.recent_monitoring || []
  const chartData = [...history].reverse().map((item) => ({
    time: dateLabel(item.checked_at),
    state: String(item.status).toLowerCase() === 'online'
      ? 1
      : String(item.status).toLowerCase() === 'offline'
        ? 0
        : null,
  }))
  const statusData = [
    { name: 'Online', value: stats?.online_devices ?? 0, color: '#40d49d' },
    { name: 'Offline', value: stats?.offline_devices ?? 0, color: '#ff6f78' },
    { name: 'Unknown', value: stats?.unknown_devices ?? 0, color: '#728399' },
  ]
  function refreshDashboard() {
    reload()
    alertsSummary.reload()
    recentAlerts.reload()
  }
  return (
    <>
      <PageHeader eyebrow="NETWORK OPERATIONS / OVERVIEW" title="Good to see you" description={`Device and network status refreshes every 30 seconds while this page is open${data?.generated_at ? ` · updated ${new Date(data.generated_at).toLocaleTimeString()}` : ''}.`} actions={<RefreshButton onClick={refreshDashboard} loading={loading || alertsSummary.loading || recentAlerts.loading} />} />
      {loading && !data ? <Spinner label="Loading dashboard from backend…" /> : error && !data ? <ErrorState error={error} retry={reload} /> : data && <>
        {error && <ErrorState error={error} retry={refreshDashboard} />}
        <div className="metrics-grid dashboard-metrics-grid">
          <MetricCard label="Registered devices" value={stats?.total_devices ?? '—'} detail={`${stats?.total_subnets ?? 0} discovered subnets`} icon={Boxes} tone="cyan" />
          <MetricCard label="Online devices" value={stats?.online_devices ?? '—'} detail={`${stats?.unknown_devices ?? 0} unknown status`} icon={CheckCircle2} tone="green" />
          <MetricCard label="Offline devices" value={stats?.offline_devices ?? '—'} detail="Currently unreachable" icon={WifiOff} tone="red" />
          <MetricCard label="Network health" value={stats?.network_health_score != null ? `${stats.network_health_score}%` : '—'} detail="Backend health score" icon={Activity} tone="amber" />
          <MetricCard label="Active alerts" value={alertsSummary.data?.active_alerts ?? '—'} detail={alertsSummary.error ? 'Alert summary unavailable' : 'From alert summary API'} icon={Bell} tone="red" />
        </div>
        {alertsSummary.error && <ErrorState error={alertsSummary.error} retry={alertsSummary.reload} />}
        <div className="dashboard-grid">
          <section className="panel chart-panel">
            <div className="panel-heading"><div><h2>Monitoring activity</h2><p>Latest backend monitoring checks</p></div><span className="chart-legend"><i /> Reachable</span></div>
            {chartData.length ? <div className="chart-area"><ResponsiveContainer width="100%" height="100%"><AreaChart data={chartData}><defs><linearGradient id="onlineFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="var(--cyan)" stopOpacity={0.3} /><stop offset="95%" stopColor="var(--cyan)" stopOpacity={0} /></linearGradient></defs><CartesianGrid stroke="var(--border-soft)" strokeDasharray="3 5" vertical={false} /><XAxis dataKey="time" tick={{ fill: 'var(--muted)', fontSize: 11 }} axisLine={false} tickLine={false} /><YAxis domain={[0, 1]} ticks={[0, 1]} tickFormatter={(v) => v ? 'Online' : 'Offline'} tick={{ fill: 'var(--muted)', fontSize: 11 }} axisLine={false} tickLine={false} width={56} /><Tooltip contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 10, color: 'var(--text)' }} /><Area dataKey="state" type="stepAfter" stroke="var(--cyan)" fill="url(#onlineFill)" strokeWidth={2} /></AreaChart></ResponsiveContainer></div> : <div className="chart-empty">Monitoring history will appear after backend checks are recorded.</div>}
          </section>
          <section className="panel quick-panel">
            <div className="panel-heading"><div><h2>Quick actions</h2><p>Common operational tasks</p></div></div>
            <div className="quick-links">
              <Link to="/devices"><span className="quick-icon"><Boxes size={17} /></span><span><strong>Manage devices</strong><small>View and update inventory</small></span><ArrowUpRight size={15} /></Link>
              <Link to="/discovery"><span className="quick-icon"><Signal size={17} /></span><span><strong>Discover network</strong><small>Scan an IP range</small></span><ArrowUpRight size={15} /></Link>
              <Link to="/speed"><span className="quick-icon"><Gauge size={17} /></span><span><strong>Run speed test</strong><small>Measure network performance</small></span><ArrowUpRight size={15} /></Link>
              <Link to="/alerts"><span className="quick-icon"><Bell size={17} /></span><span><strong>Review alerts</strong><small>Check active network alerts</small></span><ArrowUpRight size={15} /></Link>
            </div>
          </section>
        </div>
        <section className="panel status-distribution-panel"><div className="panel-heading"><div><h2>Device status distribution</h2><p>Current status counts from dashboard statistics</p></div></div>{stats?.total_devices > 0 ? <div className="status-distribution-content"><div className="status-pie-chart"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={statusData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius="88%" paddingAngle={2} stroke="var(--surface)" strokeWidth={3}>{statusData.map((item) => <Cell key={item.name} fill={item.color} />)}</Pie><Tooltip formatter={(value, name) => [`${value} (${((value / stats.total_devices) * 100).toFixed(0)}%)`, name]} contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 10, color: 'var(--text)' }} labelStyle={{ color: 'var(--text)' }} itemStyle={{ color: 'var(--text)' }} /></PieChart></ResponsiveContainer></div><div className="status-distribution-legend">{statusData.map((item) => <div className="status-distribution-legend-row" key={item.name}><span><i style={{ background: item.color }} />{item.name}</span><strong>{item.value}<small>{((item.value / stats.total_devices) * 100).toFixed(0)}%</small></strong></div>)}</div></div> : <div className="chart-empty">No registered devices to chart.</div>}</section>
        <div className="dashboard-bottom">
          <section className="panel table-panel">
            <div className="panel-heading"><div><h2>Recent monitoring checks</h2><p>Data supplied by the monitoring API</p></div><Link className="text-link" to="/monitoring">View history <ArrowUpRight size={14} /></Link></div>
            <DataTable rows={history.slice(0, 6)} empty="No monitoring activity yet" columns={[
              { key: 'device_name', label: 'Device', render: (row) => <div className="cell-device"><span className="device-dot" /><strong>{row.device_name || row.ip}</strong><small>{row.ip}</small></div> },
              { key: 'status', label: 'Status', render: (row) => <StatusBadge status={row.status} /> },
              { key: 'checked_at', label: 'Checked', render: (row) => <span className="muted-cell"><Clock3 size={13} />{row.checked_at ? new Date(row.checked_at).toLocaleString() : '—'}</span> },
            ]} />
          </section>
          <section className="panel speed-summary">
            <div className="panel-heading"><div><h2>Latest speed test</h2><p>{data.recent_speed_tests?.[0]?.measurement_source === 'device-agent' ? `Measured on ${data.recent_speed_tests[0].ip}` : 'Legacy result; not a per-device measurement'}</p></div><Gauge size={17} /></div>
            {data.recent_speed_tests?.[0] ? <><div className="speed-kpis"><div><small>Download</small><strong>{data.recent_speed_tests[0].download_mbps ?? '—'} <em>Mbps</em></strong></div><div><small>Upload</small><strong>{data.recent_speed_tests[0].upload_mbps ?? '—'} <em>Mbps</em></strong></div></div><div className="speed-footer"><span>{data.recent_speed_tests[0].measurement_source === 'device-agent' ? `Device ${data.recent_speed_tests[0].ip} latency` : 'Legacy latency'}</span><strong>{data.recent_speed_tests[0].ping_ms ?? '—'} ms</strong></div></> : <div className="chart-empty">No saved speed tests yet.</div>}
            <Link className="button button-secondary button-full" to="/speed">Open speed monitoring</Link>
          </section>
        </div>
        <section className="panel recent-alerts-panel"><div className="panel-heading"><div><h2>Recent alerts</h2><p>Latest alert records from the backend</p></div><Link className="text-link" to="/alerts">View alerts <ArrowUpRight size={14} /></Link></div>{recentAlerts.loading && !recentAlerts.data ? <Spinner label="Loading recent alerts…" /> : recentAlerts.error ? <ErrorState error={recentAlerts.error} retry={recentAlerts.reload} /> : recentAlerts.data?.length ? <div className="recent-alert-list">{recentAlerts.data.map((alert) => <div className="recent-alert-item" key={alert.id}><span className={`recent-alert-mark severity-${String(alert.severity).toLowerCase()}`}><Bell size={15} /></span><div><strong>{alert.title || alert.alert_type}</strong><small>{alert.device_name || alert.device_ip} · {alert.created_at ? new Date(alert.created_at).toLocaleString() : '—'}</small></div><StatusBadge status={alert.status} /></div>)}</div> : <div className="chart-empty">No recent alerts.</div>}</section>
        {data.device_types?.length > 0 && <section className="panel device-distribution"><div className="panel-heading"><div><h2>Device mix</h2><p>Registered device types from dashboard API</p></div></div><div className="distribution-list">{data.device_types.map((item) => <div className="distribution-row" key={item.device_type}><span>{item.device_type}</span><span className="distribution-track"><i style={{ width: `${Math.min(100, (item.count / Math.max(...data.device_types.map((v) => v.count), 1)) * 100)}%` }} /></span><strong>{item.count}</strong></div>)}</div></section>}
      </>}
    </>
  )
}
