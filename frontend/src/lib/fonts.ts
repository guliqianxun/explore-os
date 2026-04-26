/**
 * ft-026 web font loader.
 *
 * Strategy: index.html declares `<link>` tags pointing at Google Fonts CDN
 * (Source Serif 4 + Inter). When the renderer is online the browser will
 * fetch and cache them; when offline (Electron prod, no network) the CSS
 * stack falls back to system serif / sans declared in tokens.css.
 *
 * This module is intentionally thin: it exposes `ensureFontsLoaded()` so
 * a future caller could await `document.fonts.ready` for FOUT-sensitive
 * surfaces. We do not block initial render on font loading.
 */

export async function ensureFontsLoaded(): Promise<void> {
  if (typeof document === "undefined" || !("fonts" in document)) return;
  try {
    await (document as Document & { fonts: FontFaceSet }).fonts.ready;
  } catch {
    /* fall back silently to system stack */
  }
}

export const FONT_STACKS = {
  serif: 'var(--font-serif)',
  sans: 'var(--font-sans)',
  mono: 'var(--font-mono)',
} as const;
