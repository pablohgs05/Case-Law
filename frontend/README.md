# Case Law — Frontend

React application that consumes the Case Law API: search, decision detail and
the indicator screens.

## Requirements

- [Node.js](https://nodejs.org/) 24 — the version the CI runs
- npm — ships with Node, no separate install

The stack is React 18, Vite 5 and TypeScript 5.6.

## Setup

```bash
cd frontend
npm install
cp .env.example .env
```

## Running

```bash
npm run dev
```

| Address               | What it is                                                     |
| --------------------- | -------------------------------------------------------------- |
| http://localhost:5173 | the app in development, with hot reload                        |
| http://localhost:4173 | the production build, after `npm run build && npm run preview` |

Both ports are set in `vite.config.ts` and repeated in the npm scripts, so the
dev server answers on the network and not only on `localhost`.

## Quality checks

The same three commands the CI runs. Run them before opening a pull request:

```bash
npm run lint          # ESLint
npm run format:check  # formatting
npm run typecheck     # type checking
```

To fix instead of only reporting:

```bash
npm run lint:fix      # applies every auto-fixable ESLint rule
npm run format        # rewrites the files with Prettier
```

`npm run lint` fails on warnings too, so a warning cannot pile up unnoticed.

### What each tool covers

**ESLint** (`eslint.config.js`) uses the flat config format and layers four sets
of rules:

| Set                             | What it catches                                                                   |
| ------------------------------- | --------------------------------------------------------------------------------- |
| `@eslint/js` recommended        | plain JavaScript mistakes                                                         |
| `typescript-eslint` recommended | unused variables, `any`, unsafe TypeScript                                        |
| `eslint-plugin-react-hooks`     | the rules of hooks, stale dependency lists, state written straight from an effect |
| `eslint-plugin-react-refresh`   | exports that silently break Vite hot reload                                       |

The React Hooks rules are the ones worth reading the message for — they catch
bugs that only show up as a component rendering the wrong thing, not style.

**Prettier** (`.prettierrc.json`) owns formatting, and only formatting. It runs
with a 100 column width, single quotes and trailing commas.
`eslint-config-prettier` is applied last in the ESLint config, which switches off
every ESLint rule that would have an opinion about layout — the two tools never
disagree, because only one of them is looking.

**TypeScript** runs as `tsc -b`, the same command `npm run build` starts with, so
a type error fails the build and the `typecheck` script identically.

## Adding a dependency

```bash
npm install <package>              # runtime
npm install --save-dev <package>   # development only
```

Both update `package.json` and `package-lock.json`. **Commit the lock file** —
it is what keeps every machine and the CI on the same versions, and `npm ci`
refuses to run without it.

## Structure

```
frontend/
├── src/
│   ├── api/             one module per group of API calls
│   ├── pages/           one component per route
│   ├── App.tsx          declares the routes
│   ├── main.tsx         mounts React into index.html
│   └── styles.css
├── index.html           the page Vite serves
├── eslint.config.js     lint rules
├── .prettierrc.json     formatting rules
└── vite.config.ts       dev server and build
```

## Configuration

Every value that differs between a laptop and a server is read from the
environment. Vite only exposes variables prefixed with `VITE_` to the browser.

| Variable       | Default                 | What it does              |
| -------------- | ----------------------- | ------------------------- |
| `VITE_API_URL` | `http://localhost:8000` | where the backend answers |

`.env.example` is versioned as a template. The real `.env` is ignored by git.

Anything in a `VITE_` variable is compiled into the bundle and readable by anyone
who opens the site. Never put a secret there — the frontend has no private
configuration.
