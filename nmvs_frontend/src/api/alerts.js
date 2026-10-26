import api from './axios'

export const getAlerts = (params = {}) => api.get('/alerts', { params }).then((r) => r.data)
export const getAlertsSummary = () => api.get('/alerts/summary').then((r) => r.data)
export const acknowledgeAlert = (id) => api.put(`/alerts/${id}/acknowledge`).then((r) => r.data)
export const resolveAlert = (id) => api.put(`/alerts/${id}/resolve`).then((r) => r.data)
export const deleteAlert = (id) => api.delete(`/alerts/${id}`).then((r) => r.data)
