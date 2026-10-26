import api from './axios'

export const getMetricsSummary = () => api.get('/metrics/summary').then((r) => r.data)
export const getUptimeMetrics = (hours = 24) => api.get('/metrics/uptime', { params: { hours } }).then((r) => r.data)
