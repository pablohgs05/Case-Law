import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import App, { Tool } from '../App';
import type { Person } from '../api/accounts';
import { SessionContext, type Session } from '../session/sessionContext';
import AddressProbe from './AddressProbe';

// Everything behind the door needs somebody at it. These suites are about the
// search, not about signing in, so they mount the tool with a session already
// granted — the door itself is covered in `contas.test.tsx`.
export const SIGNED_IN: Person = {
  id: '7c3f1f0e-2a5b-4c9d-8e1f-6b2d9a4c7e35',
  name: 'Ana Almeida Costa',
  email: 'ana@almeidacosta.com.br',
  phone: null,
  role: 'gerente',
  active: true,
};

function session(person: Person | null): Session {
  return {
    ...(person ? { status: 'signed in' as const, person } : { status: 'signed out' as const }),
    signIn: async () => undefined,
    signOut: () => undefined,
  };
}

// The screen with its real routes, at any address — as when a link is opened
// directly or the page is reloaded there. `before` are entries already in the
// history behind it, for a test to tell where Back leads.
// `person` comes last on purpose: the suites that opt out of the prepared
// expression pass the third argument positionally, and moving it would have
// meant touching every one of them for a reason that is not theirs.
export function renderApp(
  path = '/',
  before: string[] = [],
  prefillSearch = true,
  person: Person | null = SIGNED_IN,
) {
  const view = render(
    <MemoryRouter initialEntries={[...before, path]} initialIndex={before.length}>
      <SessionContext.Provider value={session(person)}>
        <Tool />
      </SessionContext.Provider>
      <AddressProbe />
    </MemoryRouter>,
  );
  // Existing search-flow tests start with a prepared expression. The real
  // landing page starts empty; its own test opts out of this fixture.
  const input = screen.queryByRole('searchbox', { name: 'Pesquisar decisões' });
  if (prefillSearch && input && !(input as HTMLInputElement).value) {
    fireEvent.change(input, { target: { value: 'prescrição intercorrente em execução fiscal' } });
  }
  return view;
}

/** The whole application, door included, for the tests that are about it. */
export function renderWholeApp(path = '/') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

export const currentAddress = () => screen.getByTestId('address').textContent;
