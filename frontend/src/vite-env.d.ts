/// <reference types="vite/client" />

// Vite handles `?url` imports of any asset (including the pdfjs worker bundle)
// by emitting a string URL. This declaration tells TS to treat any `?url`
// suffix as `string`, which keeps `react-pdf` worker setup type-clean.
declare module "*?url" {
  const src: string;
  export default src;
}
