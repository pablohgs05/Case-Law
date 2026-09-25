import { Routes, Route } from 'react-router-dom';
import HomePage from './pages/HomePage';
import SearchSessionProvider from './search/SearchSessionProvider';

function App() {
  return (
    <div>
      {/* Above the routes, so the search outlives whichever screen shows it. */}
      <SearchSessionProvider>
        <Routes>
          {/* A decision's address is a child of the search, not a page of its
              own: the search stays mounted while the address changes, so its
              results, filters and order are still there when it changes back. */}
          <Route path="/" element={<HomePage />}>
            <Route path="decisoes/:source/:identifier" element={null} />
          </Route>
        </Routes>
      </SearchSessionProvider>
    </div>
  );
}

export default App;
