// AppSync Events client: subscribe over WebSocket, publish over HTTP.
// Same protocol validated by scripts/smoke_test.py.
import { config } from '../config'

export interface AgentEvent {
  type:
    | 'token'
    | 'cycle_start'
    | 'tool_call_start'
    | 'tool_result'
    | 'hook_blocked'
    | 'handoff'
    | 'metrics'
    | 'error'
    | 'done'
    // demo-specific insight events
    | 'structured'
    | 'node_start'
    | 'swarm_metrics'
    | 'phase'
    | 'phase_result'
    | 'comparison'
  seq?: number
  [key: string]: unknown
}

function b64url(obj: Record<string, string>): string {
  return btoa(JSON.stringify(obj)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

export class DemoSession {
  private ws: WebSocket | null = null
  private buffer = new Map<number, AgentEvent>()
  private nextSeq = 0
  private doneSeq: number | null = null
  private closedByUser = false
  private reconnectAttempts = 0

  constructor(
    private token: string,
    private demo: string,
    public readonly sessionId: string,
    private onEvent: (e: AgentEvent) => void,
    private onStatus: (s: 'connecting' | 'ready' | 'closed' | 'error') => void,
  ) {}

  async connect(): Promise<void> {
    this.closedByUser = false
    this.onStatus('connecting')
    const auth = { host: config.eventsHttpDomain, authorization: this.token }
    const ws = new WebSocket(`wss://${config.eventsRealtimeDomain}/event/realtime`, [
      'aws-appsync-event-ws',
      `header-${b64url(auth)}`,
    ])
    this.ws = ws

    await new Promise<void>((resolve, reject) => {
      ws.onopen = () => ws.send(JSON.stringify({ type: 'connection_init' }))
      ws.onerror = () => reject(new Error('WebSocket error'))
      ws.onmessage = (msg) => {
        const data = JSON.parse(msg.data)
        if (data.type === 'connection_ack') {
          ws.send(
            JSON.stringify({
              type: 'subscribe',
              id: crypto.randomUUID(),
              channel: `out/${this.demo}/${this.sessionId}`,
              authorization: auth,
            }),
          )
        } else if (data.type === 'subscribe_success') {
          this.reconnectAttempts = 0
          this.onStatus('ready')
          resolve()
        } else if (data.type === 'subscribe_error') {
          reject(new Error(JSON.stringify(data.errors ?? data)))
        } else if (data.type === 'data') {
          this.handleData(data)
        }
      }
      // Auto-reconnect with the SAME sessionId so the conversation (and the
      // agent's memory in its AgentCore microVM) survives a dropped socket.
      ws.onclose = () => {
        if (this.closedByUser) {
          this.onStatus('closed')
          return
        }
        if (this.reconnectAttempts >= 5) {
          this.onStatus('error')
          return
        }
        const delay = Math.min(1000 * 2 ** this.reconnectAttempts, 15000)
        this.reconnectAttempts++
        this.onStatus('connecting')
        window.setTimeout(() => {
          if (!this.closedByUser) this.connect().catch(() => this.onStatus('error'))
        }, delay)
      }
    })
  }

  private gapTimer: number | null = null

  // Events may arrive out of order across publishes; deliver them by seq.
  // If a seq never arrives (dropped event), skip ahead after a short gap
  // instead of stalling the whole stream.
  private handleData(msg: { event: string }): void {
    const event: AgentEvent = JSON.parse(msg.event)
    const seq = event.seq ?? this.nextSeq
    this.buffer.set(seq, event)
    if (event.type === 'done') this.doneSeq = seq
    this.flush()
    if (this.buffer.size > 0 && this.gapTimer === null) {
      this.gapTimer = window.setTimeout(() => {
        this.gapTimer = null
        if (this.buffer.size > 0) {
          this.nextSeq = Math.min(...this.buffer.keys())
          this.flush()
        }
      }, 1200)
    }
  }

  private flush(): void {
    while (this.buffer.has(this.nextSeq)) {
      const e = this.buffer.get(this.nextSeq)!
      this.buffer.delete(this.nextSeq)
      this.nextSeq++
      this.onEvent(e)
    }
    if (this.buffer.size === 0 && this.gapTimer !== null) {
      window.clearTimeout(this.gapTimer)
      this.gapTimer = null
    }
    // A new turn restarts numbering after done was flushed.
    if (this.doneSeq !== null && this.nextSeq > this.doneSeq) {
      this.nextSeq = 0
      this.doneSeq = null
      this.buffer.clear()
    }
  }

  async send(prompt: string): Promise<void> {
    const res = await fetch(`https://${config.eventsHttpDomain}/event`, {
      method: 'POST',
      headers: { 'content-type': 'application/json', authorization: this.token },
      body: JSON.stringify({
        channel: `inbox/${this.demo}/${this.sessionId}`,
        events: [JSON.stringify({ prompt })],
      }),
    })
    if (!res.ok) throw new Error(`Publish failed (${res.status})`)
  }

  close(): void {
    this.closedByUser = true
    this.ws?.close()
    this.ws = null
  }
}

export function newSessionId(): string {
  // AgentCore requires >= 33 chars; dispatcher pads too, belt and suspenders.
  return `web-${crypto.randomUUID().replace(/-/g, '')}`
}
