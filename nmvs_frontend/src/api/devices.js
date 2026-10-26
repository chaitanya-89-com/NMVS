import api from './axios'

export const getDevices = () => api.get('/devices/').then((r) => r.data)
export const getDevice = (id) => api.get(`/devices/${id}`).then((r) => r.data)
export const createDevice = (data) => api.post('/devices/', data).then((r) => r.data)
export const updateDevice = (id, data) => api.put(`/devices/${id}`, data).then((r) => r.data)
export const deleteDevice = (id) => api.delete(`/devices/${id}`).then((r) => r.data)
export const detectDevice = (ip) => api.get(`/devices/detect/${encodeURIComponent(ip)}`).then((r) => r.data)
export const redetectDevice = (id) => api.post(`/devices/${id}/redetect`).then((r) => r.data)
