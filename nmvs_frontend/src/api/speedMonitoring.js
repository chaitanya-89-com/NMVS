import api from './axios'

export const runSpeedTest = (ip) => api.post(
  '/speed-monitoring/run',
  { ip },
  { timeout: 180000 },
).then((r) => r.data)
export const getDeviceSpeedTestJob = (id) => api.get(`/speed-monitoring/jobs/${id}`).then((r) => r.data)
export const getSpeedHistory = (limit = 20) => api.get('/speed-monitoring/history', { params: { limit } }).then((r) => r.data)
export const deleteSpeedHistory = (id) => api.delete(`/speed-monitoring/history/${id}`).then((r) => r.data)
