# Running Scholr on the home machine

Decision D6 (docs/STUDENT-APP.md): Scholr runs on the home PC for the next two to three months, then moves to a
small VPS. Nothing below names a cloud, so the same three commands work in either place.

What runs: Postgres, the API and the web app, in three containers started together by
`infra/docker-compose.home.yml`. Her books and papers stay on the machine (mounted, never baked into an image).
Accounts are email and password, approved by an admin (D7).

## 1. One-time setup

```bash
cp infra/home.env.example infra/home.env
```

Fill in the four values. Generate each password with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

`infra/home.env` is gitignored and never leaves the machine. Keep a copy somewhere safe — losing
`SCHOLR_DB_PASSWORD` means losing access to the database.

## 2. Start it

```bash
docker compose -f infra/docker-compose.home.yml --env-file infra/home.env up -d --build
```

The first start builds both images, creates the database, runs the migrations and starts the app. It restarts
with the machine from then on. Check it is up:

```bash
curl http://127.0.0.1:8000/health
```

## 3. Load the curriculum and her material

Run the seed and ingest commands inside the API container, the same ones CLAUDE.md lists for development:

```bash
docker compose -f infra/docker-compose.home.yml --env-file infra/home.env exec api python -m app.seed.curriculum /content/curriculum/igcse-maths-0580.yaml
```

Moving the existing development database over instead (it already holds her record, lessons and corpus):

```bash
docker exec scholr-db pg_dump -U scholr -Fc scholr > scholr.dump
docker cp scholr.dump scholr-home-db:/tmp/scholr.dump
docker exec scholr-home-db pg_restore -U scholr -d scholr --clean --if-exists /tmp/scholr.dump
```

## 4. The first account

Registrations wait for an admin, so the admin account is made from the terminal. It asks for a password and
never prints it:

```bash
docker compose -f infra/docker-compose.home.yml --env-file infra/home.env exec api python -m app.jobs.accounts create-admin --email you@example.com --name "Your Name"
```

Then, signed in as that account, open `/admin/registrations` to approve her account and choose its streams.
The same decisions can be made from the terminal:

```bash
docker compose -f infra/docker-compose.home.yml --env-file infra/home.env exec api python -m app.jobs.accounts pending
docker compose -f infra/docker-compose.home.yml --env-file infra/home.env exec api python -m app.jobs.accounts approve her@example.com --role student --streams IGCSE,IIT --year-group "Year 10"
```

## 5. On her phone

Both devices must be on the home Wi-Fi. Find the machine's address (`ipconfig` on Windows, the IPv4 address of
the Wi-Fi adapter), then open `http://<that address>:3000` on her phone and choose **Add to Home Screen**. It
then opens like an app, full screen, with its own icon.

Two things to know:

- it works only at home, because nothing is published to the internet. That is deliberate: going public needs
  the safety notifications and helplines that are deferred (D8), and HTTPS;
- Windows may block the connection until port 3000 is allowed for private networks (Windows Defender Firewall →
  Inbound Rules).

## 6. Backups

The database holds everything she has done. Take a dump before any upgrade, and keep one off the machine:

```bash
docker exec scholr-home-db pg_dump -U scholr -Fc scholr > "scholr-$(date +%F).dump"
```

`infra/scripts/backup_restore_rehearsal.sh` restores a dump into a scratch database and checks it (AC-O2). A
backup nobody has restored is not a backup.

## 7. Upgrading

```bash
git pull
docker compose -f infra/docker-compose.home.yml --env-file infra/home.env up -d --build
```

Migrations run automatically before the API starts.

## Moving to a VPS later

The same compose file runs there. What changes: a TLS proxy (Caddy or nginx) in front of the web container so
the address is `https://…`, the firewall opened for 80 and 443 only, and — because it is then reachable from
outside — the deferred safety work (D8: an urgent-alert channel and verified helplines) must be answered first.
