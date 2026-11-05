import { useState } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import AppHeader from './components/AppHeader';
import CoveragePage, { COVERAGE_PATH } from './pages/CoveragePage';
import HomePage from './pages/HomePage';
import SignInPage from './pages/SignInPage';
import TeamPage, { TEAM_PATH } from './pages/TeamPage';
import { HeaderSearchSlot } from './search/headerSearchSlot';
import SearchSessionProvider from './search/SearchSessionProvider';
import { SessionProvider } from './session/SessionProvider';
import { useSession } from './session/sessionContext';

/**
 * Nothing of the tool renders without an account.
 *
 * The decision is made once, here, around the whole set of routes rather than
 * inside each screen: a screen added later is behind the door without anyone
 * remembering to put it there — the same posture the API takes.
 */
export function Tool() {
  // The place in the bar where the search screen puts its search.
  const [searchSlot, setSearchSlot] = useState<HTMLElement | null>(null);

  return (
    <>
      <AppHeader searchSlotRef={setSearchSlot} />
      {/* Above the routes, so the search outlives whichever screen shows it. */}
      <HeaderSearchSlot.Provider value={searchSlot}>
        <SearchSessionProvider>
          <Routes>
            {/* A decision's address is a child of the search, not a page of its
                own: the search stays mounted while the address changes, so its
                results, filters and order are still there when it changes back. */}
            <Route path="/" element={<HomePage />}>
              <Route path="decisoes/:source/:identifier" element={null} />
            </Route>
            {/* Its own page: the coverage describes the whole base, so nothing of
                the search is passed to it. */}
            <Route path={COVERAGE_PATH} element={<CoveragePage />} />
            <Route path={TEAM_PATH} element={<TeamPage />} />
            {/* Signed in, there is nothing to sign in to. */}
            <Route path="/entrar" element={<Navigate to="/" replace />} />
          </Routes>
        </SearchSessionProvider>
      </HeaderSearchSlot.Provider>
    </>
  );
}

function Shell() {
  const session = useSession();

  // The three states are three: checking is the moment after a reload, before
  // the stored token has been confirmed. Showing the login screen here would
  // bounce people out on every refresh; showing the tool would flash it at
  // someone who turns out not to be signed in.
  if (session.status === 'checking') {
    return (
      <p className="app-shell__checking" role="status">
        Verificando a sua sessão…
      </p>
    );
  }

  return session.status === 'signed in' ? <Tool /> : <SignInPage />;
}

function App() {
  return (
    // The window's height and no more: each screen scrolls inside itself.
    <div className="app-shell">
      <SessionProvider>
        <Shell />
      </SessionProvider>
    </div>
  );
}

export default App;
