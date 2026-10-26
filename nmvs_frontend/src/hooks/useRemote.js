import { useCallback, useEffect, useRef, useState } from 'react'

export function useRemote(loader, dependencies = [], pollIntervalMs = 0) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const inFlight = useRef(0)
  const requestSequence = useRef(0)
  const reload = useCallback(async (background = false) => {
    if (background && inFlight.current > 0) return
    const requestId = ++requestSequence.current
    inFlight.current += 1
    if (!background) setLoading(true)
    setError('')
    try {
      const result = await loader()
      if (requestId === requestSequence.current) setData(result)
    } catch (requestError) {
      if (requestId === requestSequence.current) setError(requestError)
    } finally {
      inFlight.current -= 1
      if (requestId === requestSequence.current && !background) setLoading(false)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, dependencies)
  useEffect(() => {
    reload()
    return () => { requestSequence.current += 1 }
  }, [reload])
  useEffect(() => {
    if (!pollIntervalMs) return undefined

    let stopped = false
    let timer
    async function poll() {
      await reload(true)
      if (!stopped) timer = window.setTimeout(poll, pollIntervalMs)
    }

    timer = window.setTimeout(poll, pollIntervalMs)
    return () => {
      stopped = true
      window.clearTimeout(timer)
    }
  }, [reload, pollIntervalMs])
  return { data, setData, loading, error, reload }
}
