import { useCallback, useState } from 'react'
import { Activity, Clock3, Gauge, ShieldCheck } from 'lucide-react'
import { getMetricsSummary, getUptimeMetrics } from '../api/metrics'
import { useRemote } from '../hooks/useRemote'
import { DataTable, ErrorState, MetricCard, PageHeader, RefreshButton, Spinner, StatusBadge } from '../components/common'

export default function Metrics() {
  const [hours, setHours] = useState(24)
  const summaryLoader = useCallback(() => getMetricsSummary(), [])
  const uptimeLoader = useCallback(() => getUptimeMetrics(hours), [hours])
  const summary = useRemote(summaryLoader)
  const uptime = useRemote(uptimeLoader, [uptimeLoader])
  function refresh() { summary.reload(); uptime.reload() }
  return <>
    <PageHeader eyebrow="SYSTEM PERFORMANCE" title="Metrics" description="Availability, latency and bandwidth metrics returned by the backend." actions={<RefreshButton onClick={refresh} loading={summary.loading || uptime.loading} />} />
    {summary.loading && !summary.data ? <Spinner /> : summary.error ? <ErrorState error={summary.error} retry={summary.reload} /> : <div className="metrics-grid">
      <MetricCard label="Network uptime" value={summary.data?.overall_network_uptime != null ? `${summary.data.overall_network_uptime}%` : '—'} detail="Overall monitored availability" icon={ShieldCheck} tone="green" />
      <MetricCard label="Average latency" value={summary.data?.average_latency_ms != null ? `${summary.data.average_latency_ms} ms` : '—'} detail="Backend-reported average" icon={Activity} tone="cyan" />
      <MetricCard label="Average download" value={summary.data?.average_download_mbps != null ? `${summary.data.average_download_mbps} Mbps` : '—'} detail="Network bandwidth" icon={Gauge} tone="purple" />
      <MetricCard label="Devices evaluated" value={summary.data?.total_devices_evaluated ?? '—'} detail={`${summary.data?.healthy_devices_count ?? 0} healthy · ${summary.data?.degraded_devices_count ?? 0} degraded`} icon={Clock3} tone="amber" />
    </div>}
    {summary.data && <section className="metrics-breakdown"><div><small>Healthy</small><strong>{summary.data.healthy_devices_count}</strong></div><div><small>Degraded</small><strong>{summary.data.degraded_devices_count}</strong></div><div><small>Unmonitored</small><strong>{summary.data.unmonitored_devices_count}</strong></div></section>}
    <section className="panel table-panel"><div className="table-toolbar"><div><h2>Device uptime</h2><p>Availability percentage, current status and check counts.</p></div><label className="range-select">Time window<select value={hours} onChange={(e) => setHours(Number(e.target.value))}><option value={24}>Last 24 hours</option><option value={168}>Last 7 days</option><option value={720}>Last 30 days</option></select></label></div>{uptime.loading && !uptime.data ? <Spinner /> : uptime.error ? <ErrorState error={uptime.error} retry={uptime.reload} /> : <DataTable rows={uptime.data || []} columns={[{ key: 'device_name', label: 'Device', render: (row) => <div className="cell-device"><strong>{row.device_name}</strong><small>{row.device_ip}</small></div> }, { key: 'device_type', label: 'Type' }, { key: 'uptime_percentage', label: 'Uptime', render: (row) => row.uptime_percentage == null ? '—' : `${row.uptime_percentage}%` }, { key: 'total_checks', label: 'Checks' }, { key: 'online_checks', label: 'Online' },     { key: 'offline_checks', label: 'Offline' }, { key: 'unknown_checks', label: 'Unknown' }, { key: 'current_status', label: 'Status', render: (row) => <StatusBadge status={row.current_status} /> }]} empty="No uptime metrics returned" />}</section>
  </>
}
