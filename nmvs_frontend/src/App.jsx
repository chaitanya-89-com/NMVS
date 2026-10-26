import { lazy, Suspense, useEffect } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './context/AuthContext'

const AppLayout = lazy(() => import('./components/layout/AppLayout'))
const LoginPage = lazy(() => import('./pages/AuthPages').then((module) => ({ default: module.LoginPage })))
const RegisterPage = lazy(() => import('./pages/AuthPages').then((module) => ({ default: module.RegisterPage })))
const ForgotPasswordPage = lazy(() => import('./pages/AuthPages').then((module) => ({ default: module.ForgotPasswordPage })))
const Dashboard = lazy(() => import('./pages/Dashboard'))
const Devices = lazy(() => import('./pages/Devices'))
const Discovery = lazy(() => import('./pages/Discovery'))
const Monitoring = lazy(() => import('./pages/Monitoring'))
const Topology = lazy(() => import('./pages/Topology'))
const SpeedMonitoring = lazy(() => import('./pages/SpeedMonitoring'))
const Alerts = lazy(() => import('./pages/Alerts'))
const Reports = lazy(() => import('./pages/Reports'))
const Metrics = lazy(() => import('./pages/Metrics'))
const Settings = lazy(() => import('./pages/Settings'))

function ProtectedLayout() {
  const { token, checking } = useAuth()
  if (checking) return <div className="auth-loading"><span className="spin-dot" /> Verifying operator session…</div>
  return token ? <AppLayout /> : <Navigate to="/login" replace />
}

function PublicRoute({ children }) {
  const { token, checking } = useAuth()
  if (checking) return <div className="auth-loading"><span className="spin-dot" /> Verifying operator session…</div>
  return token ? <Navigate to="/" replace /> : children
}

function ThemeLoader() {
  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: light)')
    const applyTheme = () => {
      const themeVersion = localStorage.getItem('nmvs_theme_version')
      if (themeVersion !== '2') {
        localStorage.setItem('nmvs_theme', 'light')
        localStorage.setItem('nmvs_theme_version', '2')
      }
      const theme = localStorage.getItem('nmvs_theme') || 'light'
      document.documentElement.dataset.theme = theme === 'system' ? (media.matches ? 'light' : 'dark') : theme
    }
    applyTheme()
    media.addEventListener('change', applyTheme)
    window.addEventListener('nmvs:themechange', applyTheme)
    return () => {
      media.removeEventListener('change', applyTheme)
      window.removeEventListener('nmvs:themechange', applyTheme)
    }
  }, [])
  return null
}

function NotFound() {
  return <div className="not-found"><span className="eyebrow">404 / NOT FOUND</span><h1>This route does not exist</h1><a href="/">Return to dashboard</a></div>
}

export default function App() {
  return <BrowserRouter><ThemeLoader /><Suspense fallback={<div className="auth-loading"><span className="spin-dot" /> Loading page…</div>}><Routes>
    <Route path="/login" element={<PublicRoute><LoginPage /></PublicRoute>} />
    <Route path="/register" element={<PublicRoute><RegisterPage /></PublicRoute>} />
    <Route path="/forgot-password" element={<PublicRoute><ForgotPasswordPage /></PublicRoute>} />
    <Route element={<ProtectedLayout />}>
      <Route index element={<Dashboard />} />
      <Route path="/devices" element={<Devices />} />
      <Route path="/discovery" element={<Discovery />} />
      <Route path="/monitoring" element={<Monitoring />} />
      <Route path="/topology" element={<Topology />} />
      <Route path="/speed" element={<SpeedMonitoring />} />
      <Route path="/alerts" element={<Alerts />} />
      <Route path="/reports" element={<Reports />} />
      <Route path="/metrics" element={<Metrics />} />
      <Route path="/settings" element={<Settings />} />
    </Route>
    <Route path="*" element={<NotFound />} />
  </Routes></Suspense></BrowserRouter>
}
