import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

// Each test mounts its own tree. Without this, a query in one test can find a
// node another test left behind, and the failure points at the wrong place.
afterEach(cleanup);
