import api from './axios'

export const getSettings = () => api.get('/settings/me').then((r) => r.data)
export const updateSettings = (data) => api.patch('/settings/me', data).then((r) => r.data)
export const getProfile = () => api.get('/settings/profile').then((r) => r.data)
export const updateProfile = (data) => api.patch('/settings/profile', data).then((r) => r.data)
