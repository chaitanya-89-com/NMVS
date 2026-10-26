export function validateStrongPassword(password) {
  if (password.length < 12 || password.length > 128) return 'Password must be between 12 and 128 characters.'
  if (!/[A-Z]/.test(password)) return 'Password must contain at least one uppercase letter.'
  if (!/[a-z]/.test(password)) return 'Password must contain at least one lowercase letter.'
  if (!/[0-9]/.test(password)) return 'Password must contain at least one number.'
  if (!/[^A-Za-z0-9\s]/.test(password)) return 'Password must contain at least one symbol.'
  return ''
}
