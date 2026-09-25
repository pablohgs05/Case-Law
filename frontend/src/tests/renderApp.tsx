import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import App from '../App';
import AddressProbe from './AddressProbe';

// The screen with its real routes, at any address — as when a link is opened
// directly or the page is reloaded there.
export function renderApp(path = '/') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
      <AddressProbe />
    </MemoryRouter>,
  );
}

export const currentAddress = () => screen.getByTestId('address').textContent;
