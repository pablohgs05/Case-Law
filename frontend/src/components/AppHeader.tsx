import { Link, NavLink, useLocation, useMatch } from 'react-router-dom';
import { Database, SignOut, UsersThree } from '@phosphor-icons/react';

import { COVERAGE_PATH, type CoverageEntry } from '../pages/CoveragePage';
import { TEAM_PATH } from '../pages/TeamPage';
import { useSession } from '../session/sessionContext';

type AppHeaderProps = {
  // Given the place where a screen may put its search, empty on the others.
  searchSlotRef?: (element: HTMLElement | null) => void;
};

function AppHeader({ searchSlotRef }: AppHeaderProps) {
  const location = useLocation();
  const onCoverage = useMatch(COVERAGE_PATH) !== null;
  const onTeam = useMatch(TEAM_PATH) !== null;
  // The search and a decision read inside it are the same screen: the list
  // stays mounted while the address changes.
  const onSearch = !onCoverage && !onTeam;
  const session = useSession();
  const person = session.status === 'signed in' ? session.person : null;

  // Opened from the search, the entry behind the page is where the reader was
  // — the list, or a decision in it — so the way back is Back. Clicked again
  // on the page itself, it replaces the entry and keeps that knowledge, so
  // Back never lands on a second copy of the same page.
  //
  // From any other screen it is not: going back from the coverage landed on
  // the users list while the button said "voltar à pesquisa". What matters is
  // whether the search is the entry behind, not whether the app opened it.
  const state: CoverageEntry = onCoverage
    ? (location.state as CoverageEntry | null)
    : { fromApp: onSearch };

  return (
    <header className="app-header">
      <div className="app-header__brand-row">
        {/* The brand is the way home. It already points at the search, so a
            second link saying "Pesquisa" beside it would be two doors to the
            same room. */}
        <Link to="/" className="app-header__brand" aria-label="Jusmap — início">
          <img src="/jusmap-logo.png" alt="Jusmap" width="113" height="30" />
        </Link>
        <span className="app-header__section">Pesquisa jurisprudencial</span>
        <nav className="app-header__nav" aria-label="Informações do sistema">
          <NavLink
            to={COVERAGE_PATH}
            state={state}
            replace={onCoverage}
            className="app-header__link"
          >
            <Database size={14} aria-hidden="true" className="app-header__icon" />
            <span className="app-header__text">
              <span className="app-header__title">Cobertura da base</span>
              <span className="app-header__subtitle">Informações do sistema</span>
            </span>
          </NavLink>

          {/* Only a manager administers, so only a manager is offered the way
              there. The API refuses the rest regardless; this keeps the bar
              from showing a door that would close in their face. */}
          {person?.role === 'gerente' && (
            <NavLink to={TEAM_PATH} replace={onTeam} className="app-header__link">
              <UsersThree size={14} aria-hidden="true" className="app-header__icon" />
              <span className="app-header__text">
                <span className="app-header__title">Usuários</span>
                <span className="app-header__subtitle">Quem tem acesso</span>
              </span>
            </NavLink>
          )}

          {person && (
            <div className="app-header__account">
              <span className="app-header__who" title={person.email}>
                {person.name}
              </span>
              <button type="button" className="app-header__leave" onClick={session.signOut}>
                <SignOut size={14} aria-hidden="true" />
                Sair
              </button>
            </div>
          )}
        </nav>
      </div>
      {/* Only where there is a search to put in it. `!onCoverage` was enough
          until the users screen existed; now it would print the prompt over a
          slot nothing fills. */}
      {onSearch && (
        <div className="app-header__search-row">
          <div className="app-header__prompt">
            <span>Pesquisa jurisprudencial</span>
            <strong>O que você precisa entender?</strong>
          </div>
          <div ref={searchSlotRef} className="app-header__search" />
        </div>
      )}
    </header>
  );
}

export default AppHeader;
