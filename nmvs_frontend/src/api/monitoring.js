import api from './axios'

export const getMonitoringHistory = (limit = 100, days) =>
  api.get('/monitoring/history', { params: { limit, ...(days ? { days } : {}) } }).then((r) => r.data)
export const getDeviceHistory = (ip, limit = 100, days) =>
  api.get(`/monitoring/history/${encodeURIComponent(ip)}`, {
    params: { limit, ...(days ? { days } : {}) },
  }).then((r) => r.data)
export const getDeviceAvailability = (days = 7) =>
  api.get('/monitoring/availability', { params: { days } }).then((r) => r.data)
export const checkDevice = (ip) => api.get(`/monitoring/check/${encodeURIComponent(ip)}`).then((r) => r.data)
export const clearMonitoringHistory = () => api.delete('/monitoring/history').then((r) => r.data)
