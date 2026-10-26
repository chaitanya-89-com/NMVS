import { useCallback, useMemo, useState } from 'react'
import { Activity, Clock3, RefreshCw, Search, Signal, Timer, Trash2 } from 'lucide-react'
import { getDeviceAvailability, getDeviceHistory, getMonitoringHistory, checkDevice, clearMonitoringHistory } from '../api/monitoring'
import { getDevices } from '../api/devices'
import { getApiError } from '../api/axios'
import { useRemote } from '../hooks/useRemote'
import { Button, DataTable, ErrorState, MetricCard, Notice, PageHeader, RefreshButton, Spinner, StatusBadge } from '../components/common'
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

const timeRanges = [
  { days: 1, label: '24 hours' },
  { days: 7, label: '7 days' },
  { days: 30, label: '30 days' },
]

function formatTime(value) {
  return value ? new Date(value).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : ''
}

export default function Monitoring() {
  const [filterIp, setFilterIp] = useState('')
  const [rangeDays, setRangeDays] = useState(7)
  const [notice, setNotice] = useState('')
  const [checking, setChecking] = useState(false)
  const [clearingHistory, setClearingHistory] = useState(false)
  const historyLoader = useCallback(
    () => filterIp
      ? getDeviceHistory(filterIp, 5000, rangeDays)
      : getMonitoringHistory(5000, rangeDays),
    [filterIp, rangeDays],
  )
  const availabilityLoader = useCallback(() => getDeviceAvailability(rangeDays), [rangeDays])
  const { data, loading, error, reload } = useRemote(historyLoader, [historyLoader], 30_000)
  const availability = useRemote(availabilityLoader, [availabilityLoader], 30_000)
  const devicesQuery = useRemote(getDevices, [], 30_000)
  const devices = devicesQuery.data || []

  async function checkNow() {
    if (!filterIp) {
      setNotice('Select a device before running a live monitoring check.')
      return
    }
    setChecking(true)
    setNotice('')
    try {
      const item = await checkDevice(filterIp)
      setNotice(
        `Check: ${item.status}${item.latency_ms != null ? ` · ${item.latency_ms} ms ${item.latency_method}` : ''}${item.detail ? ` · ${item.detail}` : ''}`,
      )
      reload()
      availability.reload()
    } catch (requestError) {
      setNotice(getApiError(requestError))
    } finally {
      setChecking(false)
    }
  }

  async function clearHistory() {
    if (!window.confirm('Clear all monitoring history? This permanently deletes monitoring records but keeps devices and alerts.')) return

    setClearingHistory(true)
    setNotice('')
    try {
      const result = await clearMonitoringHistory()
      setNotice(`Cleared ${result.deleted_count} monitoring record${result.deleted_count === 1 ? '' : 's'}. Registered devices and alerts were kept.`)
      reload()
      availability.reload()
    } catch (requestError) {
      setNotice(getApiError(requestError))
    } finally {
      setClearingHistory(false)
    }
  }

  const rows = data || []
  const availabilityRows = availability.data || []
  const selectedSummary = availabilityRows.find((item) => item.ip === filterIp)
  const successfulChecks = filterIp
    ? selectedSummary?.successful_checks
    : availabilityRows.reduce((total, item) => total + item.successful_checks, 0)
  const failedChecks = filterIp
    ? selectedSummary?.failed_checks
    : availabilityRows.reduce((total, item) => total + item.failed_checks, 0)
  const unknownChecks = filterIp
    ? selectedSummary?.unknown_checks
    : availabilityRows.reduce((total, item) => total + item.unknown_checks, 0)
  const measuredLatency = rows.filter((item) => item.latency_ms != null)
  const averageLatency = filterIp
    ? selectedSummary?.average_latency_ms
    : null
  const latestMeasured = measuredLatency[0]
  const latestLatency = selectedSummary?.latest_latency_ms ?? (filterIp ? latestMeasured?.latency_ms : null)
  const latestMethod = selectedSummary?.latest_latency_method ?? (filterIp ? latestMeasured?.latency_method : null)
  const summaryUptime = selectedSummary?.uptime_percent
  const availabilityHistory = useMemo(
    () => rows.slice().reverse().map((row) => ({
      time: formatTime(row.checked_at),
      availability: row.status === 'Online' ? 1 : row.status === 'Offline' ? 0 : null,
      status: row.status,
      detail: row.detail,
    })),
    [rows],
  )
  const latencyHistory = useMemo(
    () => rows.slice().reverse()
      .filter((row) => row.latency_ms != null)
      .map((row) => ({
        time: formatTime(row.checked_at),
        latency: row.latency_ms,
        method: row.latency_method,
      })),
    [rows],
  )

  return <>
    <PageHeader
      eyebrow="AVAILABILITY & LATENCY"
      title="Monitoring"
      description="The backend checks registered devices every 30 seconds by default, even when this page is closed. Device status and history refresh every 30 seconds while this page is open."
      actions={<><Button variant="danger" onClick={clearHistory} disabled={clearingHistory}><Trash2 size={15} />{clearingHistory ? 'Clearing…' : 'Clear history'}</Button><RefreshButton onClick={() => { reload(); availability.reload() }} loading={loading || availability.loading} /></>}
    />
    <Notice>
      A missing ping is recorded as Unknown, not proof that a device is offline. A disconnected alert is raised immediately for an explicit unreachable result, or after 3 consecutive unverified checks by default (about 90 seconds); this threshold is configurable on the backend.
    </Notice>
    <section className="panel monitoring-controls">
      <div className="filter-control">
        <label htmlFor="monitor-device">Device filter</label>
        <div className="select-with-icon"><Search size={15} /><select id="monitor-device" value={filterIp} onChange={(event) => setFilterIp(event.target.value)}><option value="">All devices</option>{devices.map((device) => <option key={device.id} value={device.ip}>{device.name} · {device.ip}</option>)}</select></div>
      </div>
      <label className="filter-control" htmlFor="monitor-range">
        Time range
        <select className="monitor-range-select" id="monitor-range" value={rangeDays} onChange={(event) => setRangeDays(Number(event.target.value))}>
          {timeRanges.map((range) => <option key={range.days} value={range.days}>{range.label}</option>)}
        </select>
      </label>
      <Button variant="secondary" onClick={checkNow} disabled={checking || !filterIp}>
        {checking ? 'Checking…' : <><RefreshCw size={15} /> Check selected now</>}
      </Button>
    </section>
    {devicesQuery.error && <Notice type="error">{getApiError(devicesQuery.error)}</Notice>}
    {notice && <Notice onClose={() => setNotice('')}>{notice}</Notice>}
    {loading && !data ? <Spinner /> : error && !data ? <ErrorState error={error} retry={reload} /> : <>
      {error && <ErrorState error={error} retry={reload} />}
      <div className="metrics-grid metrics-grid-small">
        <MetricCard label="Successful checks" value={successfulChecks ?? '—'} detail="Reachability confirmed" icon={Signal} tone="green" />
        <MetricCard label="Failed checks" value={failedChecks ?? '—'} detail="Explicit failure evidence" icon={Activity} tone="red" />
        <MetricCard label="Unknown checks" value={unknownChecks ?? '—'} detail="Not counted as uptime or downtime" icon={Activity} tone="amber" />
        <MetricCard label="Uptime estimate" value={summaryUptime == null ? '—' : `${summaryUptime}%`} detail={`Check-based · ${rangeDays === 1 ? '24 hours' : `${rangeDays} days`}`} icon={Clock3} tone="cyan" />
        <MetricCard label="Average latency" value={averageLatency == null ? '—' : `${Number(averageLatency).toFixed(2)} ms`} detail={filterIp ? 'Across measured checks' : 'Select a device to inspect latency'} icon={Timer} tone="purple" />
        <MetricCard label="Latest latency" value={latestLatency == null ? '—' : `${Number(latestLatency).toFixed(2)} ms`} detail={latestMethod || 'Select a device'} icon={Timer} tone="cyan" />
      </div>
      <Notice>
        Uptime is estimated from recorded checks: successful checks ÷ (successful + explicitly failed checks). Unknown checks and unobserved periods are excluded, so results depend on check frequency and history completeness.
      </Notice>
      <section className="panel chart-panel">
        <div className="panel-heading"><div><h2>Historical latency</h2><p>ICMP values are echo RTT. TCP values are connection setup time only, not complete application response time.</p></div></div>
        {filterIp && latencyHistory.length ? <div className="chart-area chart-area-short"><ResponsiveContainer width="100%" height="100%"><LineChart data={latencyHistory}><CartesianGrid stroke="var(--border-soft)" strokeDasharray="3 5" vertical={false} /><XAxis dataKey="time" tick={{ fill: 'var(--muted)', fontSize: 10 }} axisLine={false} tickLine={false} minTickGap={24} /><YAxis unit=" ms" tick={{ fill: 'var(--muted)', fontSize: 10 }} axisLine={false} tickLine={false} /><Tooltip contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 10, color: 'var(--text)' }} formatter={(value, name, item) => [`${Number(value).toFixed(2)} ms (${item.payload.method})`, 'Latency']} /><Line dataKey="latency" type="monotone" stroke="var(--cyan)" strokeWidth={2} dot={false} connectNulls={false} /></LineChart></ResponsiveContainer></div> : <div className="chart-empty">{filterIp ? 'No verified latency measurements in this range.' : 'Select a device to view its latency history.'}</div>}
      </section>
      <section className="panel chart-panel">
        <div className="panel-heading"><div><h2>Device availability history</h2><p>Unknown checks are gaps, not downtime.</p></div><span className="chart-legend"><i /> Online checks</span></div>
        {filterIp && availabilityHistory.length ? <div className="chart-area chart-area-short"><ResponsiveContainer width="100%" height="100%"><AreaChart data={availabilityHistory}><CartesianGrid stroke="var(--border-soft)" strokeDasharray="3 5" vertical={false} /><XAxis dataKey="time" tick={{ fill: 'var(--muted)', fontSize: 10 }} axisLine={false} tickLine={false} minTickGap={24} /><YAxis domain={[0, 1]} ticks={[0, 1]} tickFormatter={(value) => value ? 'Online' : 'Offline'} tick={{ fill: 'var(--muted)', fontSize: 10 }} axisLine={false} tickLine={false} width={55} /><Tooltip contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 10, color: 'var(--text)' }} formatter={(value, _name, item) => [item.payload.status, item.payload.detail || 'Check']} /><Area dataKey="availability" type="stepAfter" stroke="var(--cyan)" fill="var(--cyan)" fillOpacity={0.12} connectNulls={false} /></AreaChart></ResponsiveContainer></div> : <div className="chart-empty">{filterIp ? 'No availability records in this range.' : 'Select a device to inspect its availability history.'}</div>}
      </section>
      {availability.error ? <ErrorState error={availability.error} retry={availability.reload} /> : <section className="panel table-panel"><div className="panel-heading"><div><h2>Device availability</h2><p>Uptime and check counts for {rangeDays === 1 ? '24 hours' : `${rangeDays} days`} (unknown observations excluded).</p></div></div>{availability.loading && !availability.data ? <Spinner /> : <DataTable rows={availabilityRows} columns={[
        { key: 'device_name', label: 'Device', render: (row) => <div className="cell-device"><span className="device-dot" /><strong>{row.device_name}</strong><small>{row.ip}</small></div> },
        { key: 'latest_status', label: 'Latest status', render: (row) => <StatusBadge status={row.latest_status} /> },
        { key: 'uptime_percent', label: 'Uptime', render: (row) => row.uptime_percent == null ? '—' : `${row.uptime_percent}%` },
        { key: 'successful_checks', label: 'Successful' },
        { key: 'failed_checks', label: 'Failed' },
        { key: 'unknown_checks', label: 'Unknown' },
        { key: 'average_latency_ms', label: 'Avg latency', render: (row) => row.average_latency_ms == null ? '—' : `${row.average_latency_ms} ms` },
        { key: 'latest_latency_ms', label: 'Latest latency', render: (row) => row.latest_latency_ms == null ? '—' : `${row.latest_latency_ms} ms · ${row.latest_latency_method}` },
      ]} empty="No registered devices or monitoring data" />}</section>}
      <section className="panel table-panel"><div className="panel-heading"><div><h2>Monitoring records</h2><p>Latest checks with response method and failure explanation.</p></div></div><DataTable rows={rows} columns={[
        { key: 'ip', label: 'IP address' },
        { key: 'status', label: 'Reachability', render: (row) => <StatusBadge status={row.status} /> },
        { key: 'latency_ms', label: 'Latency', render: (row) => row.latency_ms == null ? '—' : `${row.latency_ms} ms · ${row.latency_method}` },
        { key: 'tcp_result', label: 'TCP check', render: (row) => row.tcp_result ? `${row.tcp_result}${row.tcp_response_ms == null ? '' : ` · ${row.tcp_response_ms} ms`}` : '—' },
        { key: 'http_status_code', label: 'HTTP health', render: (row) => row.http_status_code == null ? (row.http_health_status || '—') : `${row.http_status_code} · ${row.http_health_status}` },
        { key: 'detail', label: 'Explanation', render: (row) => row.detail || '—' },
        { key: 'checked_at', label: 'Checked at', render: (row) => row.checked_at ? new Date(row.checked_at).toLocaleString() : '—' },
      ]} empty="No monitoring history in this time range" /></section>
    </>}
  </>
}
