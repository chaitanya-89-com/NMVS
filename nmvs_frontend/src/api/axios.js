import axios from 'axios'

const apiBaseUrl =
  import.meta.env.VITE_API_URL ||
  (import.meta.env.DEV ? 'http://127.0.0.1:8000' : window.location.origin)

const api = axios.create({
  baseURL: apiBaseUrl.replace(/\/+$/, ''),
  headers: { Accept: 'application/json' },
  timeout: 30000,
})

let unauthorizedHandled = false

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('nmvs_access_token')

  if (token) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${token}`
  }

  return config
})

api.interceptors.response.use(
  (response) => {
    unauthorizedHandled = false
    return response
  },
  (error) => {
    const status = error.response?.status
    const requestUrl = error.config?.url || ''

    // Login can return 401 for incorrect credentials.
    // Do not clear an existing session from login/register errors.
    const isPublicAuthRequest =
      /\/auth\/(login|register|forgot-password|verify-reset-otp|reset-password)$/.test(
        requestUrl.split('?')[0],
      )

    if (
      status === 401 &&
      !isPublicAuthRequest &&
      localStorage.getItem('nmvs_access_token') &&
      !unauthorizedHandled
    ) {
      unauthorizedHandled = true
      localStorage.removeItem('nmvs_access_token')
      localStorage.removeItem('nmvs_user')
      window.dispatchEvent(new Event('nmvs:unauthorized'))
    }

    return Promise.reject(error)
  },
)

export function getApiError(error) {
  const detail = error.response?.data?.detail

  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg).join(', ')
  }

  if (typeof detail === 'string') {
    return detail
  }

  if (!error.response) {
    return 'Cannot reach the backend. Check your connection and API URL.'
  }

  return error.message || 'Request failed. Please try again.'
}

export default api
