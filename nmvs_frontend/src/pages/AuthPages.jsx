import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowLeft, Eye, EyeOff, Network, ShieldCheck } from 'lucide-react'
import { forgotPassword, register, resetPassword, verifyResetOtp } from '../api/auth'
import { getApiError } from '../api/axios'
import { useAuth } from '../context/AuthContext'
import { validateStrongPassword } from '../utils/validation'

function AuthFrame({ title, subtitle, children, footer }) {
  return (
    <main className={`auth-screen ${title === 'Welcome back' ? 'auth-screen-login' : ''}`}>
      <div className="auth-glow auth-glow-one" /><div className="auth-glow auth-glow-two" />
      {title === 'Welcome back' && <section className="auth-story" aria-label="Network operations">
        <div className="auth-story-kicker"><span /><span>NETWORK OPERATIONS PLATFORM</span></div>
        <h2>See every connection.<br /><span>Understand your network.</span></h2>
        <p>One clear view of your devices, performance, and network health.</p>
        <div className="auth-story-footer"><Network size={16} /><span>Network Monitoring &amp; Visibility System</span></div>
      </section>}
      <section className="auth-panel">
        <Link to="/login" className="auth-brand"><span className="brand-mark"><Network size={21} /></span><strong>NMVS</strong></Link>
        <div className="auth-heading"><div className="auth-symbol"><ShieldCheck size={21} /></div><h1>{title}</h1><p>{subtitle}</p></div>
        {children}
        {footer && <div className="auth-footer">{footer}</div>}
        <div className="auth-caption">NETWORK MONITORING & VISIBILITY SYSTEM</div>
      </section>
    </main>
  )
}

function FormAlert({ children }) {
  return children ? <div className="form-alert" role="alert">{children}</div> : null
}

export function LoginPage() {
  const [fields, setFields] = useState({ username: '', password: '' })
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const { signIn } = useAuth()
  const navigate = useNavigate()
  async function submit(event) {
    event.preventDefault()
    setError('')
    setBusy(true)
    try {
      await signIn(fields)
      navigate('/', { replace: true })
    } catch (requestError) {
      setError(getApiError(requestError))
    } finally {
      setBusy(false)
    }
  }
  return (
    <AuthFrame title="Welcome back" subtitle="Sign in to your network operations workspace.">
      <form className="form-stack" onSubmit={submit}>
        <FormAlert>{error}</FormAlert>
        <label>Username<input autoComplete="username" required value={fields.username} onChange={(e) => setFields({ ...fields, username: e.target.value })} placeholder="Enter your username" /></label>
        <label>Password<div className="password-field"><input autoComplete="current-password" required type={showPassword ? 'text' : 'password'} value={fields.password} onChange={(e) => setFields({ ...fields, password: e.target.value })} placeholder="Enter your password" /><button type="button" onClick={() => setShowPassword(!showPassword)} aria-label={showPassword ? 'Hide password' : 'Show password'}>{showPassword ? <EyeOff size={17} /> : <Eye size={17} />}</button></div></label>
        <div className="form-inline"><span>Secure operator access</span><Link to="/forgot-password">Forgot password?</Link></div>
        <button className="button button-primary button-full" disabled={busy}>{busy ? 'Signing in…' : 'Sign in to workspace'}</button>
      </form>
    </AuthFrame>
  )
}

