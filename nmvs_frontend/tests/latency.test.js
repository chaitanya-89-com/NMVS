import assert from 'node:assert/strict'
import test from 'node:test'
import { formatLatencyMilliseconds } from '../src/utils/latency.js'

test('formats device-agent latency as milliseconds without conversion', () => {
  assert.equal(formatLatencyMilliseconds(70), '70 ms')
  assert.equal(formatLatencyMilliseconds(70.25), '70.25 ms')
})

test('shows unavailable for missing or invalid latency', () => {
  assert.equal(formatLatencyMilliseconds(null), '—')
  assert.equal(formatLatencyMilliseconds(undefined), '—')
  assert.equal(formatLatencyMilliseconds(Number.NaN), '—')
  assert.equal(formatLatencyMilliseconds(-1), '—')
})
