export const INVALID_IPV4_MESSAGE = 'Invalid IP address. Please enter a valid IPv4 address.'

export function validateIPv4Address(value) {
  const octets = value.split('.')
  if (
    octets.length !== 4
    || octets.some((octet) => !/^(0|[1-9]\d{0,2})$/.test(octet) || Number(octet) > 255)
  ) {
    return INVALID_IPV4_MESSAGE
  }
  return ''
}
