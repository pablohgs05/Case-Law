import { createContext, useContext } from 'react';

import type { Person } from '../api/accounts';

/**
 * The session, apart from the component that provides it.
 *
 * Split for the same reason `headerSearchSlot` is: a file that exports both a
 * component and a hook breaks fast refresh, and the rule that says so is in
 * the project's lint.
 *
 * Three states, and they are not two. `checking` is the moment after a reload
 * when a stored token exists but has not been confirmed yet: folding it into
 * "signed out" bounces people to the login screen on every refresh, and
 * folding it into "signed in" flashes the tool at a stranger.
 */
export type SessionState =
  { status: 'checking' } | { status: 'signed in'; person: Person } | { status: 'signed out' };

export type Session = SessionState & {
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => void;
};

export const SessionContext = createContext<Session | null>(null);

export function useSession(): Session {
  const session = useContext(SessionContext);

  if (!session) {
    throw new Error('useSession precisa estar dentro de <SessionProvider>.');
  }

  return session;
}

/** The signed-in account, or null in the other two states. */
export function useCurrentPerson(): Person | null {
  const session = useSession();
  return session.status === 'signed in' ? session.person : null;
}
