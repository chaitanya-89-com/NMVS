import api from './axios'

export const getDashboardOverview = () => api.get('/dashboard/overview').then((r) => r.data)
