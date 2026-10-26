import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { getCurrentUser, login as loginRequest } from '../api/auth'
import { getApiError } from '../api/axios'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem('nmvs_access_token'))
  const [user, setUser] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('nmvs_user') || 'null')
    } catch {
      return null
    }
  })
  const [checking, setChecking] = useState(Boolean(localStorage.getItem('nmvs_access_token')))
  const [sessionError, setSessionError] = useState('')

  useEffect(() => {
    const unauthorized = () => {
      setToken(null)
      setUser(null)
      setSessionError('Your session expired. Please sign in again.')
    }
    window.addEventListener('nmvs:unauthorized', unauthorized)
    return () => window.removeEventListener('nmvs:unauthorized', unauthorized)
  }, [])

  useEffect(() => {
    if (!token) {
      setChecking(false)
      return
    }
    getCurrentUser()
      .then((profile) => {
        setUser(profile)
        localStorage.setItem('nmvs_user', JSON.stringify(profile))
        setSessionError('')
      })
      .catch((error) => {
        if ([401, 403].includes(error.response?.status)) {
          localStorage.removeItem('nmvs_access_token')
          localStorage.removeItem('nmvs_user')
          setToken(null)
          setUser(null)
        } else {
          setSessionError(`Could not refresh account details: ${getApiError(error)}`)
        }
      })
      .finally(() => setChecking(false))
  }, [token])

  async function signIn(credentials) {
    const result = await loginRequest(credentials)
    localStorage.setItem('nmvs_access_token', result.access_token)
    localStorage.setItem('nmvs_user', JSON.stringify(result.user))
    setToken(result.access_token)
    setUser(result.user)
    setSessionError('')
  }

  function signOut() {
    localStorage.removeItem('nmvs_access_token')
    localStorage.removeItem('nmvs_user')
    setToken(null)
    setUser(null)
    setSessionError('')
  }

  const value = useMemo(() => ({ user, token, checking, sessionError, signIn, signOut }), [user, token, checking, sessionError])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  return useContext(AuthContext)
}
