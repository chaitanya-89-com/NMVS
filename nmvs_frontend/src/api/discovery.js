import api from './axios'

export const scanNetwork = (network) => api.get('/discovery/scan', { params: { network } }).then((r) => r.data)
export const pingAddress = (ip, port) =>
  api.get(`/discovery/ping/${encodeURIComponent(ip)}`, {
    params: port ? { port } : undefined,
  }).then((r) => r.data)
