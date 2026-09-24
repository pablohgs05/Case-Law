# Public access

Both environments run behind the private network: the container publishes its port
on the Tailscale interface only, so nothing on the servers is reachable from the
internet. These files put nginx in front, on the machine that already has a public
address.

```
internet ──► VPS (nginx) ──► production, on the same machine
                         └─► development, on the Raspberry over Tailscale
```

The Raspberry keeps no port open to the internet. Only nginx faces the world.

| Address | Serves |
|---|---|
| `jurisfonte.pedrohenribeiro.com/api` | production |
| `dev.jurisfonte.pedrohenribeiro.com/api` | development, behind a password |

The API lives under `/api` on the same host as the interface, so the browser sees
one origin and CORS never comes up. The application is told about the prefix
through `ROOT_PATH`, which is what makes Swagger generate the right URLs.

## Installing

Run on the VPS, once per environment.

**1. The shared rate limit.** Inside the `http` block of `/etc/nginx/nginx.conf`:

```nginx
limit_req_zone $binary_remote_addr zone=jurisfonte_api:10m rate=10r/s;
```

**2. The password for development:**

```bash
sudo apt-get install -y apache2-utils
sudo htpasswd -c /etc/nginx/jurisfonte-dev.htpasswd <user>
sudo chmod 640 /etc/nginx/jurisfonte-dev.htpasswd
sudo chown root:www-data /etc/nginx/jurisfonte-dev.htpasswd
```

**3. The certificates.** Certbot needs the name to resolve first:

```bash
sudo certbot certonly --nginx \
  -d jurisfonte.pedrohenribeiro.com \
  -d dev.jurisfonte.pedrohenribeiro.com
```

One certificate covering both names, so both files point at the same path. Two
separate certificates would mean two renewals to watch instead of one.

**4. The sites.** Both files carry a placeholder where the backend address goes.
The addresses live on the private network and are deliberately not in this
repository, which is public — take them from the team's internal notes:

```bash
sed -e "s|__PRODUCTION_BACKEND__|<address:8000>|" \
    -e "s|__PRODUCTION_FRONTEND__|<address:8001>|" jurisfonte.conf \
  | sudo tee /etc/nginx/sites-available/jurisfonte > /dev/null
sed -e "s|__DEVELOPMENT_BACKEND__|<address:8000>|" \
    -e "s|__DEVELOPMENT_FRONTEND__|<address:8001>|" dev.jurisfonte.conf \
  | sudo tee /etc/nginx/sites-available/dev.jurisfonte > /dev/null
sudo ln -s /etc/nginx/sites-available/jurisfonte     /etc/nginx/sites-enabled/
sudo ln -s /etc/nginx/sites-available/dev.jurisfonte /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

`nginx -t` before reloading is not optional: this machine serves other projects,
and a broken file would take them down with it.

## Turning it off

```bash
sudo rm /etc/nginx/sites-enabled/dev.jurisfonte
sudo nginx -t && sudo systemctl reload nginx
```

The environment goes back to being reachable only over the private network. The
same works for production.

## How the two halves fit

`/` reaches the interface container and `/api` reaches the API, both on the same
host. The browser therefore sees a single origin: CORS never applies, and the
interface is built with a relative `/api`, so the same image serves whichever
environment it lands in.
