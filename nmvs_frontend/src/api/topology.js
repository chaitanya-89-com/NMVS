import api from './axios'

export const getTopology = (params = {}) => api.get('/topology/graph', {
  params,
  headers: { 'Cache-Control': 'no-cache' },
}).then((r) => r.data)
export const getDiscoveryTopology = (network, autoRegister = false) =>
  api.get('/topology/discovery', {
    params: { network, auto_register: autoRegister, refresh: Date.now() },
    headers: { 'Cache-Control': 'no-cache' },
  }).then((r) => r.data)
export const getHiddenTopologyDevices = () =>
  api.get('/topology/hidden-devices', { headers: { 'Cache-Control': 'no-cache' } }).then((r) => r.data)
export const removeTopologyDevice = (deviceId) =>
  api.post(`/topology/devices/${deviceId}/remove`).then((r) => r.data)
export const restoreTopologyDevice = (deviceId) =>
  api.post(`/topology/devices/${deviceId}/restore`).then((r) => r.data)
