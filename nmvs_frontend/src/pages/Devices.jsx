import { useCallback, useMemo, useState } from 'react'
import { Activity, Edit2, Eye, Plus, Radar, Search, Trash2 } from 'lucide-react'
import { createDevice, deleteDevice, detectDevice, getDevices, redetectDevice, updateDevice } from '../api/devices'
import { getApiError } from '../api/axios'
import { useRemote } from '../hooks/useRemote'
import { Button, DataTable, ErrorState, Notice, PageHeader, RefreshButton, Spinner, StatusBadge } from '../components/common'

function DeviceForm({ device, onClose, onSaved }) {
  const [form, setForm] = useState({
    name: device?.name || '',
    ip: device?.ip || '',
    network_type: device?.network_type || '',
    service_port: device?.service_port ?? '',
    health_check_url: device?.health_check_url || '',
  })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  async function submit(event) {
    event.preventDefault()
    setError('')
    setBusy(true)
    try {
      const body = {
        name: form.name.trim(),
        ip: form.ip.trim(),
        network_type: form.network_type.trim() || null,
        service_port: form.service_port ? Number(form.service_port) : null,
        health_check_url: form.health_check_url.trim() || null,
      }
      if (device) await updateDevice(device.id, body)
      else await createDevice(body)
      onSaved(device ? 'Device updated.' : 'Device registered.')
      onClose()
    } catch (requestError) {
      setError(getApiError(requestError))
    } finally {
      setBusy(false)
    }
  }
  return <div className="modal-backdrop" role="presentation" onMouseDown={(e) => e.target === e.currentTarget && onClose()}><section className="modal-card" role="dialog" aria-modal="true" aria-labelledby="device-form-title"><div className="modal-heading"><div><span className="eyebrow">{device ? 'INVENTORY UPDATE' : 'NEW INVENTORY ITEM'}</span><h2 id="device-form-title">{device ? 'Edit device' : 'Register a device'}</h2></div><button className="modal-close" onClick={onClose} aria-label="Close">×</button></div><form className="form-stack" onSubmit={submit}>{error && <Notice type="error">{error}</Notice>}<label>Device name<input required maxLength="100" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label><label>IP address<input required inputMode="text" placeholder="192.168.1.10" value={form.ip} onChange={(e) => setForm({ ...form, ip: e.target.value })} /></label><label>Network type <small className="field-hint">Optional classification; device type is detected by backend.</small><input maxLength="100" value={form.network_type} onChange={(e) => setForm({ ...form, network_type: e.target.value })} /></label><label>TCP service port <small className="field-hint">Optional fallback when ICMP ping receives no reply.</small><input type="number" min="1" max="65535" step="1" value={form.service_port} onChange={(e) => setForm({ ...form, service_port: e.target.value })} /></label><label>HTTP health-check URL <small className="field-hint">Optional. The administrator must allowlist its host in MONITORING_HTTP_ALLOWED_HOSTS.</small><input type="url" maxLength="2048" placeholder="https://approved.example/health" value={form.health_check_url} onChange={(e) => setForm({ ...form, health_check_url: e.target.value })} /></label><div className="modal-actions"><Button variant="secondary" type="button" onClick={onClose}>Cancel</Button><Button disabled={busy}>{busy ? 'Saving…' : device ? 'Save changes' : 'Register device'}</Button></div></form></section></div>
}

function DeviceDetails({ device, onClose, onRedetect }) {
  return <div className="modal-backdrop" role="presentation" onMouseDown={(e) => e.target === e.currentTarget && onClose()}><section className="modal-card" role="dialog" aria-modal="true"><div className="modal-heading"><div><span className="eyebrow">DEVICE RECORD · #{device.id}</span><h2>{device.name}</h2></div><button className="modal-close" onClick={onClose} aria-label="Close">×</button></div><div className="details-grid">{[['IP address', device.ip], ['Device type', device.device_type], ['Network type', device.network_type], ['Status', device.status || 'Unknown'], ['TCP service port', device.service_port || '—'], ['HTTP health URL', device.health_check_url || 'Not configured'], ['Source', device.source], ['Last seen', device.last_seen ? new Date(device.last_seen).toLocaleString() : '—'], ['Created', device.created_at ? new Date(device.created_at).toLocaleString() : '—'], ['Updated', device.updated_at ? new Date(device.updated_at).toLocaleString() : '—']].map(([label, value]) => <div key={label}><small>{label}</small><strong>{value}</strong></div>)}</div><div className="modal-actions"><Button variant="secondary" onClick={onClose}>Close</Button><Button onClick={() => onRedetect(device)}>Re-detect type</Button></div></section></div>
}