export function RegisterPage() {
  const [fields, setFields] = useState({ username: '', email: '', password: '', confirm_password: '' })
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)
  const [busy, setBusy] = useState(false)
  async function submit(event) {
    event.preventDefault()
    setError('')
    if (fields.password !== fields.confirm_password) return setError('Passwords do not match.')
    const passwordError = validateStrongPassword(fields.password)
    if (passwordError) return setError(passwordError)
    setBusy(true)
    try {
      await register(fields)
      setDone(true)
    } catch (requestError) {
      setError(getApiError(requestError))
    } finally {
      setBusy(false)
    }
  }
  return (
    <AuthFrame title={done ? 'Account created' : 'Create your account'} subtitle={done ? 'Your NMVS operator account is ready.' : 'Register an operator account to access the monitoring console.'}
      footer={<>Already registered? <Link to="/login">Sign in</Link></>}>
      {done ? <div className="success-panel">Registration succeeded. Sign in to continue.</div> : (
        <form className="form-stack" onSubmit={submit}>
          <FormAlert>{error}</FormAlert>
          <label>Username<input autoComplete="username" minLength="3" maxLength="50" required value={fields.username} onChange={(e) => setFields({ ...fields, username: e.target.value })} /></label>
          <label>Email address<input type="email" autoComplete="email" required value={fields.email} onChange={(e) => setFields({ ...fields, email: e.target.value })} /></label>
          <label>Password <small className="field-hint">12+ chars, upper/lowercase, number and symbol</small><input type="password" autoComplete="new-password" minLength="12" required value={fields.password} onChange={(e) => setFields({ ...fields, password: e.target.value })} /></label>
          <label>Confirm password<input type="password" autoComplete="new-password" minLength="12" required value={fields.confirm_password} onChange={(e) => setFields({ ...fields, confirm_password: e.target.value })} /></label>
          <button className="button button-primary button-full" disabled={busy}>{busy ? 'Creating account…' : 'Create account'}</button>
        </form>
      )}
    </AuthFrame>
  )
}

export function ForgotPasswordPage() {
  const [step, setStep] = useState(0)
  const [email, setEmail] = useState('')
  const [otp, setOtp] = useState('')
  const [token, setToken] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()
  async function submit(event) {
    event.preventDefault()
    setError('')
    setBusy(true)
    try {
      if (step === 0) {
        const result = await forgotPassword({ email })
        setMessage(result.message)
        setStep(1)
      } else if (step === 1) {
        const result = await verifyResetOtp({ email, otp })
        setToken(result.reset_token)
        setStep(2)
      } else {
        if (password !== confirmPassword) throw new Error('Passwords do not match.')
        const passwordError = validateStrongPassword(password)
        if (passwordError) throw new Error(passwordError)
        const result = await resetPassword({ token, password, confirm_password: confirmPassword })
        setMessage(result.message)
        setStep(3)
      }
    } catch (requestError) {
      setError(getApiError(requestError))
    } finally {
      setBusy(false)
    }
  }
  return (
    <AuthFrame title={step === 3 ? 'Password updated' : 'Reset your password'} subtitle={step === 0 ? 'Request a password reset code for your account.' : step === 1 ? 'Enter the six-digit OTP sent to your email.' : step === 2 ? 'Choose a new secure password.' : 'You can now sign in with your new password.'}
      footer={<Link to="/login"><ArrowLeft size={14} /> Back to sign in</Link>}>
      <form className="form-stack" onSubmit={submit}>
        <FormAlert>{error}</FormAlert>
        {message && <div className="success-panel">{message}</div>}
        {step === 0 && <label>Email address<input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></label>}
        {step === 1 && <><label>Email address<input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></label><label>Six-digit OTP<input inputMode="numeric" pattern="[0-9]{6}" minLength="6" maxLength="6" required value={otp} onChange={(e) => setOtp(e.target.value)} /></label></>}
        {step === 2 && <><label>New password<input type="password" minLength="12" required value={password} onChange={(e) => setPassword(e.target.value)} /></label><label>Confirm new password<input type="password" minLength="12" required value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} /></label></>}
        {step < 3 && <button className="button button-primary button-full" disabled={busy}>{busy ? 'Please wait…' : step === 0 ? 'Request reset code' : step === 1 ? 'Verify code' : 'Update password'}</button>}
        {step === 3 && <button type="button" className="button button-primary button-full" onClick={() => navigate('/login')}>Return to sign in</button>}
      </form>
    </AuthFrame>
  )
}
