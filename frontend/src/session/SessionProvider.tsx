import { useCallback, useEffect, useState, type ReactNode } from 'react';

import { currentPerson, signIn as callSignIn, signOut as forget } from '../api/accounts';
import { SessionContext, type SessionState } from './sessionContext';

/** Who is using the tool, for the whole interface at once. */
export function SessionProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<SessionState>({ status: 'checking' });

  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    currentPerson({ signal: controller.signal }).then(
      (person) => {
        if (active) {
          setState(person ? { status: 'signed in', person } : { status: 'signed out' });
        }
      },
      () => {
        // The server not answering is not the same as being signed out, but
        // there is nothing to show either way: the tool needs the account.
        if (active) {
          setState({ status: 'signed out' });
        }
      },
    );

    return () => {
      active = false;
      controller.abort();
    };
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    const person = await callSignIn(email, password);
    setState({ status: 'signed in', person });
  }, []);

  const signOut = useCallback(() => {
    forget();
    setState({ status: 'signed out' });
  }, []);

  return (
    <SessionContext.Provider value={{ ...state, signIn, signOut }}>
      {children}
    </SessionContext.Provider>
  );
}
