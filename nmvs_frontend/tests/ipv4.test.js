import assert from 'node:assert/strict'
import test from 'node:test'

import { INVALID_IPV4_MESSAGE, validateIPv4Address } from '../src/utils/ipv4.js'

test('accepts valid four-octet IPv4 addresses', () => {
  assert.equal(validateIPv4Address('10.20.56.217'), '')
  assert.equal(validateIPv4Address('0.0.0.0'), '')
  assert.equal(validateIPv4Address('255.255.255.255'), '')
})

test('rejects malformed and out-of-range IPv4 addresses', () => {
  for (const address of [
    '10.20.56.888',
    '0.0.9.-90',
    '10.20.56',
    '10.20.56.abc',
    '10.20.56.217.5',
    '',
    '10.20.56.01',
  ]) {
    assert.equal(validateIPv4Address(address), INVALID_IPV4_MESSAGE, address)
  }
})
