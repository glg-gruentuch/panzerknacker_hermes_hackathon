// Cloudflare Worker for the site. It serves the built files in dist/ and
// forwards POST /api/chat to the chat backend on Nebius, so the browser stays
// on one domain and needs no CORS. Set these in the Worker settings
// (Settings > Variables and Secrets):
//   CHAT_BACKEND_URL    origin of the backend, e.g. https://chat.example.org
//   CHAT_BACKEND_TOKEN  optional; sent as a bearer token so the backend can
//                       refuse calls that do not come through this site

interface Env {
  ASSETS: { fetch(request: Request): Promise<Response> }
  CHAT_BACKEND_URL?: string
  CHAT_BACKEND_TOKEN?: string
}

const detail = (status: number, message: string) => Response.json({ detail: message }, { status })

async function chat(request: Request, env: Env): Promise<Response> {
  if (!env.CHAT_BACKEND_URL) {
    return detail(503, 'The chat backend is not set up yet. Set CHAT_BACKEND_URL in the Cloudflare Worker settings.')
  }
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (env.CHAT_BACKEND_TOKEN) headers.Authorization = `Bearer ${env.CHAT_BACKEND_TOKEN}`

  let res: Response
  try {
    res = await fetch(new URL('/api/chat', env.CHAT_BACKEND_URL), { method: 'POST', headers, body: await request.text() })
  } catch {
    return detail(502, 'The chat backend did not answer. Check that it is running on Nebius.')
  }
  return new Response(res.body, {
    status: res.status,
    headers: { 'Content-Type': res.headers.get('Content-Type') ?? 'application/json' },
  })
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const { pathname } = new URL(request.url)
    if (pathname === '/api/chat') {
      return request.method === 'POST' ? chat(request, env) : detail(405, 'Send chat questions with POST.')
    }
    if (pathname.startsWith('/api/')) return detail(404, 'The site has no such API endpoint. Only /api/chat is live.')
    return env.ASSETS.fetch(request)
  },
}
