import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { currentAddress, renderApp } from './renderApp';

// Only the address of the API is replaced: the request code under test is the
// real one, answering what each test says.
vi.mock('../api/client', () => ({
  apiBaseUrl: 'http://api.test',
  assertApiConfiguration: () => undefined,
}));

function decision(identifier: string, caseNumber: string) {
  return {
    source: 'tjdft-jurisdf',
    identifier,
    court: 'TJDFT',
    case_number: caseNumber,
    judging_body: '1ª TURMA CÍVEL',
    reporting_judge: `RELATOR ${identifier}`,
    decided_on: '2026-03-10',
    small_claims: false,
    source_url: `https://jurisdf.tjdft.jus.br/detalhes/${identifier}`,
    source_url_reachable: true,
    class_code: 198,
    judged_on: '2026-03-10',
    published_on: '2026-03-15',
    summary: `Ementa da decisão ${identifier}.`,
    outcome: null,
    full_text_available: true,
    sections: null,
  };
}

// Two decisions of the same case: only the identifier tells them apart.
const FIRST = decision('2000001', '0700001-11.2026.8.07.0001');
const SAME_CASE = decision('2000002', '0700001-11.2026.8.07.0001');
const DECISIONS = [FIRST, SAME_CASE];

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function installApi() {
  const searches: URL[] = [];
  const details: string[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input));
      const detail = url.pathname.match(/^\/decisions\/([^/]+)\/([^/]+)$/);
      if (detail) {
        details.push(url.pathname);
        const found = DECISIONS.find((d) => d.identifier === decodeURIComponent(detail[2]));
        return found ? json(found) : json({ detail: 'Decision not found.' }, 404);
      }
      if (url.pathname === '/decisions') {
        searches.push(url);
        return json({
          total: 2,
          page: 1,
          page_size: 20,
          results: DECISIONS.map((d) => ({ ...d, snippet: `Trecho ${d.identifier}.` })),
        });
      }
      return json({ courts: [] });
    }),
  );
  return { searches, details };
}

const panelHeading = () => screen.findByRole('heading', { level: 2 });

beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('a result', () => {
  it('links to its own address, by collection and identifier', async () => {
    installApi();
    const user = userEvent.setup();
    renderApp();
    await user.click(screen.getByRole('button', { name: 'Pesquisar' }));

    const links = await screen.findAllByRole('link', { name: /Ler a decisão/ });

    expect(links.map((link) => link.getAttribute('href'))).toEqual([
      '/decisoes/tjdft-jurisdf/2000001',
      '/decisoes/tjdft-jurisdf/2000002',
    ]);
  });

  it('opens the decision it names, even when another shares its case number', async () => {
    const api = installApi();
    const user = userEvent.setup();
    renderApp();
    await user.click(screen.getByRole('button', { name: 'Pesquisar' }));
    // The first result shows beside the list, and the address stays the list's.
    expect(await within(screen.getByRole('complementary')).findByText('RELATOR 2000001'));
    expect(currentAddress()).toBe('/');

    const [, second] = await screen.findAllByRole('link', { name: /Ler a decisão/ });
    await user.click(second);

    expect(currentAddress()).toBe('/decisoes/tjdft-jurisdf/2000002');
    const panel = screen.getByRole('complementary');
    expect(await within(panel).findByText('RELATOR 2000002')).toBeInTheDocument();
    expect(api.details).toContain('/decisions/tjdft-jurisdf/2000002');
  });

  it('keeps the official source a link of its own, that does not open the decision', async () => {
    installApi();
    const user = userEvent.setup();
    renderApp();
    await user.click(screen.getByRole('button', { name: 'Pesquisar' }));
    const [first] = await screen.findAllByRole('link', { name: /Ler a decisão/ });
    await user.click(first);
    await waitFor(() => expect(currentAddress()).toBe('/decisoes/tjdft-jurisdf/2000001'));

    const secondCard = screen.getAllByRole('article')[1];
    const official = within(secondCard).getByRole('link', { name: /fonte oficial/i });

    expect(official.closest('a[href^="/decisoes/"]')).toBeNull();
    await user.click(official);
    expect(currentAddress()).toBe('/decisoes/tjdft-jurisdf/2000001');
  });
});

describe('the address of a decision', () => {
  it('opened directly, loads that decision from the API, with no search behind it', async () => {
    const api = installApi();
    renderApp('/decisoes/tjdft-jurisdf/2000002');

    expect(await screen.findByText('RELATOR 2000002')).toBeInTheDocument();
    expect(api.details).toEqual(['/decisions/tjdft-jurisdf/2000002']);
    expect(api.searches).toHaveLength(0);
  });

  it('reloaded, still opens the decision the reader chose, with nothing kept from before', async () => {
    installApi();
    const user = userEvent.setup();
    const { unmount } = renderApp();
    await user.click(screen.getByRole('button', { name: 'Pesquisar' }));
    const [, second] = await screen.findAllByRole('link', { name: /Ler a decisão/ });
    await user.click(second);
    const address = currentAddress()!;

    // A reload: the whole app, session included, gone and started again at
    // the address the reader was on.
    unmount();
    const reloaded = installApi();
    renderApp(address);

    const panel = screen.getByRole('complementary');
    expect(await within(panel).findByText('RELATOR 2000002')).toBeInTheDocument();
    expect(reloaded.details).toEqual(['/decisions/tjdft-jurisdf/2000002']);
    expect(reloaded.searches).toHaveLength(0);
    expect(screen.queryAllByRole('article')).toHaveLength(0);
  });

  it('shows the existing not-found state for a decision that does not exist', async () => {
    installApi();
    renderApp('/decisoes/tjdft-jurisdf/9999999');

    expect(await screen.findByRole('alert')).toHaveTextContent('Decisão não encontrada');
  });

  it('reads identifiers with characters the address has to encode', async () => {
    const api = installApi();
    renderApp('/decisoes/fonte%20teste/abc%2F1');

    await panelHeading();
    expect(api.details).toEqual(['/decisions/fonte%20teste/abc%2F1']);
  });
});
