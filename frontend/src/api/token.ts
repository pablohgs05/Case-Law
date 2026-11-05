/**
 * The session token, and the headers every call carries.
 *
 * Its own module, apart from `client`. The suites mock `client` to neutralise
 * the API address, with a factory that lists what it returns — so an export
 * added there silently becomes `undefined` in seventeen test files. The token
 * is a different concern anyway: `client` answers *where* the API is, this
 * answers *who is asking*.
 */

// The session token, kept in one place so no caller has to know where it
// lives. `sessionStorage` and not `localStorage`: closing the tab ends the
// session, which is what someone working on a shared machine expects.
const TOKEN_KEY = 'case-law:session';

let token: string | null = readStored();

function readStored(): string | null {
  try {
    return window.sessionStorage.getItem(TOKEN_KEY);
  } catch {
    // Private windows and blocked site data throw rather than return null.
    // The session still works; it just will not survive a reload.
    return null;
  }
}

export function sessionToken(): string | null {
  return token;
}

export function rememberSession(value: string | null) {
  token = value;
  try {
    if (value) {
      window.sessionStorage.setItem(TOKEN_KEY, value);
    } else {
      window.sessionStorage.removeItem(TOKEN_KEY);
    }
  } catch {
    // Nothing to do: the token stays in memory for this tab.
  }
}

/**
 * The headers every call to this API carries.
 *
 * Declared here and used by every module, so a request that forgets the token
 * is a request that forgot the headers entirely — which fails loudly instead
 * of quietly coming back 401.
 */
export function apiHeaders(extra: Record<string, string> = {}): Record<string, string> {
  return {
    Accept: 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...extra,
  };
}
