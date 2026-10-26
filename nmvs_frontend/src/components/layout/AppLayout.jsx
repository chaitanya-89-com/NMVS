import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import {
  Activity, Bell, Boxes, ChevronLeft, ChevronRight, CircleGauge, Compass, Gauge,
  LayoutDashboard, LogOut, Menu, Network, Settings, Shield, X,
} from 'lucide-react'
import { getAlerts } from '../../api/alerts'
import { useAuth } from '../../context/AuthContext'
import { Notice } from '../common'

const navigation = [
  { label: 'Overview', to: '/', icon: LayoutDashboard },
  { label: 'Inventory', to: '/devices', icon: Boxes },
  { label: 'Discovery', to: '/discovery', icon: Compass },
  { label: 'Monitoring', to: '/monitoring', icon: Activity },
  { label: 'Topology', to: '/topology', icon: Network },
  { label: 'Speed tests', to: '/speed', icon: Gauge },
  { label: 'Alerts', to: '/alerts', icon: Bell },
  { label: 'Reports', to: '/reports', icon: CircleGauge },
  { label: 'Metrics', to: '/metrics', icon: Shield },
  { label: 'Settings', to: '/settings', icon: Settings },
]

function AlertNotifications() {
  const [notifications, setNotifications] = useState([])
  const latestAlertId = useRef(null)

  useEffect(() => {
    let stopped = false
    let timer

    async function pollAlerts() {
      try {
        const alerts = await getAlerts({ limit: 200 })
        if (stopped) return

        const newestId = alerts.reduce((latest, alert) => Math.max(latest, alert.id), 0)
        const previousId = latestAlertId.current

        if (previousId === null) {
          latestAlertId.current = newestId
          const activeDeviceAlerts = alerts
            .filter((alert) => (
              alert.status === 'active'
              && ['DISCONNECTED', 'STATUS_UNKNOWN'].includes(alert.alert_type)
            ))
            .slice(0, 3)
          if (activeDeviceAlerts.length) setNotifications(activeDeviceAlerts)
        } else {
          latestAlertId.current = Math.max(previousId, newestId)
          const newStatusAlerts = alerts
            .filter((alert) => (
              alert.id > previousId
            ))
            .sort((first, second) => first.id - second.id)

          if (newStatusAlerts.length) {
            setNotifications((current) => [...current, ...newStatusAlerts].slice(-3))
          }
        }
      } catch (error) {
        if (!stopped) console.error('Unable to check for new alert notifications:', error)
      } finally {
        if (!stopped) timer = window.setTimeout(pollAlerts, 10000)
      }
    }

    pollAlerts()
    return () => {
      stopped = true
      window.clearTimeout(timer)
    }
  }, [])

  useEffect(() => {
    if (!notifications.length) return undefined

    const timers = notifications.map((alert) => window.setTimeout(() => {
      setNotifications((current) => current.filter((item) => item.id !== alert.id))
    }, alert.alert_type === 'DISCONNECTED' ? 30000 : 15000))

    return () => timers.forEach((timer) => window.clearTimeout(timer))
  }, [notifications])

  function dismissAlert(id) {
    setNotifications((current) => current.filter((alert) => alert.id !== id))
  }

  if (!notifications.length) return null

  return (
    <aside className="alert-toast-region" aria-live="assertive" aria-label="New device alerts">
      {notifications.map((alert) => {
        const severity = String(alert.severity || 'info').toLowerCase()
        return (
          <article
            className={`alert-toast alert-toast-${severity}`}
            key={alert.id}
            role="alert"
          >
            <div className="alert-toast-content">
              <strong>{alert.title || alert.alert_type}</strong>
              <p>{alert.message}</p>
              <Link to="/alerts" onClick={() => dismissAlert(alert.id)}>View alert</Link>
            </div>
            <button
              type="button"
              aria-label="Dismiss alert notification"
              onClick={() => dismissAlert(alert.id)}
            >
              ×
            </button>
          </article>
        )
      })}
    </aside>
  )
}

export default function AppLayout() {
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const { user, signOut, sessionError } = useAuth()
  const location = useLocation()
  const current = navigation.find((item) => item.to === location.pathname)
  return (
    <div className={`app-shell ${collapsed ? 'sidebar-collapsed' : ''} ${mobileOpen ? 'mobile-open' : ''}`}>
      {mobileOpen && <button className="mobile-scrim" aria-label="Close menu" onClick={() => setMobileOpen(false)} />}
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><Network size={21} /></div>
          <div className="brand-copy"><strong>NMVS</strong><span>NETWORK OPERATIONS</span></div>
          <button className="mobile-close" aria-label="Close navigation" onClick={() => setMobileOpen(false)}><X size={18} /></button>
        </div>
        <div className="nav-section-label">WORKSPACE</div>
        <nav className="side-nav">
          {navigation.map(({ label, to, icon: Icon }) => (
            <NavLink key={to} end={to === '/'} to={to} title={collapsed ? label : undefined} onClick={() => setMobileOpen(false)}>
              <Icon size={18} /><span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="connection-state"><span className="configured-dot" /><span>API endpoint configured</span></div>
          <button className="user-card" onClick={signOut} title="Sign out">
            <span className="avatar">{(user?.username || 'U').slice(0, 1).toUpperCase()}</span>
            <span className="user-copy"><strong>{user?.username || 'Operator'}</strong><small>Sign out</small></span>
            <LogOut size={16} className="logout-icon" />
          </button>
          <button className="collapse-button" onClick={() => setCollapsed(!collapsed)} aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}>
            {collapsed ? <ChevronRight size={17} /> : <><ChevronLeft size={17} /> Collapse navigation</>}
          </button>
        </div>
      </aside>
      <main className="main-area">
        <header className="topbar">
          <button className="mobile-menu" aria-label="Open navigation" onClick={() => setMobileOpen(true)}><Menu size={21} /></button>
          <div className="breadcrumb"><span>NMVS</span><span className="crumb-separator">/</span><strong>{current?.label || 'Workspace'}</strong></div>
          <div className="topbar-right"><span className="topbar-status"><i />Monitoring console</span><span className="top-avatar">{(user?.username || 'U').slice(0, 1).toUpperCase()}</span></div>
        </header>
        <div className="page-content">{sessionError && <Notice type="error">{sessionError}</Notice>}<Outlet /></div>
      </main>
      <AlertNotifications />
    </div>
  )
}
