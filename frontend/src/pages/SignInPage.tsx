import { useState, type FormEvent } from 'react';
import { Envelope, Lock, ShieldCheck, WarningCircle } from '@phosphor-icons/react';

import { AccountError } from '../api/accounts';
import { useSession } from '../session/sessionContext';

/**
 * The door.
 *
 * It is the one screen an outsider can reach, so it says as little as
 * possible: one refusal for a wrong password, an unknown address and a revoked
 * account alike. Telling them apart would turn this form into a way of asking
 * which firms have a licence.
 *
 * There is no "create an account" link, and that is the product: access is
 * given by a manager, never taken.
 */

export default function SignInPage() {
  const { signIn } = useSession();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [failure, setFailure] = useState<string | null>(null);
  const [sending, setSending] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setFailure(null);
    setSending(true);

    try {
      await signIn(email.trim(), password);
    } catch (error) {
      setFailure(error instanceof AccountError ? error.message : 'Não foi possível entrar agora.');
      setSending(false);
    }
  }

  return (
    <main className="sign-in">
      <section className="sign-in__pitch">
        <p className="sign-in__eyebrow">Inteligência em dados judiciais</p>
        <h1 className="sign-in__headline">
          Investigue entendimentos.
          <br />
          Sustente cada conclusão.
        </h1>
        <p className="sign-in__lead">
          Pesquise decisões, confronte linhas favoráveis e contrárias e chegue aos documentos
          oficiais que comprovam a análise.
        </p>

        <p className="sign-in__notice">
          <ShieldCheck size={16} weight="fill" aria-hidden="true" />
          <span>
            <strong>Ambiente de pesquisa protegido.</strong> O acesso às decisões exige uma conta
            autorizada, criada pelo gerente do seu escritório.
          </span>
        </p>
      </section>

      <section className="sign-in__panel" aria-labelledby="entrar">
        <p className="sign-in__kicker">Acesso profissional</p>
        <h2 id="entrar" className="sign-in__title">
          Entre na sua conta
        </h2>
        <p className="sign-in__subtitle">
          Use as credenciais que o gerente do seu escritório cadastrou.
        </p>

        <form className="sign-in__form" onSubmit={submit} noValidate>
          <label className="sign-in__field">
            <span className="sign-in__label">E-mail profissional</span>
            <span className="sign-in__input">
              <Envelope size={16} aria-hidden="true" />
              <input
                type="email"
                name="email"
                autoComplete="username"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="voce@seuescritorio.com.br"
              />
            </span>
          </label>

          <label className="sign-in__field">
            <span className="sign-in__label">Senha</span>
            <span className="sign-in__input">
              <Lock size={16} aria-hidden="true" />
              <input
                type="password"
                name="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </span>
          </label>

          {/* Announced, not just coloured: whoever is listening to the page
              hears the refusal at the moment it happens. */}
          {failure && (
            <p className="sign-in__failure" role="alert">
              <WarningCircle size={16} weight="fill" aria-hidden="true" />
              <span>{failure}</span>
            </p>
          )}

          <button type="submit" className="sign-in__submit" disabled={sending}>
            {sending ? 'Entrando…' : 'Entrar na plataforma'}
          </button>
        </form>

        <p className="sign-in__help">
          Esqueceu a senha? Fale com o gerente do seu escritório — ele cadastra e repõe os acessos
          da equipe.
        </p>
      </section>
    </main>
  );
}
