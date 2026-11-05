"""
The thesis reader, as the ADK Dev UI serves it.

The same agent the API uses, not a copy of it: `montar` is the function
`app.agente.ler` calls on every request, so what the panel traces is what
production does. A demonstration built from a second definition would show a
reading nobody is served.

Run it on the tailnet and nowhere else. The Dev UI is unauthenticated by
design — the ADK's own help says so — and it spends the project's Gemini quota
for whoever opens it.

    cd backend
    uv run adk web --host "$(tailscale ip -4)" --port 8080 adk
"""

from app.agente import montar

root_agent = montar()
