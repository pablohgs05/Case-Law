import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowCounterClockwise, ArrowLeft, Prohibit, UserPlus } from '@phosphor-icons/react';

import {
  AccountError,
  addPerson,
  listTeam,
  restoreAccess,
  revokeAccess,
  type Person,
} from '../api/accounts';
import { useCurrentPerson } from '../session/sessionContext';
import {
  asPhone,
  PASSWORD_HINT,
  PASSWORD_MIN,
  passwordIsStrong,
  PHONE_HINT,
  phoneIsComplete,
} from '../components/accountFormat';

/**
 * A manager running the firm's access.
 *
 * One firm uses this system, with few people in it, so this list is everyone:
 * a manager sees and administers all of them, including accounts another
 * manager created.
 *
 * Revoked people stay on the list, marked. They ran searches, and hiding them
 * would hide that — and it would also hide the mistake when the wrong person
 * was revoked, which is what the "devolver acesso" button is there for.
 */

export const TEAM_PATH = '/equipe';

type Feedback = { kind: 'done' | 'failed'; message: string } | null;

const EMPTY = { name: '', email: '', phone: '', password: '' };

export default function TeamPage() {
  const navigate = useNavigate();
  const person = useCurrentPerson();
  const [team, setTeam] = useState<Person[] | null>(null);
  const [loadFailure, setLoadFailure] = useState<string | null>(null);
  const [form, setForm] = useState(EMPTY);
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [working, setWorking] = useState(false);

  const load = useCallback((signal?: AbortSignal) => {
    listTeam({ signal }).then(
      (people) => setTeam(people),
      (error: unknown) => {
        if (!signal?.aborted) {
          setLoadFailure(
            error instanceof AccountError ? error.message : 'Não foi possível carregar a equipe.',
          );
        }
      },
    );
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setFeedback(null);

    // Caught here so the person is not made to wait for a round trip to be
    // told something this screen already knew.
    if (!passwordIsStrong(form.password)) {
      setFeedback({ kind: 'failed', message: PASSWORD_HINT });
      return;
    }

    if (!phoneIsComplete(form.phone)) {
      setFeedback({ kind: 'failed', message: PHONE_HINT });
      return;
    }

    setWorking(true);

    try {
      const created = await addPerson({
        name: form.name.trim(),
        email: form.email.trim(),
        phone: form.phone.trim() || undefined,
        password: form.password,
      });
      setTeam((current) => [...(current ?? []), created]);
      setForm(EMPTY);
      setFeedback({ kind: 'done', message: `${created.name} já pode entrar.` });
    } catch (error) {
      setFeedback({
        kind: 'failed',
        message:
          error instanceof AccountError ? error.message : 'Não foi possível cadastrar agora.',
      });
    } finally {
      setWorking(false);
    }
  }

  async function change(target: Person) {
    setFeedback(null);

    try {
      const changed = target.active
        ? await revokeAccess(target.id)
        : await restoreAccess(target.id);
      setTeam((current) => (current ?? []).map((row) => (row.id === changed.id ? changed : row)));
      setFeedback({
        kind: 'done',
        message: changed.active
          ? `${changed.name} voltou a ter acesso.`
          : `${changed.name} não acessa mais a ferramenta.`,
      });
    } catch (error) {
      setFeedback({
        kind: 'failed',
        message: error instanceof AccountError ? error.message : 'Não foi possível concluir.',
      });
    }
  }

  return (
    <main className="team">
      <header className="team__header">
        {/* Forward to the search, never Back: this screen is reached from the
            bar, and Back would land wherever the reader happened to be. */}
        <button type="button" className="coverage-back" onClick={() => navigate('/')}>
          <ArrowLeft size={13} aria-hidden="true" />
          Voltar à pesquisa
        </button>

        <h1 className="team__title">Usuários do sistema</h1>
        <p className="team__lead">
          Todo mundo que tem acesso está nesta lista. Você cadastra quem entra e tira o acesso de
          quem sai. Quem for cadastrado aqui pesquisa decisões; administrar os usuários é dos
          gerentes.
        </p>
      </header>

      <section className="team__add" aria-labelledby="cadastrar">
        <h2 id="cadastrar" className="team__section-title">
          Cadastrar uma pessoa
        </h2>

        <form className="team__form" onSubmit={submit}>
          <label className="team__field">
            <span>Nome</span>
            <input
              required
              minLength={2}
              value={form.name}
              onChange={(event) => setForm({ ...form, name: event.target.value })}
            />
          </label>

          <label className="team__field">
            <span>E-mail</span>
            <input
              required
              type="email"
              value={form.email}
              onChange={(event) => setForm({ ...form, email: event.target.value })}
            />
          </label>

          <label className="team__field">
            <span>
              Telefone <em>opcional</em>
            </span>
            <input
              // `inputMode` raises the number pad on a phone; the value is
              // reformatted on every keystroke, so a letter never lands.
              inputMode="numeric"
              autoComplete="tel"
              placeholder="(12) 99999-0000"
              value={form.phone}
              onChange={(event) => setForm({ ...form, phone: asPhone(event.target.value) })}
            />
            <small>{PHONE_HINT}</small>
          </label>

          <label className="team__field">
            <span>Senha inicial</span>
            <input
              required
              type="password"
              minLength={PASSWORD_MIN}
              autoComplete="new-password"
              value={form.password}
              onChange={(event) => setForm({ ...form, password: event.target.value })}
            />
            {/* Said before the refusal, not after: a rule the person only
                discovers by breaking it is a rule that wastes their time. */}
            <small>{PASSWORD_HINT}</small>
          </label>

          <button type="submit" className="team__submit" disabled={working}>
            <UserPlus size={16} weight="bold" aria-hidden="true" />
            {working ? 'Cadastrando…' : 'Cadastrar'}
          </button>
        </form>

        {feedback && (
          <p
            className={`team__feedback team__feedback--${feedback.kind === 'done' ? 'done' : 'failed'}`}
            role="status"
          >
            {feedback.message}
          </p>
        )}
      </section>

      <section className="team__list-area" aria-labelledby="quem-tem-acesso">
        <h2 id="quem-tem-acesso" className="team__section-title">
          Quem tem acesso
        </h2>

        {loadFailure && (
          <p className="team__feedback team__feedback--failed" role="alert">
            {loadFailure}
          </p>
        )}

        {team === null && !loadFailure && (
          <p className="team__state" role="status">
            Carregando a equipe…
          </p>
        )}

        {team !== null && (
          <ul className="team__list">
            {team.map((row) => (
              <li key={row.id} className={`team__person${row.active ? '' : ' team__person--off'}`}>
                <div className="team__who">
                  <p className="team__name">
                    {row.name}
                    {row.role === 'gerente' && <span className="team__badge">gerente</span>}
                    {!row.active && (
                      <span className="team__badge team__badge--off">sem acesso</span>
                    )}
                  </p>
                  <p className="team__contact">
                    {row.email}
                    {row.phone ? ` · ${row.phone}` : ''}
                  </p>
                </div>

                {/* The one account a manager cannot touch is their own: revoking
                    yourself leaves the firm with nobody able to administer. */}
                {row.id !== person?.id && (
                  <button type="button" className="team__change" onClick={() => void change(row)}>
                    {row.active ? (
                      <>
                        <Prohibit size={15} aria-hidden="true" /> Revogar acesso
                      </>
                    ) : (
                      <>
                        <ArrowCounterClockwise size={15} aria-hidden="true" /> Devolver acesso
                      </>
                    )}
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
