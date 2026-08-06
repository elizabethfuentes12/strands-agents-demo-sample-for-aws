/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_AWS_REGION?: string
  readonly VITE_COGNITO_CLIENT_ID?: string
  readonly VITE_EVENTS_HTTP_DOMAIN?: string
  readonly VITE_EVENTS_REALTIME_DOMAIN?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
