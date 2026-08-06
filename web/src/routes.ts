// Lightweight URL routing for the SPA (no router dependency).
//
// Each demo has a direct URL path so visitors can deep-link straight to it,
// e.g. /agent_loop, /structured_output, /hooks. CloudFront rewrites 403/404 to
// /index.html (see web-infra/stacks/web_stack.py), so these paths resolve to
// the SPA on a static S3 + CloudFront deploy as well as under `vite dev`.
import { DEMO_SLUGS } from './config'

export const ROBOTS_ROUTE = 'robots'

// path segment (no leading slash) -> canonical demo slug.
// Canonical path is the slug with underscores (/agent_loop). We also accept the
// slug itself (/agent-loop) and a few short, memorable aliases.
const ALIASES: Record<string, string> = {
  hooks: 'hooks-guardian',
  guardian: 'hooks-guardian',
  hitl: 'human-in-the-loop',
  tokens: 'token-optimization',
  memory: 'memory-poisoning',
  chaos: 'chaos-resilience',
  xray: 'observability',
}

function pathToSlug(): Record<string, string> {
  const map: Record<string, string> = {}
  for (const slug of DEMO_SLUGS) {
    map[slug] = slug // hyphen form: /agent-loop
    map[slug.replace(/-/g, '_')] = slug // underscore form: /agent_loop
  }
  for (const [alias, slug] of Object.entries(ALIASES)) map[alias] = slug
  return map
}

const PATH_TO_SLUG = pathToSlug()

export interface Route {
  robots: boolean
  slug: string
}

function normalize(pathname: string): string {
  return pathname.replace(/^\/+/, '').replace(/\/+$/, '').toLowerCase()
}

/** Parse the current location into a route. Unknown paths fall back to the first demo. */
export function parseRoute(pathname: string, fallbackSlug: string): Route {
  const seg = normalize(pathname)
  if (seg === ROBOTS_ROUTE) return { robots: true, slug: fallbackSlug }
  const slug = PATH_TO_SLUG[seg]
  return { robots: false, slug: slug ?? fallbackSlug }
}

/** Canonical URL path for a demo slug (underscore form). */
export function slugToPath(slug: string): string {
  return '/' + slug.replace(/-/g, '_')
}

/** Push a new route into the address bar without reloading the page. */
export function pushRoute(path: string): void {
  if (window.location.pathname !== path) {
    window.history.pushState({}, '', path)
  }
}
