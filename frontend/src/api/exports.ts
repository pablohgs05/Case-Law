import { apiBaseUrl, assertApiConfiguration } from './client';
import { readDetail, type SearchParams } from './search';

export type ExportParams = Omit<SearchParams, 'page' | 'page_size'>;

export class ExportRequestError extends Error {}

export function exportParams(params: SearchParams): ExportParams {
  const { page: _page, page_size: _size, ...cut } = params;
  return cut;
}

export async function exportPdf(params: ExportParams, signal: AbortSignal) {
  assertApiConfiguration();
  const response = await fetch(`${apiBaseUrl}/exports/pdf`, {
    method: 'POST',
    signal,
    headers: { Accept: 'application/pdf', 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!response.ok) {
    const detail = await readDetail(response);
    throw new ExportRequestError(
      response.status === 409 && detail ? detail : 'Não foi possível gerar o PDF. Tente novamente.',
    );
  }
  const disposition = response.headers.get('Content-Disposition') ?? '';
  const filename = /filename="([^"\r\n]+)"/i.exec(disposition)?.[1];
  if (
    !response.headers.get('Content-Type')?.startsWith('application/pdf') ||
    !filename?.endsWith('.pdf') ||
    /[/\\:]/.test(filename)
  )
    throw new ExportRequestError('A resposta da exportação é inválida. Tente novamente.');
  const buffer = await response.arrayBuffer();
  const bytes = new Uint8Array(buffer);
  const decoder = new TextDecoder();
  const length = response.headers.get('Content-Length');
  if (
    (length !== null && Number(length) !== bytes.length) ||
    !decoder.decode(bytes.slice(0, 5)).startsWith('%PDF-') ||
    !decoder.decode(bytes.slice(-32)).trimEnd().endsWith('%%EOF')
  )
    throw new ExportRequestError('O arquivo recebido está incompleto. Tente novamente.');
  signal.throwIfAborted();
  return { blob: new Blob([buffer], { type: 'application/pdf' }), filename };
}

export function downloadPdf(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.append(anchor);
  try {
    anchor.click();
  } finally {
    anchor.remove();
    // Give the browser time to consume the object URL before releasing it.
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}
