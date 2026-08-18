# Nova Agent

**Secure remote maintenance agent for local Git repositories.**

Kelola repo GitHub/GitLab lokal dari mana saja (HP, laptop lain, atau chat AI) tanpa perlu akses langsung ke PC tempat repo berada.

```
[HP / AI / Laptop]  ->  Internet  ->  Cloudflare Tunnel / ngrok  ->  localhost:8080  ->  Local Git Repo
```

## Fitur

| Kategori | Endpoint | Keterangan |
|----------|----------|------------|
| **File** | GET /files | List directory |
| | GET /files/content | Baca file |
| | PUT /files | Tulis / overwrite file |
| | DELETE /files | Hapus file |
| **Git** | GET /git/status | Status working tree |
| | GET /git/diff | Diff (working / staged) |
| | GET /git/log | Commit history |
| | GET /git/show | Show commit |
| | GET /git/branch | List branch |
| | POST /git/commit | Commit |
| | POST /git/push | Push |
| | POST /git/pull | Pull |
| | POST /git/branch/create | Buat branch |
| | POST /git/branch/checkout | Checkout branch |
| | POST /git/branch/delete | Hapus branch |
| | POST /git/branch/rename | Rename branch |
| **Quality** | POST /quality/run | Jalankan pytest / ruff / mypy / black |
| **Server** | GET /health | Health check (tanpa auth) |
| | GET /config | Lihat konfigurasi (tanpa secret) |
| | GET /audit | Baca audit log |

## Keamanan (9 Layer)

1. HTTPS via Cloudflare Tunnel atau ngrok
2. Bearer Auth
3. Constant-time key comparison
4. Path Sandboxing
5. Command Whitelist
6. Feature Flags (ALLOW_WRITE, ALLOW_PUSH, dll)
7. Rate Limiting
8. Idle Timeout
9. Audit Logging

Mode: `git` (full) atau `folder` (file ops only).

## Install

```bash
git clone https://github.com/rndz1618/nova-agent.git
cd nova-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env: NOVA_API_KEY, REPO_PATH, MODE, TUNNEL_PROVIDER
chmod +x scripts/*.sh
./scripts/start-nova.sh
# stop: ./scripts/stop-nova.sh
```

## Contoh

```bash
export NOVA_URL="https://xxxx.trycloudflare.com"
export NOVA_KEY="your-secret-key"
curl -H "Authorization: Bearer $NOVA_KEY" $NOVA_URL/git/status
```

Lihat `.env.example` untuk semua opsi konfigurasi.
