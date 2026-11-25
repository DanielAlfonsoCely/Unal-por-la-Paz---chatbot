// ─────────────────────────────────────────────────────────────
// Textos e identidad visibles en la interfaz. Cambia aquí y listo.
// ─────────────────────────────────────────────────────────────

/** Título central del encabezado (temporal). */
export const TITULO = 'Título por definir'

/** Frase breve debajo del título. */
export const SUBTITULO = 'Consulta la producción académica de la Universidad Nacional.'

/**
 * Ruta del logo (archivo dentro de public/). Es provisional: para cambiarlo,
 * reemplaza public/logo-unal.png por el oficial (mismo nombre) o cambia esta ruta.
 * Si el archivo no carga, se muestra un círculo neutro con el texto "UNAL".
 */
export const LOGO_SRC = '/logo-unal.png'

/** Aviso del pie de página. */
export const AVISO =
  'Prototipo en pruebas. Las respuestas se basan solo en documentos del repositorio de la UNAL y pueden contener errores; verifica en las fuentes.'

/** Mensaje de bienvenida si Dify no trae `opening_statement`. */
export const BIENVENIDA_POR_DEFECTO =
  'Hola. Soy el asistente de investigación. Respondo con base en documentos del repositorio de la Universidad Nacional y cito mis fuentes.'

/**
 * Selector de "modo" (preparado para el futuro, oculto por ahora).
 * Para activarlo: MOSTRAR_SELECTOR_MODO = true. El valor elegido se envía en
 * `inputs[VARIABLE_MODO]`, así que el Chatflow debe tener esa variable en el nodo Inicio.
 */
export const MOSTRAR_SELECTOR_MODO = false
export const VARIABLE_MODO = 'modo'
export const MODOS = [
  { valor: 'consultar', etiqueta: 'Consultar documentos' },
  { valor: 'orientar', etiqueta: 'Orientar un proyecto de paz' },
] as const

/** Tiempo máximo sin recibir datos antes de dar la respuesta por perdida (ms). Dify manda "ping" cada ~10 s. */
export const INACTIVIDAD_MAX_MS = 200_000

/** A partir de cuántos ms sin primer token se muestra el aviso de "puede tardar". */
export const AVISO_DEMORA_MS = 15_000
