import { useState } from 'react'
import { Activity, ArrowUpRight, Network, Radio, Search, Signal } from 'lucide-react'
import { Link } from 'react-router-dom'
import { pingAddress } from '../api/discovery'
import { getDiscoveryTopology } from '../api/topology'
import { getApiError } from '../api/axios'
import { Button, DataTable, Notice, PageHeader, StatusBadge } from '../components/common'

export default function Discovery() {
  const [network, setNetwork] = useState('')
  const [ip, setIp] = useState('')
  const [tcpPort, setTcpPort] = useState('')
  const [results, setResults] = useState(null)
  const [pingResult, setPingResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [pingBusy, setPingBusy] = useState(false)
  const [error, setError] = useState('')
  const [pingError, setPingError] = useState('')
  async function scan(event) {
    event.preventDefault(); setBusy(true); setError(''); setResults(null)
    try {
      const cidr = network.trim()
      const topology = await getDiscoveryTopology(cidr, true)
      localStorage.setItem(
        'nmvs_topology_grouping_network',
        topology.nodes.find((node) => node.subnet)?.subnet || cidr,
      )
      setResults({ network: cidr, count: topology.nodes.length, devices: topology.nodes })
    } catch (e) { setError(getApiError(e)) } finally { setBusy(false) }
  }
  async function ping(event) {
    event.preventDefault(); setPingBusy(true); setPingError(''); setPingResult(null)
    try { setPingResult(await pingAddress(ip.trim(), tcpPort ? Number(tcpPort) : undefined)) } catch (e) { setPingError(getApiError(e)) } finally { setPingBusy(false) }
  }
  return <>
    <PageHeader eyebrow="NETWORK VISIBILITY" title="Network discovery" description="Scan a CIDR network, add detected devices to inventory, and view the results in Topology." />
    <div className="discovery-grid">
      <section className="panel discovery-card"><div className="panel-heading"><div className="feature-title"><span className="feature-icon"><Network size={18} /></span><div><h2>Scan network range</h2><p>Scans up to 4,096 addresses, identifies reachable devices, and adds them to Topology inventory.</p></div></div></div><form className="inline-form" onSubmit={scan}><label>CIDR network<input required placeholder="192.168.1.0/24" value={network} onChange={(e) => setNetwork(e.target.value)} /></label><Button disabled={busy}>{busy ? <><span className="button-loader" />Scanning…</> : <><Search size={16} /> Start scan</>}</Button></form>{busy && <Notice>Scanning and identifying reachable devices. Duration depends on network size and response time.</Notice>}{error && <Notice type="error">{error}</Notice>}{results && <div className="scan-result-summary"><span className="live-dot" /> Scan complete · {results.count} reachable {results.count === 1 ? 'device' : 'devices'} · {results.network}<Link className="text-link" to="/topology">View in Topology <ArrowUpRight size={14} /></Link></div>}</section>
      <section className="panel discovery-card"><div className="panel-heading"><div className="feature-title"><span className="feature-icon feature-purple"><Radio size={18} /></span><div><h2>Ping test</h2><p>Check an individual IPv4 or IPv6 address. If the device blocks ping, enter a TCP service port to check as a fallback.</p></div></div></div><form className="inline-form" onSubmit={ping}><label>IP address<input required placeholder="192.168.1.1" value={ip} onChange={(e) => setIp(e.target.value)} /></label><label>TCP service port (optional)<input type="number" min="1" max="65535" step="1" placeholder="443" value={tcpPort} onChange={(e) => setTcpPort(e.target.value)} /></label><Button variant="secondary" disabled={pingBusy}>{pingBusy ? 'Testing…' : <><Activity size={16} /> Ping address</>}</Button></form>{pingError && <Notice type="error">{pingError}</Notice>}{pingResult?.detail && <Notice type={pingResult.status === 'Unknown' ? 'error' : 'info'}>{pingResult.detail}</Notice>}{pingResult && <div className="ping-result"><Signal size={18} /><strong>{pingResult.ip}</strong><StatusBadge status={pingResult.status} /><span>Checked by {pingResult.checked_by}</span></div>}</section>
    </div>
    <section className="panel table-panel"><div className="panel-heading"><div><h2>Discovered devices</h2><p>Detected devices are saved to inventory and shown in the Topology module by the scanned CIDR.</p></div></div>{results ? <DataTable rows={results.devices || []} empty="No reachable hosts returned by scan" columns={[{ key: 'name', label: 'Device' }, { key: 'ip', label: 'IP address' }, { key: 'device_type', label: 'Device type' }, { key: 'status', label: 'Status', render: (row) => <StatusBadge status={row.status} /> }]} /> : <div className="chart-empty">Enter a network CIDR and run a scan to discover devices.</div>}</section>
  </>
}
