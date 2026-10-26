import api from './axios'

export async function downloadReport(path, fallbackName) {
  let response
  try {
    response = await api.get(path, { responseType: 'blob' })
  } catch (error) {
    const body = error.response?.data
    if (body instanceof Blob) {
      const text = await body.text()
      try {
        const payload = JSON.parse(text)
        if (payload.detail) throw new Error(payload.detail)
      } catch (parseError) {
        if (parseError instanceof SyntaxError) throw error
        throw parseError
      }
    }
    throw error
  }
  const disposition = response.headers['content-disposition']
  const match = disposition?.match(/filename="?([^";]+)"?/i)
  const url = URL.createObjectURL(response.data)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = match?.[1] || fallbackName
  anchor.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
