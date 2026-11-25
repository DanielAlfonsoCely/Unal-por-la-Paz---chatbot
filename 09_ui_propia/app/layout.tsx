import type { Metadata, Viewport } from 'next'
import { SUBTITULO, TITULO, LOGO_SRC } from '@/lib/config'
import './globals.css'

export const metadata: Metadata = {
  title: `${TITULO} · Universidad Nacional de Colombia`,
  description: SUBTITULO,
  icons: { icon: LOGO_SRC },
  robots: { index: false, follow: false },
}

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  themeColor: '#5F7E24',
  colorScheme: 'light',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  )
}
