export type Lang = 'en' | 'es'

const STORAGE_KEY = 'strands-demos-lang'

export function getStoredLang(): Lang {
  const raw = localStorage.getItem(STORAGE_KEY)
  return raw === 'es' ? 'es' : 'en'
}

export function storeLang(lang: Lang): void {
  localStorage.setItem(STORAGE_KEY, lang)
}

export interface Strings {
  username: string
  password: string
  signIn: string
  signOut: string
  connected: string
  connecting: string
  disconnected: string
  restart: string
  working: string
  typeMessage: string
  send: string
  underHood: string
  whyInteresting: string
  waiting: string
  waitingBody: string
  cycleLabel: string
  reasoning: (cycle: string) => string
  toolCall: string
  result: string
  blocked: string
  cycles: string
  tokens: string
  duration: string
  output: string
  whyTitle: (title: string) => string
  gotIt: string
  loginIncomplete: string
  sendFailed: string
  structuredLabel: string
  nodeActive: string
  swarmSummary: string
  phaseRunning: string
  phaseDone: string
  phaseNaive: string
  phasePointer: string
  comparisonLabel: string
  tokensSaved: string
  readDocs: string
}

export const STRINGS: Record<Lang, Strings> = {
  en: {
    username: 'Username',
    password: 'Password',
    signIn: 'Sign in',
    signOut: 'Sign out',
    connected: '● connected',
    connecting: '○ connecting…',
    disconnected: '○ disconnected',
    restart: '↺ Restart demo',
    working: 'the agent is working…',
    typeMessage: 'Type your message…',
    send: 'Send',
    underHood: '🔬 Under the hood',
    whyInteresting: '🔍 Why is this interesting?',
    waiting: 'Waiting for activity',
    waitingBody:
      'Send a message and watch the agent loop in action: cycles, tool calls, and metrics in real time.',
    cycleLabel: 'Agent loop cycle',
    reasoning: (cycle: string) => `Reasoning… (cycle ${cycle})`,
    toolCall: '🔧 Tool call',
    result: '✅ Result',
    blocked: '🔴 Blocked',
    cycles: 'cycles',
    tokens: 'tokens',
    duration: 'duration',
    output: 'output',
    whyTitle: (title: string) => `🔍 ${title} — why it matters`,
    gotIt: 'Got it',
    loginIncomplete: 'Login incomplete (password change required?)',
    sendFailed: 'Failed to send',
    structuredLabel: 'Validated record',
    nodeActive: 'Agent working',
    swarmSummary: 'Swarm summary',
    phaseRunning: 'Running',
    phaseDone: 'Finished',
    phaseNaive: 'Naive agent',
    phasePointer: 'Memory pointer',
    comparisonLabel: 'Token comparison',
    tokensSaved: 'tokens saved',
    readDocs: 'Read the Strands docs',
  },
  es: {
    username: 'Usuario',
    password: 'Contraseña',
    signIn: 'Entrar',
    signOut: 'Salir',
    connected: '● conectado',
    connecting: '○ conectando…',
    disconnected: '○ desconectado',
    restart: '↺ Reiniciar demo',
    working: 'el agente está trabajando…',
    typeMessage: 'Escribe tu mensaje…',
    send: 'Enviar',
    underHood: '🔬 Qué pasa por dentro',
    whyInteresting: '🔍 ¿Por qué es interesante?',
    waiting: 'Esperando actividad',
    waitingBody:
      'Envía un mensaje y mira el agent loop en acción: ciclos, tool calls y métricas en tiempo real.',
    cycleLabel: 'Ciclo del agent loop',
    reasoning: (cycle: string) => `Razonando… (ciclo ${cycle})`,
    toolCall: '🔧 Tool call',
    result: '✅ Resultado',
    blocked: '🔴 Bloqueado',
    cycles: 'ciclos',
    tokens: 'tokens',
    duration: 'duración',
    output: 'salida',
    whyTitle: (title: string) => `🔍 ${title} — por qué importa`,
    gotIt: 'Entendido',
    loginIncomplete: 'Login incompleto (¿requiere cambio de contraseña?)',
    sendFailed: 'Error al enviar',
    structuredLabel: 'Registro validado',
    nodeActive: 'Agente trabajando',
    swarmSummary: 'Resumen del swarm',
    phaseRunning: 'Ejecutando',
    phaseDone: 'Terminado',
    phaseNaive: 'Agente naive',
    phasePointer: 'Memory pointer',
    comparisonLabel: 'Comparación de tokens',
    tokensSaved: 'tokens ahorrados',
    readDocs: 'Lee la documentación de Strands',
  },
}
