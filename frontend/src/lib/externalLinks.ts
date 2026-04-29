/**
 * 外链工具：arxiv abs / pdf URL + 系统浏览器打开。
 *
 * Electron 下走 ``window.explore.openExternal`` 调 shell.openExternal；
 * 普通浏览器（dev / 测试）回退到 ``window.open(url, "_blank")``。
 */

const ARXIV_NEW = /^\d{4}\.\d{4,5}(v\d+)?$/;
const ARXIV_OLD = /^[a-z-]+(\.[A-Z]{2})?\/\d{7}(v\d+)?$/;

export function isArxivId(arxivId: string): boolean {
  return ARXIV_NEW.test(arxivId) || ARXIV_OLD.test(arxivId);
}

export function arxivAbsUrl(arxivId: string): string | null {
  if (!isArxivId(arxivId)) return null;
  return `https://arxiv.org/abs/${arxivId}`;
}

export function arxivPdfUrl(arxivId: string): string | null {
  if (!isArxivId(arxivId)) return null;
  return `https://arxiv.org/pdf/${arxivId}.pdf`;
}

export async function openExternal(url: string): Promise<void> {
  const bridge = (window as unknown as {
    explore?: { openExternal?: (u: string) => Promise<void> };
  }).explore;
  if (bridge && typeof bridge.openExternal === "function") {
    await bridge.openExternal(url);
    return;
  }
  window.open(url, "_blank", "noreferrer");
}
