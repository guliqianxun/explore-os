/**
 * ft-034 P0-7: thin re-export shell — ``api/papers.ts`` 拆为 ``api/papers/``
 * package. This file forwards everything from the package barrel so existing
 * ``import ... from "@/api/papers"`` consumers keep compiling. New code SHOULD
 * import from ``@/api/papers/<module>`` directly.
 *
 * 1-sprint deprecation; v1.3 iter-020 删除该 shell。
 */

export * from "./papers/core";
export * from "./papers/material";
export * from "./papers/claim";
export * from "./papers/brief";
