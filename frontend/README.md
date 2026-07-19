# ContextIQ — Frontend

Next.js frontend for ContextIQ (Private AI-Powered Document
Intelligence). Talks to the FastAPI backend at the repo root.

**Status: scaffold only — no interface built yet.**

## Stack

- Next.js 15 (App Router) + React 19 + TypeScript
- Tailwind CSS 4
- shadcn/ui (neutral base, CSS variables) + Lucide icons
- Framer Motion (subtle use only, per the design language)
- TanStack Query for all server state
- Dark theme, forced via the `dark` class in `app/layout.tsx`

## Structure

```
app/            # App Router: layout (dark theme, providers), pages
  providers.tsx # TanStack Query client provider
components/
  ui/           # shadcn/ui primitives (generated via `npx shadcn add`)
  chat/         # chat interface components        (next phase)
  sidebar/      # knowledge-base sidebar components (next phase)
  layout/       # app shell components              (next phase)
hooks/          # TanStack Query hooks per API endpoint (next phase)
lib/            # utils (shadcn cn helper), API client to come
```

## Development

```bash
npm install
cp .env.example .env.local   # points at the FastAPI backend
npm run dev                  # http://localhost:3000
```

The backend must be running for API calls to succeed:
`uvicorn api.main:app --port 8000` from the repo root.
