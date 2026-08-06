# Strands Demos Web App

The single-page front end for the [Strands Agents](https://strandsagents.com/) demo showcase: a chat on the left and a live "under the hood" insights panel on the right that visualizes what each agent is doing in real time.

This is a React + Vite + TypeScript SPA (confirmed in [`package.json`](./package.json): `react` 18, `vite` 6, `typescript` 5, `@vitejs/plugin-react`). It signs in against Amazon Cognito, connects to [AWS AppSync Events](https://docs.aws.amazon.com/appsync/latest/eventapi/event-api-welcome.html) over a WebSocket, publishes prompts, and renders the typed event stream the agents send back. The UI ships in English, Spanish, and Portuguese.

> This front end is part of the larger showcase. For the agents, the shared infra, and the one-command deploy, see the [root README](../README.md). For how the static site is hosted, see [`web-infra/`](../web-infra/).

## Layout: chat plus insights panel

`App.tsx` renders a two-pane workspace once you are signed in:

- **Chat (left):** message bubbles, quick-suggestion buttons per demo, a text input, and a "the agent is working" indicator. `token` events stream in and append to the current agent bubble. Nova's inline `<thinking>...</thinking>` is stripped from the visible bubble. For the human-in-the-loop demo, an approval bar appears when the agent sends an `interrupt` event, with Approve and Reject buttons that call `respondToInterrupt`.
- **Insights panel (right):** the "Under the hood" feed. Every non-`token` event becomes a card: cycles, tool calls, tool results, blocked hooks, handoffs, structured-output records, swarm summaries, graph topology, business attributes, ground-truth ledgers, memory state, chaos injections, and recoveries. A metrics bar at the bottom shows cycles, tokens, duration, and output tokens from the `metrics` event. A "Why is this interesting?" overlay shows the demo's talking points, a code snippet, and a link to the relevant Strands docs.

The left navigation groups demos by category (Fundamentals, Safety & Control, Observability, Multi-agent, Context engineering) plus a Robots placeholder section. Switching demos or pressing "Restart demo" opens a fresh session (new `sessionId`), which resets the agent's memory.

## Internationalization (EN / ES / PT)

All UI strings live in [`src/i18n.ts`](./src/i18n.ts) as a `STRINGS` record keyed by `'en' | 'es' | 'pt'`. The language switch is in the top bar (and on the login screen); the choice is persisted in `localStorage` under `strands-demos-lang`. The per-demo copy (titles, descriptions, suggestions, "why it matters" points) is also translated in all three languages inside [`src/config.ts`](./src/config.ts).

## How it connects to the backend

[`src/services/events.ts`](./src/services/events.ts) holds the `DemoSession` class, the AppSync Events client:

- **Subscribe over WebSocket:** opens `wss://<realtime-domain>/event/realtime` with the `aws-appsync-event-ws` subprotocol and a base64url-encoded auth header, sends `connection_init`, then subscribes to the channel `out/<demo>/<sessionId>`.
- **Publish over HTTP:** `POST https://<http-domain>/event` to the channel `inbox/<demo>/<sessionId>` to send a prompt (or an interrupt response).
- **Ordering:** AppSync fan-out does not guarantee order, so events are buffered by `seq` and flushed in sequence. A dropped `seq` is skipped after a 1.2 second gap so the stream never stalls. Numbering restarts after each `done`.
- **Resilience:** if the socket drops unexpectedly it auto-reconnects with exponential backoff (up to 5 attempts) using the same `sessionId`, so the conversation and the agent's memory survive. A deliberate close (demo switch or logout) does not trigger reconnect.

Auth lives in [`src/services/auth.ts`](./src/services/auth.ts): it calls Cognito's public `InitiateAuth` API with the `USER_PASSWORD_AUTH` flow (no SDK needed), stores the access token in `sessionStorage`, and treats the token as expired 5 minutes before its real expiry.

## Configuration

Runtime config comes from Vite environment variables read in [`src/config.ts`](./src/config.ts):

| Variable | Used for |
|----------|----------|
| `VITE_AWS_REGION` | Cognito endpoint region |
| `VITE_COGNITO_CLIENT_ID` | Cognito user pool client id (login) |
| `VITE_EVENTS_HTTP_DOMAIN` | AppSync Events HTTP endpoint (publish) |
| `VITE_EVENTS_REALTIME_DOMAIN` | AppSync Events realtime endpoint (subscribe) |

These are written to `web/.env.local` by the repo's `deploy.sh` from the deployed stack outputs (see [`deploy.sh`](../deploy.sh) step 5). The file is not committed; if you deploy manually, create it yourself with the four values above. The typed shape of these variables is declared in [`src/vite-env.d.ts`](./src/vite-env.d.ts).

## Run locally

Prerequisites: Node.js 20+ and a deployed backend (so `web/.env.local` exists with real values).

```bash
cd web
npm install
npm run dev      # Vite dev server with hot reload
```

Other scripts (from [`package.json`](./package.json)):

```bash
npm run build    # tsc -b && vite build -> dist/
npm run preview  # serve the production build locally
```

The production build in `dist/` is what the [`web-infra/`](../web-infra/) CDK app uploads to S3 and serves through CloudFront.

## Source layout

```
web/
  index.html            SPA entry (mounts #root, loads src/main.tsx)
  vite.config.ts        Vite config (React plugin)
  tsconfig.json         TypeScript config (strict, react-jsx)
  package.json          scripts + dependencies (React 18, Vite 6, TS 5)
  .env.local            VITE_* config (written by deploy.sh; not committed)
  src/
    main.tsx            React root render
    App.tsx             login, layout, chat, insights cards, metrics, overlay
    config.ts           VITE_* config + per-demo copy (EN/ES/PT), code snippets, docs links
    i18n.ts             Lang type + STRINGS (EN/ES/PT) + language persistence
    styles.css          Strands dark theme
    vite-env.d.ts       typed import.meta.env
    services/
      auth.ts           Cognito USER_PASSWORD_AUTH login + token storage
      events.ts         AppSync Events client (subscribe over WS, publish over HTTP)
  dist/                 production build output (npm run build)
```
