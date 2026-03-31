/**
 * apiFetch — drop-in replacement for fetch('/api/...')
 * Automatically injects X-Region header from the current RegionContext value.
 *
 * Usage:
 *   import { apiFetch } from '../utils/apiFetch'
 *   const res = await apiFetch('/api/natal_chart', { method: 'POST', body: JSON.stringify(data) })
 *
 * RegionContext calls setRegionGetter() on mount/update to keep the getter current.
 */

let _getRegion = () => 'GLOBAL'

/** Called by RegionContext to wire up the region getter. */
export function setRegionGetter(fn) {
  _getRegion = fn
}

/** Fetch wrapper that adds Content-Type and X-Region headers. */
export async function apiFetch(path, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    'X-Region': _getRegion(),
    ...options.headers,
  }
  return fetch(path, { ...options, headers })
}
