import api from './axios'

export const login = (data) => api.post('/auth/login', data).then((r) => r.data)
export const register = (data) => api.post('/auth/register', data).then((r) => r.data)
export const forgotPassword = (data) => api.post('/auth/forgot-password', data).then((r) => r.data)
export const verifyResetOtp = (data) => api.post('/auth/verify-reset-otp', data).then((r) => r.data)
export const resetPassword = (data) => api.post('/auth/reset-password', data).then((r) => r.data)
export const getCurrentUser = () => api.get('/auth/me').then((r) => r.data)
export const changePassword = (data) => api.post('/auth/change-password', data).then((r) => r.data)
