import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import ExportAction from '../components/ExportAction';
import { exportParams } from '../api/exports';
import { resetBuffer } from '../search/resultsBuffer';
import { renderApp } from './renderApp';

vi.mock('../api/client', () => ({
  apiBaseUrl: 'http://api.test',
  assertApiConfiguration: () => undefined,
}));
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
const pdf = (body = '%PDF-1.7\ncomplete\n%%EOF', length?: number) =>
  new Response(body, {
    headers: {
      'Content-Type': 'application/pdf',
      'Content-Disposition': 'attachment; filename="case-law-recorte-dano-moral-2026-10-23.pdf"',
      ...(length === undefined ? {} : { 'Content-Length': String(length) }),
    },
  });
const params = {
  q: '"dano moral"',
  tribunal: ['STJ'],
  relator: ['RELATOR A'],
  classe_cnj: [198],
  date_from: '2024-01-01',
  order: 'date' as const,
};
let downloads: string[];
beforeEach(() => {
  resetBuffer();
  downloads = [];
  Object.defineProperty(URL, 'createObjectURL', {
    configurable: true,
    value: vi.fn(() => 'blob:pdf-test'),
  });
  Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() });
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
    this: HTMLAnchorElement,
  ) {
    downloads.push(this.download);
  });
});
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function api(answer: () => Response | Promise<Response> = () => pdf()) {
  const posts: RequestInit[] = [];
  const signals: AbortSignal[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input));
      if (url.pathname === '/exports/options')
        throw new Error('Export must not depend on a limit lookup');
      if (url.pathname === '/exports/pdf') {
        posts.push(init!);
        signals.push(init!.signal as AbortSignal);
        return answer();
      }
      if (url.pathname === '/courts')
        return json({ courts: [{ abbreviation: 'STJ', name: 'STJ' }] });
      if (url.pathname === '/filters')
        return json({ judging_bodies: [], reporting_judges: [], procedural_classes: [] });
      if (url.pathname === '/decisions')
        return json({
          total: 7,
          page: 1,
          page_size: 12,
          results: [
            {
              source: 'test',
              identifier: '1',
              court: 'STJ',
              case_number: 'processo-1',
              judging_body: null,
              reporting_judge: null,
              decided_on: '2024-01-01',
              small_claims: null,
              source_url: 'https://example.test',
              source_url_reachable: true,
              deliberation: null,
              snippet: 'Dano moral.',
            },
          ],
        });
      throw new Error(`Unexpected request ${url.pathname}`);
    }),
  );
  return { posts, signals };
}
async function ready() {
  const button = screen.getByRole('button', { name: /Exportar recorte/ });
  await waitFor(() => expect(button).toBeEnabled());
  return button;
}

it('shows ready, generating and complete; rapid double click makes one download', async () => {
  let resolve!: (response: Response) => void;
  const pending = new Promise<Response>((done) => {
    resolve = done;
  });
  const { posts } = api(() => pending);
  render(<ExportAction params={params} total={19} disabled={false} />);
  const button = await ready();
  expect(button).toHaveTextContent('19 decisões');
  expect(screen.getByText(/O PDF inclui todas as decisões/)).toBeVisible();
  fireEvent.click(button);
  fireEvent.click(button);
  expect(screen.getByRole('button', { name: 'Gerando PDF...' })).toBeDisabled();
  expect(screen.getByRole('status')).toHaveTextContent('Aguarde a conclusão');
  expect(posts).toHaveLength(1);
  expect(downloads).toEqual([]);
  await act(async () => {
    resolve(pdf());
  });
  await screen.findByText('PDF gerado e enviado para download.');
  expect(downloads).toEqual(['case-law-recorte-dano-moral-2026-10-23.pdf']);
  expect(JSON.parse(posts[0].body as string)).toEqual(params);
});

