# matrixtools

`matrixtools` provides helpers for a Synapse homeserver: creating users via
the admin API and logging in to obtain access tokens.

## Functions

```python
from wit_pytools.matrixtools import create_user, login, login_as_user
```

- `create_user(user_id, password, displayname=None, *, server=None, admin_token=None)`
  calls `PUT /_synapse/admin/v2/users/{user_id}`. `user_id` is the full MXID
  (`@pirx:matrix.witconsult.de`). `admin_token` falls back to env
  `MATRIX_ADMIN_TOKEN`, `server` to `MATRIX_SERVER`.
- `login(user, password, *, server=None)` calls
  `POST /_matrix/client/v3/login` and returns the `access_token`.
- `login_as_user(user_id, *, server=None, admin_token=None)` calls
  `POST /_synapse/admin/v1/users/{user_id}/login` with the admin token and
  returns an `access_token` for that user — no password needed, so it also
  works when password login is disabled.

Typical bot provisioning (admin token only, no passwords in scripts):

```python
create_user("@pirx:matrix.witconsult.de", "<password>", displayname="Pirx (KI-Bot)")
bot_token = login_as_user("@pirx:matrix.witconsult.de")
```

## Configuration

`.env` (never commit real values):

```text
MATRIX_SERVER=https://matrix.witconsult.de
MATRIX_ADMIN_TOKEN=syt_...
```

## Bootstrapping an admin token

There is no separate API key — the admin token is the access token of a
server-admin account.

1. Create an admin user inside the container (`matrix`):

   ```bash
   docker exec -it matrix register_new_matrix_user \
       -c /data/homeserver.yaml http://localhost:8008
   ```

   Answer "Make admin? yes". To promote an existing user instead (sqlite
   default):

   ```bash
   docker exec -it matrix sqlite3 /data/homeserver.db \
       "UPDATE users SET admin = 1 WHERE name = '@pirx:matrix.witconsult.de';"
   ```

2. Password login must be enabled **once** to obtain the admin token in
   step 3. Afterwards it can be disabled again — `create_user` and
   `login_as_user` only need `MATRIX_ADMIN_TOKEN`. In this deployment
   `matrix-extra.yaml`
   is loaded after `homeserver.yaml` and overrides it, so set
   `password_config.enabled: true` in
   `/opt/containers/matrix/synapse/matrix-extra.yaml` (host path for the
   `/data` volume), then restart:

   ```bash
   docker restart matrix
   ```

   Find the `/data` volume's host path with:

   ```bash
   docker inspect matrix --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{"\n"}}{{end}}'
   ```

3. Log in and store the token:

   ```python
   from wit_pytools.matrixtools import login
   token = login("matrixadmin", "<password>")  # MATRIX_SERVER from .env
   ```

   Or via Element: Settings → Help & About → Access Token.

## Notes

- Use `https://` for `MATRIX_SERVER`: the `http://` URL 301-redirects and
  the POST body is dropped on redirect, surfacing as a confusing
  `404 page not found` (which is the proxy's message, not a Synapse error).
- Proxy responses like `404 page not found` mean the request never reached
  Synapse. Check reachability with
  `curl -i https://matrix.witconsult.de/_matrix/client/versions` — a JSON
  `{"versions": [...]}` reply means the client API is up.
- If `/_synapse/admin/*` is not forwarded by the reverse proxy, call the
  container directly on port `8008`.
- Access tokens stay valid until the session is logged out; rotate by
  logging in again. Rotate the user password via `create_user` if it was
  exposed (e.g. in shell history).
