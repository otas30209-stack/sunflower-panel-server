# Sunflower Server

Bu klasor, panel baglanmaya hazir Sunflower server projesidir.

## Mantik
- bot kodu `workspace/bot.txt` icinde tutulur
- server lisans, auth, heartbeat, bot dagitimi, notice, Telegram ve Supabase state sync islerini yonetir
- panel admin token ile servera baglanir

## Ana dosyalar
- `server.py` -> ana Flask server
- `config.py` -> env ve dosya yollari
- `requirements.txt` -> Python paketleri
- `.env.example` -> ornek env
- `render.yaml` -> bu klasor tek basina deploy edilecekse Render tanimi
- `workspace/` -> runtime json state alani

## Render
Start command:
```txt
python server.py
```
