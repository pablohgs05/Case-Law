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

// The expressions the screen asked the API for, in order.
function searchesMade() {
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
  return searches;
}

const box = () => screen.getByRole('searchbox', { name: 'Pesquisar decisões' });

it('says beside the box that quotation marks search the exact phrase', async () => {
  resetBuffer();
  searchesMade();
  renderApp('/', [], false);
  expect(await screen.findByText(/Use aspas para pesquisar a frase exata/)).toBeVisible();
  expect(screen.getByRole('button', { name: /Exemplo: "prescrição intercorrente"/ })).toBeVisible();
});

it('fills the box with the quoted example, and only searches it when asked', async () => {
  resetBuffer();
  const searches = searchesMade();
  renderApp('/', [], false);
  await userEvent.click(screen.getByRole('button', { name: /Exemplo:/ }));
  expect(box()).toHaveValue('"prescrição intercorrente"');
  expect(box()).toHaveFocus();
  expect(searches).toHaveLength(0);
  await userEvent.click(screen.getByRole('button', { name: 'Pesquisar' }));
  await waitFor(() => expect(searches).toHaveLength(1));
  expect(searches[0].searchParams.get('q')).toBe('"prescrição intercorrente"');
});

it('leaves the expression typed by whoever ignores the hint untouched', async () => {
  resetBuffer();
  const searches = searchesMade();
  renderApp('/', [], false);
  await userEvent.type(box(), 'dano moral in re ipsa');
  await userEvent.click(screen.getByRole('button', { name: 'Pesquisar' }));
  await waitFor(() => expect(searches).toHaveLength(1));
  expect(searches[0].searchParams.get('q')).toBe('dano moral in re ipsa');
  expect(box()).toHaveValue('dano moral in re ipsa');
});
