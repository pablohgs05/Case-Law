import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import { renderApp } from './renderApp';
import { resetBuffer } from '../search/resultsBuffer';

vi.mock('../api/client', () => ({
  apiBaseUrl: 'http://api.test',
  assertApiConfiguration: () => undefined,
}));

afterEach(() => vi.unstubAllGlobals());

it('starts without a search and the example opens real results using the existing search', async () => {
  resetBuffer();
  const searches: URL[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input));
      let body: unknown = { courts: [] };
      if (url.pathname === '/decisions') {
        searches.push(url);
        body = { total: 0, page: 1, page_size: 20, results: [] };
      }
      if (url.pathname === '/exports/options') body = { max_decisions: 1000 };
      return new Response(JSON.stringify(body), {
        headers: { 'Content-Type': 'application/json' },
      });
    }),
  );
  renderApp('/', [], false);
  expect(screen.getByRole('searchbox', { name: 'Pesquisar decisões' })).toHaveValue('');
  expect(screen.getByRole('heading', { name: /Comece pela questão jurídica/ })).toBeVisible();
  expect(screen.queryByRole('tab')).not.toBeInTheDocument();
  expect(
    screen.queryByText(
      /Mapa da tese|Consulte fontes oficiais|Refine por tribunal e período|Chegue aos documentos do resultado/,
    ),
  ).not.toBeInTheDocument();
  expect(searches).toHaveLength(0);
  await userEvent.click(screen.getByRole('button', { name: /Experimentar com um exemplo/ }));
  await waitFor(() => expect(searches).toHaveLength(1));
  expect(searches[0].searchParams.get('q')).toBe('prescrição intercorrente em execução fiscal');
  expect(screen.getByRole('searchbox', { name: 'Pesquisar decisões' })).toHaveValue(
    'prescrição intercorrente em execução fiscal',
  );
  expect(
    screen.queryByRole('heading', { name: /Comece pela questão jurídica/ }),
  ).not.toBeInTheDocument();
  expect(screen.getByRole('tab', { name: 'Documentos' })).toBeVisible();
});
