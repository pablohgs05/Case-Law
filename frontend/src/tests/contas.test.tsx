import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { readPeople, signIn, signOut } from '../api/accounts';
import { apiHeaders, sessionToken } from '../api/token';
import SignInPage from '../pages/SignInPage';
import { SessionProvider } from '../session/SessionProvider';
import { useSession } from '../session/sessionContext';

/**
 * The door, and what it carries afterwards.
 *
 * Two promises here. The screen says one thing to every refusal, because
 * saying more would turn it into a way of asking which addresses have an
 * account. And once someone is in, the token rides on every call to the API —
 * a request that forgets it comes back 401 and looks like a dead screen.
 */

vi.mock('../api/client', async () => {
  const real = await vi.importActual<typeof import('../api/client')>('../api/client');
  return { ...real, apiBaseUrl: 'http://localhost:8000', assertApiConfiguration: () => undefined };
});

const MANAGER = {
  id: '7c3f1f0e-2a5b-4c9d-8e1f-6b2d9a4c7e35',
  name: 'Ana Almeida Costa',
  email: 'ana@almeidacosta.com.br',
  phone: null,
  role: 'gerente',
  active: true,
};

function answering(body: unknown, status = 200) {
  return vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  });
}

beforeEach(() => {
  signOut();
  vi.stubGlobal('fetch', answering({ token: 'um-token', user: MANAGER }));
});

afterEach(() => {
  signOut();
  vi.unstubAllGlobals();
});

describe('a tela de entrar', () => {
  it('não oferece criar conta: o acesso é dado, nunca tomado', () => {
    render(<SignInPage />, { wrapper: SessionProvider });

    expect(screen.queryByText(/criar conta|cadastre-se|registrar/i)).not.toBeInTheDocument();
    expect(screen.getByText(/criada pelo gerente do seu escritório/)).toBeInTheDocument();
  });

  it('entra e guarda a sessão', async () => {
    const user = userEvent.setup();
    render(<SignInPage />, { wrapper: SessionProvider });

    await user.type(screen.getByLabelText(/E-mail profissional/), MANAGER.email);
    await user.type(screen.getByLabelText(/^Senha$/), 'uma senha bem longa');
    await user.click(screen.getByRole('button', { name: /Entrar na plataforma/ }));

    await waitFor(() => expect(sessionToken()).toBe('um-token'));
  });

  it('mostra a recusa sem dizer qual das duas falhou', async () => {
    vi.stubGlobal(
      'fetch',
      answering(
        { detail: 'E-mail ou senha incorretos, ou o acesso desta conta foi revogado.' },
        401,
      ),
    );
    const user = userEvent.setup();
    render(<SignInPage />, { wrapper: SessionProvider });

    await user.type(screen.getByLabelText(/E-mail profissional/), 'quem@exemplo.com');
    await user.type(screen.getByLabelText(/^Senha$/), 'errada');
    await user.click(screen.getByRole('button', { name: /Entrar na plataforma/ }));

    const recusa = await screen.findByRole('alert');
    expect(recusa).toHaveTextContent(/E-mail ou senha incorretos/);
    // Nem "não existe", nem "senha errada": as duas levariam à mesma pergunta.
    expect(recusa).not.toHaveTextContent(/não existe|senha errada|conta inexistente/i);
    expect(sessionToken()).toBeNull();
  });

  it('a senha nunca viaja num endereço', async () => {
    const chamada = answering({ token: 't', user: MANAGER });
    vi.stubGlobal('fetch', chamada);
    const user = userEvent.setup();
    render(<SignInPage />, { wrapper: SessionProvider });

    await user.type(screen.getByLabelText(/E-mail profissional/), MANAGER.email);
    await user.type(screen.getByLabelText(/^Senha$/), 'uma senha bem longa');
    await user.click(screen.getByRole('button', { name: /Entrar na plataforma/ }));

    // A primeira chamada é a do provedor conferindo a sessão guardada; a que
    // interessa é o POST do formulário.
    await waitFor(() =>
      expect(chamada.mock.calls.some((call) => (call[1] as RequestInit)?.method === 'POST')).toBe(
        true,
      ),
    );
    const [endereco, opcoes] = chamada.mock.calls.find(
      (call) => (call[1] as RequestInit)?.method === 'POST',
    ) as [URL, RequestInit];

    expect(String(endereco)).not.toContain('senha');
    expect(String(endereco)).not.toContain('bem longa');
    expect(String(opcoes.body)).toContain('bem longa');
  });
});

describe('o token em toda chamada', () => {
  it('não vai antes de entrar', () => {
    expect(apiHeaders().Authorization).toBeUndefined();
  });

  it('vai depois de entrar, e some ao sair', async () => {
    await signIn(MANAGER.email, 'uma senha bem longa');
    expect(apiHeaders().Authorization).toBe('Bearer um-token');

    signOut();
    expect(apiHeaders().Authorization).toBeUndefined();
  });

  it('o cabeçalho de quem chama pode acrescentar, nunca perder o token', async () => {
    await signIn(MANAGER.email, 'uma senha bem longa');

    const headers = apiHeaders({ 'Content-Type': 'application/json' });

    expect(headers.Authorization).toBe('Bearer um-token');
    expect(headers.Accept).toBe('application/json');
  });
});

describe('a leitura da equipe', () => {
  it('descarta a linha que não dá para apresentar', () => {
    const lidas = readPeople({
      users: [MANAGER, { id: 'x' }, { ...MANAGER, role: 'dono' }, null],
    });

    expect(lidas).toHaveLength(1);
  });

  it('sem o campo ativo, a conta não parece revogada', () => {
    const [pessoa] = readPeople({ users: [{ ...MANAGER, active: undefined }] });

    expect(pessoa.active).toBe(true);
  });
});

function Quem() {
  const session = useSession();
  return <p>{session.status === 'signed in' ? session.person.name : session.status}</p>;
}

describe('a sessão da interface', () => {
  it('confere a sessão guardada antes de decidir qualquer coisa', async () => {
    // Sem este estado, recarregar a página jogaria a pessoa para fora.
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})));
    render(<Quem />, { wrapper: SessionProvider });

    expect(await screen.findByText('checking')).toBeInTheDocument();
  });

  it('um token que o servidor recusa vira sessão encerrada, não erro', async () => {
    vi.stubGlobal('fetch', answering({ detail: 'expirou' }, 401));
    render(<Quem />, { wrapper: SessionProvider });

    expect(await screen.findByText('signed out')).toBeInTheDocument();
  });

  it('um token aceito traz a pessoa', async () => {
    vi.stubGlobal('fetch', answering(MANAGER));
    render(<Quem />, { wrapper: SessionProvider });

    expect(await screen.findByText(MANAGER.name)).toBeInTheDocument();
  });
});
