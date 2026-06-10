# Sunflower Panel Server

Sunflower Land icin lisans kontrollu bot dagitim sistemi.

## Klasorler

- `server/` Flask tabanli auth ve bot dagitim sunucusu
- `panel/` Tkinter tabanli script uretim ve bot yukleme paneli

## Mantik

1. Panel admin token ile servera baglanir.
2. Panel bot dosyasini servera yukler.
3. Panel kullanici icin ozel userscript uretir.
4. Userscript Sunflower Land uzerinde acilir.
5. Kullanici key girer.
6. Server lisansi dogrular.
7. Server bot kodunu kullaniciya ozel sekilde verir.
8. Script botu cacheleyip calistirir.

## Render env

Ornek degiskenler:

- `HOST=0.0.0.0`
- `PORT=10000`
- `ADMIN_TOKEN=...`
- `SERVER_LICENSE_SECRET=...`
- `SUPABASE_URL=...`
- `SUPABASE_SERVICE_KEY=...`
- `ALLOWED_ORIGINS=*`
- `SESSION_TTL_SECONDS=21600`
- `ADMIN_RATE_LIMIT_PER_MIN=120`
- `AUTH_RATE_LIMIT_PER_MIN=240`

## Calistirma

### Server

```bash
pip install -r server/requirements.txt
python server/server.py
```

### Panel

```bash
python panel/t.py
```