it('failure produces no download and retry can complete', async () => {
  let failed = true;
  const { posts } = api(() => (failed ? json({ detail: 'render failure' }, 503) : pdf()));
  render(<ExportAction params={params} total={19} disabled={false} />);
  fireEvent.click(await ready());
  expect(await screen.findByRole('alert')).toHaveTextContent('Não foi possível gerar o PDF');
  expect(downloads).toEqual([]);
  failed = false;
  fireEvent.click(screen.getByRole('button', { name: 'Tentar exportar novamente' }));
  await screen.findByText('PDF gerado e enviado para download.');
  expect(posts).toHaveLength(2);
  expect(downloads).toHaveLength(1);
});

it.each([
  ['%PDF-1.7\ncut midway', undefined],
  ['%PDF-1.7\ncut\n%%EOF', 1000],
] as const)('rejects incomplete bytes before creating any download', async (body, length) => {
  api(() => pdf(body, length));
  render(<ExportAction params={params} total={19} disabled={false} />);
  fireEvent.click(await ready());
  expect(await screen.findByRole('alert')).toHaveTextContent('incompleto');
  expect(downloads).toEqual([]);
  expect(URL.createObjectURL).not.toHaveBeenCalled();
});

it('disables an empty cut before requesting a PDF', async () => {
  const { posts } = api();
  render(<ExportAction params={params} total={0} disabled={false} />);
  await screen.findByText(/Não há decisões/);
  const button = screen.getByRole('button', { name: /Exportar recorte/ });
  expect(button).toBeDisabled();
  fireEvent.click(button);
  expect(posts).toEqual([]);
});

it.each([1001, 46967])(
  'allows exporting all %i decisions without a limit lookup',
  async (total) => {
    const { posts } = api();
    render(<ExportAction params={params} total={total} disabled={false} />);
    fireEvent.click(await ready());
    await screen.findByText('PDF gerado e enviado para download.');
    expect(posts).toHaveLength(1);
    expect(downloads).toHaveLength(1);
  },
);

it('aborts on leaving and ignores a response that arrives after unmount', async () => {
  let resolve!: (response: Response) => void;
  const pending = new Promise<Response>((done) => {
    resolve = done;
  });
  const { signals } = api(() => pending);
  const view = render(<ExportAction params={params} total={19} disabled={false} />);
  fireEvent.click(await ready());
  view.unmount();
  expect(signals[0].aborted).toBe(true);
  await act(async () => {
    resolve(pdf());
  });
  expect(downloads).toEqual([]);
});

it('exports the applied search from results, never drafts or visible pagination', async () => {
  const { posts } = api();
  const user = userEvent.setup();
  renderApp();
  await user.click(screen.getByRole('button', { name: 'Pesquisar' }));
  await ready();
  const input = screen.getByRole('searchbox', { name: 'Pesquisar decisões' });
  await user.clear(input);
  await user.type(input, 'rascunho que não foi aplicado');
  fireEvent.click(screen.getByRole('button', { name: /Exportar recorte/ }));
  await screen.findByText('PDF gerado e enviado para download.');
  const sent = JSON.parse(posts[0].body as string);
  expect(sent.q).toBe('prescrição intercorrente em execução fiscal');
  expect(sent.order).toBe('relevance');
  expect(sent).not.toHaveProperty('page');
  expect(sent).not.toHaveProperty('page_size');
  expect(exportParams({ ...params, page: 8, page_size: 6 })).toEqual(params);
});

it('applying a different search cancels the previous export and suppresses its late download', async () => {
  let resolve!: (response: Response) => void;
  const pending = new Promise<Response>((done) => {
    resolve = done;
  });
  const { signals } = api(() => pending);
  const user = userEvent.setup();
  renderApp();
  await user.click(screen.getByRole('button', { name: 'Pesquisar' }));
  fireEvent.click(await ready());
  const input = screen.getByRole('searchbox', { name: 'Pesquisar decisões' });
  await user.clear(input);
  await user.type(input, 'outro recorte');
  await user.click(screen.getByRole('button', { name: 'Pesquisar' }));
  await ready();
  expect(signals[0].aborted).toBe(true);
  await act(async () => {
    resolve(pdf());
  });
  expect(downloads).toEqual([]);
});
