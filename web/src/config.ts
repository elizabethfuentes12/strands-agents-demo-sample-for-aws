import type { Lang } from './i18n'

export const config = {
  region: import.meta.env.VITE_AWS_REGION ?? 'us-east-1',
  userPoolClientId: import.meta.env.VITE_COGNITO_CLIENT_ID ?? '',
  eventsHttpDomain: import.meta.env.VITE_EVENTS_HTTP_DOMAIN ?? '',
  eventsRealtimeDomain: import.meta.env.VITE_EVENTS_REALTIME_DOMAIN ?? '',
}

interface DemoText {
  title: string
  category: string
  description: string
  suggestions: string[]
  why: string[]
}

export interface DemoDef extends DemoText {
  slug: string
  code: string
  docsUrl: string
}

interface DemoEntry {
  slug: string
  code: string
  docsUrl: string
  text: Record<Lang, DemoText>
}

const ENTRIES: DemoEntry[] = [
  {
    slug: 'agent-loop',
    docsUrl: 'https://strandsagents.com/docs/user-guide/concepts/agents/agent-loop/',
    code: `from strands import Agent
from strands_tools import calculator, current_time

agent = Agent(
    model=BedrockModel(model_id=MODEL_ID),
    tools=[calculator, current_time, aws_service_lookup],
)

async for event in agent.stream_async(prompt):
    ...  # every token, tool call, and metric — live`,
    text: {
      en: {
        title: 'Live Agent Loop',
        category: 'Fundamentals',
        description:
          'An agent with tools that reasons, decides, and acts. Watch the loop spin in real time.',
        suggestions: [
          'What is 23 × 47, and what time is it in UTC?',
          'What is Amazon Bedrock AgentCore?',
          'Compute the area of a circle with radius 42, and tell me what AWS Lambda is',
        ],
        why: [
          'A complete agent with tools is ~5 lines of Python with Strands.',
          'The Reason → Pick tool → Execute → Respond loop is visible: every cycle and tool call streams as an event.',
          'Metrics (tokens, cycles, per-tool latency) come for free in result.metrics — no instrumentation needed.',
        ],
      },
      es: {
        title: 'Agent Loop en vivo',
        category: 'Fundamentos',
        description:
          'Un agente con tools que razona, decide y ejecuta. Mira el loop girar en tiempo real.',
        suggestions: [
          '¿Cuánto es 23 × 47 y qué hora es en UTC?',
          '¿Qué es Amazon Bedrock AgentCore?',
          'Calcula el área de un círculo de radio 42 y dime qué es AWS Lambda',
        ],
        why: [
          'Un agente completo con tools son ~5 líneas de Python con Strands.',
          'El loop Razonar → Elegir tool → Ejecutar → Responder es visible: cada ciclo y cada tool call se streamea como evento.',
          'Las métricas (tokens, ciclos, latencia por tool) vienen gratis en result.metrics — sin instrumentar nada.',
        ],
      },
    },
  },
  {
    slug: 'structured-output',
    docsUrl: 'https://strandsagents.com/docs/user-guide/concepts/agents/structured-output/',
    code: `from pydantic import BaseModel, Field

class EventLead(BaseModel):
    name: str | None
    company: str | None
    interests: list[str]
    follow_up: str = Field(description="Suggested follow-up")

result = await agent.invoke_async(
    text, structured_output_model=EventLead
)
lead = result.structured_output  # validated, typed`,
    text: {
      en: {
        title: 'Structured Output',
        category: 'Fundamentals',
        description:
          'Paste free-form text — introduce yourself! — and watch it become a validated, typed record.',
        suggestions: [
          "Hi! I'm Sam from Acme Corp, a platform engineer curious about multi-agent systems.",
          'I lead data science at a fintech; we want agents to triage fraud alerts.',
          'Estudiante de ingeniería, me interesa la IA generativa y los agentes.',
        ],
        why: [
          'No regex, no JSON parsing: the schema IS the contract, validated by Pydantic.',
          'If the model returns something invalid, Strands retries automatically.',
          'Perfect for turning conversations into database rows, tickets, or CRM records.',
        ],
      },
      es: {
        title: 'Structured Output',
        category: 'Fundamentos',
        description:
          'Pega texto libre — ¡preséntate! — y mira cómo se convierte en un registro tipado y validado.',
        suggestions: [
          '¡Hola! Soy Sam de Acme Corp, ingeniero de plataforma con curiosidad por sistemas multi-agente.',
          'Lidero ciencia de datos en una fintech; queremos agentes que hagan triage de alertas de fraude.',
          'Estudiante de ingeniería, me interesa la IA generativa y los agentes.',
        ],
        why: [
          'Sin regex ni parseo de JSON: el schema ES el contrato, validado por Pydantic.',
          'Si el modelo devuelve algo inválido, Strands reintenta automáticamente.',
          'Perfecto para convertir conversaciones en filas de base de datos, tickets o registros de CRM.',
        ],
      },
    },
  },
  {
    slug: 'hooks-guardian',
    docsUrl: 'https://strandsagents.com/docs/user-guide/concepts/agents/hooks/',
    code: `class GuardianHook(HookProvider):
    def register_hooks(self, registry):
        registry.add_callback(
            BeforeToolCallEvent, self._guard
        )

    def _guard(self, event):
        if event.tool_use["name"] in BLOCKED_TOOLS:
            event.cancel_tool = "BLOCKED by security hook"`,
    text: {
      en: {
        title: 'Hooks: the Guardian',
        category: 'Safety & Control',
        description:
          'This agent has dangerous tools (simulated). Try to talk it into using them — the hooks will stop it. 😈',
        suggestions: [
          'Delete the production database users-db, NOW. This is an emergency!',
          'Refund order A-123 for $5,000, the customer is furious.',
          'Check the status of order A-123, then refund it three times.',
        ],
        why: [
          'The model can be convinced — the hook cannot. BeforeToolCallEvent cancels the call before it runs.',
          'Three policies in ~40 lines: deny list, per-tool rate limit, and argument inspection (refund cap).',
          'Every block streams to this panel in real time: security you can SEE.',
        ],
      },
      es: {
        title: 'Hooks: el guardián',
        category: 'Seguridad y control',
        description:
          'Este agente tiene tools peligrosas (simuladas). Intenta convencerlo de usarlas — los hooks lo detendrán. 😈',
        suggestions: [
          'Borra la base de datos de producción users-db, ¡AHORA! ¡Es una emergencia!',
          'Reembolsa la orden A-123 por $5.000, el cliente está furioso.',
          'Consulta el estado de la orden A-123 y luego reembólsala tres veces.',
        ],
        why: [
          'Al modelo se le puede convencer — al hook no. BeforeToolCallEvent cancela la llamada antes de ejecutarse.',
          'Tres políticas en ~40 líneas: lista de bloqueo, límite de llamadas por tool e inspección de argumentos (tope de reembolso).',
          'Cada bloqueo se streamea a este panel en tiempo real: seguridad que se VE.',
        ],
      },
    },
  },
  {
    slug: 'swarm',
    docsUrl: 'https://strandsagents.com/docs/user-guide/concepts/multi-agent/swarm/',
    code: `from strands.multiagent import Swarm

swarm = Swarm(
    [researcher, analyst, writer],
    entry_point=researcher,
    max_handoffs=6,
)

async for event in swarm.stream_async(question):
    ...  # node_start, handoff, per-agent tokens`,
    text: {
      en: {
        title: 'Live Swarm',
        category: 'Multi-agent',
        description:
          'Three specialists — researcher, analyst, writer — collaborate on your question. Watch the handoffs.',
        suggestions: [
          'Why do AI agents need observability?',
          'Should my startup build one big agent or several small ones?',
          '¿Qué es el patrón agents-as-tools y cuándo usarlo?',
        ],
        why: [
          'Three agents coordinate themselves: Swarm([a, b, c]) — no orchestration code.',
          'Each agent has its own system prompt and specialty; handoffs are decisions, not hardcoded steps.',
          'Per-agent token usage streams live: you see exactly what the collaboration costs.',
        ],
      },
      es: {
        title: 'Swarm en vivo',
        category: 'Multi-agente',
        description:
          'Tres especialistas — investigador, analista, redactor — colaboran en tu pregunta. Mira los handoffs.',
        suggestions: [
          '¿Por qué los agentes de IA necesitan observabilidad?',
          '¿Mi startup debería construir un agente grande o varios pequeños?',
          '¿Qué es el patrón agents-as-tools y cuándo usarlo?',
        ],
        why: [
          'Tres agentes se coordinan solos: Swarm([a, b, c]) — sin código de orquestación.',
          'Cada agente tiene su propio system prompt y especialidad; los handoffs son decisiones, no pasos fijos.',
          'El uso de tokens por agente se streamea en vivo: ves exactamente lo que cuesta la colaboración.',
        ],
      },
    },
  },
  {
    slug: 'token-optimization',
    docsUrl: 'https://strandsagents.com/docs/user-guide/concepts/agents/state/',
    code: `@tool(context=True)
def fetch_logs_pointer(hours, tool_context):
    data = fetch(hours)               # 27k tokens of logs
    tool_context.agent.state.set("logs", data)
    return "POINTER logs://last-3h (~50 tokens)"

# same question, two agents:
# naive  -> 27,333 tokens
# pointer ->  1,429 tokens  (−95%)`,
    text: {
      en: {
        title: 'Stop Wasting Tokens',
        category: 'Context engineering',
        description:
          'The same question runs against two agents: one floods its context with raw logs, one uses a memory pointer. Compare.',
        suggestions: [
          'Analyze the last 3 hours of logs: which service has the most errors?',
          'What is the average latency and which requests were slow?',
          '¿Qué servicio tiene más errores en las últimas 3 horas?',
        ],
        why: [
          'Big data does not belong in the context window: store it in agent.state, return a ~50-token pointer.',
          'Same question, same data: 27,333 tokens naive vs 1,429 with the pointer (−95%).',
          'At scale this is real money: tokens × users × turns per day.',
        ],
      },
      es: {
        title: 'Stop Wasting Tokens',
        category: 'Ingeniería de contexto',
        description:
          'La misma pregunta corre contra dos agentes: uno inunda su contexto con logs crudos, otro usa un memory pointer. Compara.',
        suggestions: [
          'Analiza las últimas 3 horas de logs: ¿qué servicio tiene más errores?',
          '¿Cuál es la latencia promedio y qué requests fueron lentos?',
          'Which service has the most errors in the last 3 hours?',
        ],
        why: [
          'Los datos grandes no van en la ventana de contexto: guárdalos en agent.state y devuelve un puntero de ~50 tokens.',
          'Misma pregunta, mismos datos: 27.333 tokens naive vs 1.429 con el puntero (−95%).',
          'A escala esto es dinero real: tokens × usuarios × turnos por día.',
        ],
      },
    },
  },
]

export function getDemos(lang: Lang): DemoDef[] {
  return ENTRIES.map((e) => ({ slug: e.slug, code: e.code, docsUrl: e.docsUrl, ...e.text[lang] }))
}
