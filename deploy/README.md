# Deploying Vouch

| Part | Where | URL |
|---|---|---|
| Website (Next.js) | Vercel, project `vouch` (account priyanshu-byte-coder) | https://vouch-theta-one.vercel.app |
| API + GROBID + HTTPS | Vultr `vc2-2c-4gb`, Bangalore, Ubuntu 24.04 (label `vouch`) | https://139-84-216-217.sslip.io/api/health |

The API host name is the server IP on [sslip.io](https://sslip.io); Caddy gets the HTTPS certificate automatically.

## Server
SSH key: `~/.ssh/vouch_vultr` (created by `create_vm.sh`). Code lives in `/srv/vouch` (from `git archive`), secrets in `/srv/vouch/.env`
(copied over SSH), compose settings in `/srv/vouch/deploy/.env`:

```
API_DOMAIN=139-84-216-217.sslip.io
VOUCH_CORS_ORIGINS=https://vouch-theta-one.vercel.app,https://vouch-priyanshu-doshis-projects.vercel.app,http://localhost:3000,http://127.0.0.1:3000
VOUCH_RATE_LIMIT=60
```

Volumes: `deploy_vouch-cache` (SQLite lookup + report cache, Retraction Watch CSV), `deploy_caddy-data` (certificates).

### Update the API after a code change (from the repo root, Git Bash)
```sh
IP=139.84.216.217
git archive --format=tar.gz -o /tmp/vouch.tgz HEAD backend deploy
scp -i ~/.ssh/vouch_vultr /tmp/vouch.tgz root@$IP:/root/
ssh -i ~/.ssh/vouch_vultr root@$IP 'cd /srv/vouch && tar xzf /root/vouch.tgz && cd deploy && docker compose up -d --build'
cd backend && .venv/Scripts/python scripts/warm_examples.py --api https://139-84-216-217.sslip.io   # example buttons instant again
```
If `REPORT_VERSION` in `backend/app/main.py` changed, the old cached reports are ignored and the warm-up recomputes them (~2 min).

### Look at it
```sh
ssh -i ~/.ssh/vouch_vultr root@139.84.216.217
cd /srv/vouch/deploy && docker compose ps && docker compose logs --tail 50 api
```

## Website
```sh
cd frontend
npx vercel deploy --prod --yes --scope priyanshu-doshis-projects --token <token>
```
`NEXT_PUBLIC_API_URL` is set in the Vercel project (Production). Use the priyanshu-byte-coder token, **not** the default CLI login.

## Demo safety (step 5.3)
- Example buttons are pre-run (`warm_examples.py`); a replay takes < 1 s.
- `/report/demo` is static and works even if the API is down.
- Containers restart automatically (`restart: unless-stopped`), including after a reboot.
- Rate limit: 60 checks per IP per 10 minutes (judges may share one network).
- If arXiv is rate-limiting, use an example button or paste a bibliography instead of an arXiv ID.

## After the finals
Delete the VM (Vultr dashboard → Products → `vouch` → Destroy) and rotate the Vultr, OpenAlex, Semantic Scholar, inference and Vercel keys that were shared in chat.
