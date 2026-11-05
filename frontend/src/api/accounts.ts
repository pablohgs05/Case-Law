import { apiBaseUrl, assertApiConfiguration } from './client';
import { apiHeaders, rememberSession } from './token';

/**
 * Signing in, and a manager running their company's access.
 *
 * The token lives in `client.ts` and is attached to every call from there, so
 * nothing outside this module ever handles it.
 */

export type Role = 'usuario' | 'gerente';

export type Person = {
  id: string;
  name: string;
  email: string;
  phone: string | null;
  role: Role;
  active: boolean;
};

export class AccountError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'AccountError';
    this.status = status;
  }
}

const REFUSED = 'E-mail ou senha incorretos, ou o acesso desta conta foi revogado.';
const UNREACHABLE = 'Não foi possível falar com o servidor. Verifique a conexão.';

const text = (value: unknown) => (typeof value === 'string' && value.trim() ? value.trim() : null);

function readPerson(value: unknown): Person | null {
  const row = (value ?? {}) as Record<string, unknown>;
  const id = text(row.id);
  const name = text(row.name);
  const role = text(row.role);

  if (!id || !name || (role !== 'usuario' && role !== 'gerente')) {
    return null;
  }

  return {
    id,
    name,
    email: text(row.email) ?? '',
    phone: text(row.phone),
    role,
    // Absent reads as active: a row that lost the field in transit should
    // not look revoked.
    active: row.active !== false,
  };
}

export function readPeople(body: unknown): Person[] {
  const raw = (body ?? {}) as Record<string, unknown>;

  return Array.isArray(raw.users)
    ? raw.users.map(readPerson).filter((row): row is Person => row !== null)
    : [];
}

async function detailOf(response: Response, fallback: string): Promise<string> {
  try {
    const body = (await response.json()) as Record<string, unknown>;
    return text(body.detail) ?? fallback;
  } catch {
    return fallback;
  }
}

async function call(path: string, init: RequestInit = {}): Promise<Response> {
  assertApiConfiguration();

  try {
    return await fetch(new URL(`${apiBaseUrl}${path}`, window.location.origin), {
      ...init,
      headers: apiHeaders(init.body ? { 'Content-Type': 'application/json' } : {}),
    });
  } catch {
    throw new AccountError(0, UNREACHABLE);
  }
}

export async function signIn(email: string, password: string): Promise<Person> {
  const response = await call('/session', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    throw new AccountError(response.status, await detailOf(response, REFUSED));
  }

  const body = (await response.json()) as Record<string, unknown>;
  const person = readPerson(body.user);
  const token = text(body.token);

  if (!person || !token) {
    throw new AccountError(500, 'O servidor respondeu sem a sessão.');
  }

  rememberSession(token);
  return person;
}

export function signOut() {
  // Nothing to tell the server: the token is signed, not stored, so letting
  // go of it is the whole of signing out on this side.
  rememberSession(null);
}

/** Who the stored token belongs to, or null when there is no usable session. */
export async function currentPerson(
  options: { signal?: AbortSignal } = {},
): Promise<Person | null> {
  const response = await call('/session', { signal: options.signal });

  if (response.status === 401) {
    rememberSession(null);
    return null;
  }

  if (!response.ok) {
    throw new AccountError(response.status, await detailOf(response, UNREACHABLE));
  }

  return readPerson(await response.json());
}

export async function listTeam(options: { signal?: AbortSignal } = {}): Promise<Person[]> {
  const response = await call('/users', { signal: options.signal });

  if (!response.ok) {
    throw new AccountError(response.status, await detailOf(response, UNREACHABLE));
  }

  return readPeople(await response.json());
}

export type NewPerson = { name: string; email: string; phone?: string; password: string };

export async function addPerson(person: NewPerson): Promise<Person> {
  const response = await call('/users', { method: 'POST', body: JSON.stringify(person) });

  if (!response.ok) {
    throw new AccountError(
      response.status,
      await detailOf(response, 'Não foi possível cadastrar.'),
    );
  }

  const created = readPerson(await response.json());

  if (!created) {
    throw new AccountError(500, 'O servidor respondeu sem a conta criada.');
  }

  return created;
}

export async function revokeAccess(id: string): Promise<Person> {
  return changeAccess(id, 'DELETE', 'Não foi possível revogar o acesso.');
}

export async function restoreAccess(id: string): Promise<Person> {
  return changeAccess(id, 'POST', 'Não foi possível devolver o acesso.');
}

async function changeAccess(id: string, method: string, fallback: string): Promise<Person> {
  const response = await call(`/users/${encodeURIComponent(id)}/access`, { method });

  if (!response.ok) {
    throw new AccountError(response.status, await detailOf(response, fallback));
  }

  const person = readPerson(await response.json());

  if (!person) {
    throw new AccountError(500, fallback);
  }

  return person;
}
