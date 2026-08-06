export type Lang = 'en' | 'es' | 'pt'

const STORAGE_KEY = 'strands-demos-lang'

export function getStoredLang(): Lang {
  const raw = localStorage.getItem(STORAGE_KEY)
  return raw === 'es' || raw === 'pt' ? raw : 'en'
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
  clickToSee: string
  businessAttr: string
  groundTruth: string
  groundTruthEmpty: string
  nodeDone: string
  graphTopology: string
  memoryState: string
  memoryEmpty: string
  emailsBlocked: string
  emailsLeaked: string
  approve: string
  reject: string
  approvalNeeded: string
  robotsTitle: string
  robotsBody: string
  robotsVideoSoon: string
  robotsHint: string
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
    clickToSee: 'click to see the reasoning',
    businessAttr: 'Business attribute (OTEL span)',
    groundTruth: 'Ground truth (ledger)',
    groundTruthEmpty: 'No bookings recorded yet.',
    memoryState: 'Agent memory (ground truth)',
    memoryEmpty: 'No notes stored.',
    emailsBlocked: 'Exfiltration blocked at the tool boundary — 0 emails left.',
    emailsLeaked: 'email(s) actually left — the gate failed!',
    nodeDone: 'Node finished',
    graphTopology: 'Graph topology (fixed DAG)',
    approve: '✅ Approve',
    reject: '❌ Reject',
    approvalNeeded: 'The agent is frozen, waiting for your decision',
    robotsTitle: 'Strands on Robots',
    robotsBody:
      'The same Strands agents you just chatted with can drive physical robots: the agent loop picks tools like move, look, and speak — same SDK, same hooks, same observability, different body.',
    robotsVideoSoon: 'Video coming soon — imagine a robot arm here taking orders from the Swarm demo.',
    robotsHint: 'Ask the booth staff about running Strands on hardware.',
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
    clickToSee: 'clic para ver el razonamiento',
    businessAttr: 'Atributo de negocio (span OTEL)',
    groundTruth: 'Verdad de terreno (libro mayor)',
    groundTruthEmpty: 'Aún no hay reservas registradas.',
    memoryState: 'Memoria del agente (verdad de terreno)',
    memoryEmpty: 'No hay notas guardadas.',
    emailsBlocked: 'Fuga bloqueada en la frontera de la tool — salieron 0 correos.',
    emailsLeaked: 'correo(s) salieron de verdad — ¡el gate falló!',
    nodeDone: 'Nodo terminado',
    graphTopology: 'Topología del grafo (DAG fijo)',
    approve: '✅ Aprobar',
    reject: '❌ Rechazar',
    approvalNeeded: 'El agente está congelado esperando tu decisión',
    robotsTitle: 'Strands en Robots',
    robotsBody:
      'Los mismos agentes Strands con los que acabas de chatear pueden manejar robots físicos: el agent loop elige tools como moverse, mirar y hablar — mismo SDK, mismos hooks, misma observabilidad, distinto cuerpo.',
    robotsVideoSoon: 'Video próximamente — imagina aquí un brazo robótico recibiendo órdenes del demo de Swarm.',
    robotsHint: 'Pregunta al equipo del stand por Strands en hardware.',
  },
  pt: {
    username: 'Usuário',
    password: 'Senha',
    signIn: 'Entrar',
    signOut: 'Sair',
    connected: '● conectado',
    connecting: '○ conectando…',
    disconnected: '○ desconectado',
    restart: '↺ Reiniciar demo',
    working: 'o agente está trabalhando…',
    typeMessage: 'Digite sua mensagem…',
    send: 'Enviar',
    underHood: '🔬 Por dentro',
    whyInteresting: '🔍 Por que isso é interessante?',
    waiting: 'Aguardando atividade',
    waitingBody:
      'Envie uma mensagem e veja o agent loop em ação: ciclos, chamadas de tools e métricas em tempo real.',
    cycleLabel: 'Ciclo do agent loop',
    reasoning: (cycle: string) => `Raciocinando… (ciclo ${cycle})`,
    toolCall: '🔧 Chamada de tool',
    result: '✅ Resultado',
    blocked: '🔴 Bloqueado',
    cycles: 'ciclos',
    tokens: 'tokens',
    duration: 'duração',
    output: 'saída',
    whyTitle: (title: string) => `🔍 ${title} — por que importa`,
    gotIt: 'Entendi',
    loginIncomplete: 'Login incompleto (requer troca de senha?)',
    sendFailed: 'Falha ao enviar',
    structuredLabel: 'Registro validado',
    nodeActive: 'Agente trabalhando',
    swarmSummary: 'Resumo do swarm',
    phaseRunning: 'Executando',
    phaseDone: 'Concluído',
    phaseNaive: 'Agente naive',
    phasePointer: 'Memory pointer',
    comparisonLabel: 'Comparação de tokens',
    tokensSaved: 'tokens economizados',
    readDocs: 'Leia a documentação do Strands',
    clickToSee: 'clique para ver o raciocínio',
    businessAttr: 'Atributo de negócio (span OTEL)',
    groundTruth: 'Verdade de base (livro-razão)',
    groundTruthEmpty: 'Nenhuma reserva registrada ainda.',
    memoryState: 'Memória do agente (verdade de base)',
    memoryEmpty: 'Nenhuma nota salva.',
    emailsBlocked: 'Exfiltração bloqueada na fronteira da tool — 0 e-mails saíram.',
    emailsLeaked: 'e-mail(s) saíram de verdade — o gate falhou!',
    nodeDone: 'Nó concluído',
    graphTopology: 'Topologia do grafo (DAG fixo)',
    approve: '✅ Aprovar',
    reject: '❌ Rejeitar',
    approvalNeeded: 'O agente está congelado aguardando sua decisão',
    robotsTitle: 'Strands em Robôs',
    robotsBody:
      'Os mesmos agentes Strands com quem você acabou de conversar podem controlar robôs físicos: o agent loop escolhe tools como mover, olhar e falar — mesmo SDK, mesmos hooks, mesma observabilidade, corpo diferente.',
    robotsVideoSoon: 'Vídeo em breve — imagine aqui um braço robótico recebendo ordens do demo de Swarm.',
    robotsHint: 'Pergunte à equipe do estande sobre rodar Strands em hardware.',
  },
}
