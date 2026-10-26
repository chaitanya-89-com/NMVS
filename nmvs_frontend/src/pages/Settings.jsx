import { useCallback, useEffect, useState } from 'react'
import { Bell, LockKeyhole, Save, UserRound } from 'lucide-react'
import { changePassword } from '../api/auth'
import { getApiError } from '../api/axios'
import { getProfile, getSettings, updateProfile, updateSettings } from '../api/settings'
import { useAuth } from '../context/AuthContext'
import { useRemote } from '../hooks/useRemote'
import { Button, ErrorState, Notice, PageHeader, Spinner } from '../components/common'
import { validateStrongPassword } from '../utils/validation'

export default function Settings() {
  const profileLoader = useCallback(() => getProfile(), [])
  const settingsLoader = useCallback(() => getSettings(), [])
  const profileQuery = useRemote(profileLoader)
  const settingsQuery = useRemote(settingsLoader)
  const [profile, setProfile] = useState({ username: '', email: '' })
  const [preferences, setPreferences] = useState({ theme: 'light', email_notifications: true, alert_notifications: true, timezone: 'Asia/Kolkata' })
  const [password, setPassword] = useState({ current_password: '', new_password: '', confirm_password: '' })
  const [busy, setBusy] = useState('')
  const [notice, setNotice] = useState('')
  const { user } = useAuth()
  useEffect(() => { if (profileQuery.data) setProfile({ username: profileQuery.data.username, email: profileQuery.data.email }) }, [profileQuery.data])
  useEffect(() => {
    if (!settingsQuery.data) return
    const activeTheme = localStorage.getItem('nmvs_theme') || document.documentElement.dataset.theme || settingsQuery.data.theme
    setPreferences({ theme: activeTheme, email_notifications: settingsQuery.data.email_notifications, alert_notifications: settingsQuery.data.alert_notifications, timezone: settingsQuery.data.timezone })
  }, [settingsQuery.data])
  async function saveProfile(event) {
    event.preventDefault(); setBusy('profile'); setNotice('')
    try { await updateProfile(profile); await profileQuery.reload(); setNotice('Profile saved.') }
    catch (e) { setNotice(getApiError(e)) }
    finally { setBusy('') }
  }
  async function savePreferences(event) {
    event.preventDefault(); setBusy('settings'); setNotice('')
    try {
      const saved = await updateSettings(preferences)
      setPreferences({ theme: saved.theme, email_notifications: saved.email_notifications, alert_notifications: saved.alert_notifications, timezone: saved.timezone })
      localStorage.setItem('nmvs_theme', saved.theme)
      window.dispatchEvent(new Event('nmvs:themechange'))
      setNotice('Preferences saved by the backend.')
    } catch (e) { setNotice(getApiError(e)) }
    finally { setBusy('') }
  }
  async function savePassword(event) {
    event.preventDefault(); setBusy('password'); setNotice('')
    try {
      if (password.new_password !== password.confirm_password) throw new Error('New passwords do not match.')
      const passwordError = validateStrongPassword(password.new_password)
      if (passwordError) throw new Error(passwordError)
      const result = await changePassword(password)
      setPassword({ current_password: '', new_password: '', confirm_password: '' })
      setNotice(result.message)
    }
    catch (e) { setNotice(getApiError(e)) }
    finally { setBusy('') }
  }
  if (profileQuery.loading && settingsQuery.loading && !profileQuery.data && !settingsQuery.data) return <Spinner label="Loading account settings…" />
  return <>
    <PageHeader eyebrow="OPERATOR PREFERENCES" title="Settings" description={`Account and notification preferences for ${user?.username || 'your account'}.`} />
    {notice && <Notice type={notice.toLowerCase().includes('saved') || notice.toLowerCase().includes('success') ? 'success' : 'error'} onClose={() => setNotice('')}>{notice}</Notice>}
    {profileQuery.error && !profileQuery.data && <ErrorState error={profileQuery.error} retry={profileQuery.reload} />}
    {settingsQuery.error && !settingsQuery.data && <ErrorState error={settingsQuery.error} retry={settingsQuery.reload} />}
    <div className="settings-grid">
      {profileQuery.data && <section className="panel settings-card"><div className="settings-heading"><span className="feature-icon"><UserRound size={18} /></span><div><h2>Profile</h2><p>Update your account name and email.</p></div></div><form className="form-stack" onSubmit={saveProfile}><label>Username<input minLength="3" maxLength="50" required value={profile.username} onChange={(e) => setProfile({ ...profile, username: e.target.value })} /></label><label>Email address<input type="email" required value={profile.email} onChange={(e) => setProfile({ ...profile, email: e.target.value })} /></label><div className="settings-footnote">Email verified: {profileQuery.data.email_verified ? 'Yes' : 'No'}</div><Button disabled={busy === 'profile'}><Save size={15} />{busy === 'profile' ? 'Saving…' : 'Save profile'}</Button></form></section>}
      {settingsQuery.data && <section className="panel settings-card"><div className="settings-heading"><span className="feature-icon feature-purple"><Bell size={18} /></span><div><h2>Preferences</h2><p>Supported notification and display settings.</p></div></div><form className="form-stack" onSubmit={savePreferences}><label>Theme<select value={preferences.theme} onChange={(e) => setPreferences({ ...preferences, theme: e.target.value })}><option value="dark">Dark</option><option value="light">Light</option><option value="system">System</option></select></label><label>Timezone<input maxLength="64" required value={preferences.timezone} onChange={(e) => setPreferences({ ...preferences, timezone: e.target.value })} /><small className="field-hint">Use a valid IANA timezone, e.g. Asia/Kolkata.</small></label><label className="toggle-row"><span><strong>Email notifications</strong><small>Backend preference</small></span><input type="checkbox" checked={preferences.email_notifications} onChange={(e) => setPreferences({ ...preferences, email_notifications: e.target.checked })} /></label><label className="toggle-row"><span><strong>Alert notifications</strong><small>Backend preference</small></span><input type="checkbox" checked={preferences.alert_notifications} onChange={(e) => setPreferences({ ...preferences, alert_notifications: e.target.checked })} /></label><Button disabled={busy === 'settings'}><Save size={15} />{busy === 'settings' ? 'Saving…' : 'Save preferences'}</Button></form></section>}
      <section className="panel settings-card"><div className="settings-heading"><span className="feature-icon feature-orange"><LockKeyhole size={18} /></span><div><h2>Change password</h2><p>New password must be 12+ characters with upper/lowercase, number and symbol.</p></div></div><form className="form-stack" onSubmit={savePassword}><label>Current password<input type="password" autoComplete="current-password" required value={password.current_password} onChange={(e) => setPassword({ ...password, current_password: e.target.value })} /></label><label>New password<input type="password" autoComplete="new-password" minLength="12" required value={password.new_password} onChange={(e) => setPassword({ ...password, new_password: e.target.value })} /></label><label>Confirm new password<input type="password" autoComplete="new-password" minLength="12" required value={password.confirm_password} onChange={(e) => setPassword({ ...password, confirm_password: e.target.value })} /></label><Button disabled={busy === 'password'}>{busy === 'password' ? 'Updating…' : 'Change password'}</Button></form></section>
    </div>
    <div className="settings-note">Authentication uses the backend’s Bearer access token. Tokens are held in browser local storage to match the current backend mechanism; use HTTPS in deployed environments.</div>
  </>
}
