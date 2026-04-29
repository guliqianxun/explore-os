/**
 * ft-034 P0-7: papers package barrel — splits old 352-line ``api/papers.ts``
 * into 4 modules. Imports of ``@/api/papers`` resolve here (or to the legacy
 * ``papers.ts`` re-export, depending on bundler resolution preference).
 */

export * from "./core";
export * from "./material";
export * from "./claim";
export * from "./brief";
