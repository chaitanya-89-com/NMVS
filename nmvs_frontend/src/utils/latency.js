export function formatLatencyMilliseconds(value) {
  const latency = Number(value)
  return value == null || !Number.isFinite(latency) || latency < 0
    ? '—'
    : `${latency} ms`
}