export default function Devices() {
  const loader = useCallback(() => getDevices(), [])
  const { data: devices, loading, error, reload } = useRemote(loader, [loader], 30_000)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [editing, setEditing] = useState(null)
  const [details, setDetails] = useState(null)
  const [create, setCreate] = useState(false)
  const [notice, setNotice] = useState('')
  const [detectorIp, setDetectorIp] = useState('')
  const [detection, setDetection] = useState(null)
  const [detectError, setDetectError] = useState('')
  const [detecting, setDetecting] = useState(false)
  const filtered = useMemo(() => (devices || []).filter((device) => {
    const matches = `${device.name} ${device.ip} ${device.device_type} ${device.network_type}`.toLowerCase().includes(search.toLowerCase())
    return matches && (statusFilter === 'all' || String(device.status || 'unknown').toLowerCase() === statusFilter)
  }), [devices, search, statusFilter])
  async function doDelete(device) {
    if (!window.confirm(`Delete ${device.name} (${device.ip})? This cannot be undone.`)) return
    try {
      await deleteDevice(device.id)
      setNotice(`${device.name} was deleted.`)
      reload()
    } catch (requestError) { setNotice(getApiError(requestError)) }
  }
  async function doRedetect(device) {
    try {
      const updated = await redetectDevice(device.id)
      setNotice(`Device type detected as ${updated.device_type}.`)
      setDetails(updated)
      reload()
    } catch (requestError) { setNotice(getApiError(requestError)) }
  }
  async function detect() {
    setDetecting(true); setDetectError(''); setDetection(null)
    try { setDetection(await detectDevice(detectorIp.trim())) }
    catch (requestError) { setDetectError(getApiError(requestError)) }
    finally { setDetecting(false) }
  }
  const columns = [
    { key: 'name', label: 'Device', render: (row) => <div className="cell-device"><span className={`device-dot ${String(row.status).toLowerCase() === 'online' ? 'dot-online' : ''}`} /><strong>{row.name}</strong><small>{row.ip}</small></div> },
    { key: 'device_type', label: 'Device type', render: (row) => <span className="type-pill">{row.device_type}</span> },
    { key: 'network_type', label: 'Network type' },
    { key: 'status', label: 'Status', render: (row) => <StatusBadge status={row.status} /> },
    { key: 'last_seen', label: 'Last seen', render: (row) => row.last_seen ? new Date(row.last_seen).toLocaleString() : '—' },
    { key: 'actions', label: '', render: (row) => <div className="row-actions"><button title="View details" onClick={() => setDetails(row)}><Eye size={15} /></button><button title="Edit device" onClick={() => setEditing(row)}><Edit2 size={15} /></button><button title="Delete device" onClick={() => doDelete(row)}><Trash2 size={15} /></button></div> },
  ]
  return <>
    <PageHeader eyebrow="ASSET MANAGEMENT" title="Device inventory" description="Manage registered network devices and their backend-detected classifications." actions={<><RefreshButton onClick={reload} loading={loading} /><Button onClick={() => setCreate(true)}><Plus size={16} /> Add device</Button></>} />
    {notice && <Notice onClose={() => setNotice('')}>{notice}</Notice>}
    <section className="panel detect-panel"><div className="detect-copy"><div className="detect-icon"><Radar size={20} /></div><div><h2>Device detection</h2><p>Ask the backend to inspect an IP address. Device type and ISP data appear only when returned by the API.</p></div></div><div className="detect-controls"><input aria-label="IP address to detect" placeholder="IP address" value={detectorIp} onChange={(e) => setDetectorIp(e.target.value)} /><Button disabled={detecting || !detectorIp.trim()} onClick={detect}>{detecting ? 'Detecting…' : 'Detect device'}</Button></div>{detectError && <Notice type="error">{detectError}</Notice>}{detection && <div className="detect-result"><strong>{detection.device_type}</strong><span>{detection.ip}</span><StatusBadge status={detection.status} />{detection.isp && <span>ISP: {detection.isp}</span>}{detection.network_type && <span>Network: {detection.network_type}</span>}{detection.hostname && <span>Hostname: {detection.hostname}</span>}</div>}</section>
    <section className="panel table-panel">
      <div className="table-toolbar"><div><h2>Registered devices <span className="count-badge">{devices?.length ?? '—'}</span></h2><p>Current status refreshes every 30 seconds while this page is open.</p></div><div className="table-filters"><label className="search-input"><Search size={16} /><input aria-label="Search devices" placeholder="Search devices…" value={search} onChange={(e) => setSearch(e.target.value)} /></label><select aria-label="Filter by status" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}><option value="all">All status</option><option value="online">Online</option><option value="offline">Offline</option><option value="unknown">Unknown</option></select></div></div>
      {loading && !devices ? <Spinner /> : error && !devices ? <ErrorState error={error} retry={reload} /> : <>{error && <ErrorState error={error} retry={reload} />}<DataTable columns={columns} rows={filtered} empty={devices?.length ? 'No devices match your filters' : 'No devices registered'} /></>}
    </section>
    {(create || editing) && <DeviceForm device={editing} onClose={() => { setCreate(false); setEditing(null) }} onSaved={(text) => { setNotice(text); reload() }} />}
    {details && <DeviceDetails device={details} onClose={() => setDetails(null)} onRedetect={doRedetect} />}
  </>
}
