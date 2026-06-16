#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import Flask, request, jsonify
from flask_cors import CORS
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import threading
from datetime import datetime
from io import BytesIO
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from config import (
    HOST, PORT, ADMIN_TOKEN, SERVER_LICENSE_SECRET, SUPABASE_URL, SUPABASE_SERVICE_KEY,
    D1_STATE_API_URL, D1_STATE_API_TOKEN, ALLOWED_ORIGINS,
    USERS_FILE, LICENSES_FILE, NOTICE_FILE, LOGS_FILE, BOT_FILE,
    REVOKED_LICENSES_FILE, QUICK_LINKS_FILE,
    ADMIN_ALLOWED_IPS, SESSION_TTL_SECONDS, ADMIN_RATE_LIMIT_PER_MIN, AUTH_RATE_LIMIT_PER_MIN,
    TASKS_CONFIG_FILE, BANNED_UIDS_FILE,
)

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": ALLOWED_ORIGINS or "*"}})

IV = b'dYQ9R99bkKLsLHad'
LICENSE_SECRET = hashlib.sha256((SERVER_LICENSE_SECRET or 'sunflower-default-secret').encode('utf-8')).digest()[:32]
DATA_SECRET = hashlib.sha256((str(SERVER_LICENSE_SECRET or 'sunflower-default-secret') + '|data').encode('utf-8')).digest()[:32]
MAX_SESSIONS_PER_USER = 20
pending_client_commands = []
pending_bot_commands = []
request_buckets = {}
last_bot_status = {
    'updated_at': '',
    'status_text': 'Ready',
    'captcha_waiting': False,
    'captcha_game_id': None,
    'level_missing': False,
    'missing_level_info': {},
    'ready_games_count': 0,
    'total_loaded_games': 0,
    'total_played_games': 0,
    'total_power': 0,
    'history_count': 0,
}

DEFAULT_TASK_ROUTES = {
    'games_page': 'https://sunflower-land.com/',
    'preview_page': 'https://sunflower-land.com/',
    'status_page': 'https://sunflower-land.com/',
    'claim_pattern': '',
}

REMOTE_STATE_KEYS = {
    str(USERS_FILE): 'users',
    str(LICENSES_FILE): 'licenses',
    str(NOTICE_FILE): 'notice',
    str(BOT_FILE): 'bot',
    str(REVOKED_LICENSES_FILE): 'revoked_licenses',
    str(QUICK_LINKS_FILE): 'quick_links',
    str(TASKS_CONFIG_FILE): 'tasks_config',
    str(BANNED_UIDS_FILE): 'banned_uids',
}

BOT_TELEGRAM_I18N = {
    'tr': {
        'menu_ready': '🎮 Sunflower kontrol menusu hazir.',
        'menu_hint': '🎮 Kontrol menusu altta hazir knk.',
        'status_button': '🎮 Bot Durumu',
        'start_button': '▶️ Başlat',
        'stop_button': '⏹️ Durdur',
        'screenshot_button': '📸 Ekran Al',
        'refresh_button': '🔄 Sayfa Yenile',
        'captcha_inline': '✅ Cozdum',
        'status_text': '📊 Durum\nHazir gorev: {ready}\nToplam islem: {played}\nToplam puan: {power}',
        'captcha_detected': '🚨 CAPTCHA algilandi! Gorev {game}\nCozduysen alttaki butona bas.',
        'captcha_solved': '✅ CAPTCHA cozuldu, devam komutu gonderildi.',
        'start_sent': '▶️ Baslat komutu gonderildi.',
        'stop_sent': '⏹️ Durdur komutu gonderildi.',
        'refresh_sent': '🔄 Sayfa yenile komutu gonderildi.',
        'screenshot_sent': '📸 Ekran alma komutu gonderildi.',
        'callback_ok': 'Tamam knk',
        'telegram_connected': '✅ Telegram baglandi. Bu script icin kontrol menusu aktif.',
        'screenshot_caption': 'Sunflower ekran goruntusu',
        'level_missing': '⚠️ LEVEL EKSIK! Gorev {game} level {level}'
    },
    'en': {
        'menu_ready': '🎮 Sunflower control menu is ready.',
        'menu_hint': '🎮 Control menu is ready below.',
        'status_button': '🎮 Bot Status',
        'start_button': '▶️ Start',
        'stop_button': '⏹️ Stop',
        'screenshot_button': '📸 Screenshot',
        'refresh_button': '🔄 Refresh Page',
        'captcha_inline': '✅ Solved',
        'status_text': '📊 Status\nReady tasks: {ready}\nTotal actions: {played}\nTotal score: {power}',
        'captcha_detected': '🚨 CAPTCHA detected! Task {game}\nPress the button below after solving it.',
        'captcha_solved': '✅ CAPTCHA solved, continue command sent.',
        'start_sent': '▶️ Start command sent.',
        'stop_sent': '⏹️ Stop command sent.',
        'refresh_sent': '🔄 Refresh page command sent.',
        'screenshot_sent': '📸 Screenshot command sent.',
        'callback_ok': 'Done',
        'telegram_connected': '✅ Telegram connected. Control menu is active for this script.',
        'screenshot_caption': 'Sunflower screenshot',
        'level_missing': '⚠️ MISSING LEVEL! Task {game} level {level}'
    }
}


def _mask_sensitive_text(text):
    text = str(text or '')
    text = re.sub(r'([A-Fa-f0-9]{24})', lambda m: m.group(1)[:4] + '***' + m.group(1)[-4:], text)
    text = re.sub(r'(\b\d{6,}\b)', lambda m: m.group(1)[:3] + '***' + m.group(1)[-2:], text)
    text = re.sub(r'(bot\d+:[A-Za-z0-9_-]+)', 'bot***', text)
    return text


def log_event(event):
    try:
        with open(LOGS_FILE, 'a', encoding='utf-8') as f:
            safe_event = _mask_sensitive_text(event)
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {safe_event}\n")
    except Exception:
        pass


def _supabase_enabled():
    return bool(SUPABASE_URL and SUPABASE_SERVICE_KEY)


def _supabase_headers():
    return {
        'apikey': SUPABASE_SERVICE_KEY,
        'Authorization': f'Bearer {SUPABASE_SERVICE_KEY}',
        'Content-Type': 'application/json'
    }


def _supabase_get_state(state_key, default):
    if not _supabase_enabled():
        return default
    try:
        url = f"{SUPABASE_URL}/rest/v1/app_state?key=eq.{quote(state_key)}&select=value"
        req = urlrequest.Request(url, headers=_supabase_headers(), method='GET')
        with urlrequest.urlopen(req, timeout=20) as resp:
            rows = json.loads(resp.read().decode('utf-8'))
        if rows and isinstance(rows, list):
            return rows[0].get('value', default)
    except Exception as e:
        log_event(f'Supabase load error ({state_key}): {e}')
    return default


def _supabase_set_state(state_key, value):
    if not _supabase_enabled():
        return False
    try:
        body = json.dumps({
            'key': state_key,
            'value': value,
            'updated_at': datetime.now().isoformat()
        }).encode('utf-8')
        headers = _supabase_headers()
        headers['Prefer'] = 'resolution=merge-duplicates'
        url = f"{SUPABASE_URL}/rest/v1/app_state?on_conflict=key"
        req = urlrequest.Request(url, data=body, headers=headers, method='POST')
        with urlrequest.urlopen(req, timeout=20) as resp:
            resp.read()
        return True
    except Exception as e:
        log_event(f'Supabase save error ({state_key}): {e}')
        return False


def _d1_state_enabled():
    return bool(D1_STATE_API_URL and D1_STATE_API_TOKEN)


def _d1_state_headers():
    return {
        'Authorization': f'Bearer {D1_STATE_API_TOKEN}',
        'Content-Type': 'application/json'
    }


def _d1_get_state(state_key, default):
    if not _d1_state_enabled():
        return default
    try:
        url = f"{D1_STATE_API_URL}/state/{quote(state_key)}"
        req = urlrequest.Request(url, headers=_d1_state_headers(), method='GET')
        with urlrequest.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode('utf-8') or '{}')
        if payload.get('success') and payload.get('found'):
            return payload.get('value', default)
    except Exception as e:
        log_event(f'D1 state load error ({state_key}): {e}')
    return default


def _d1_set_state(state_key, value):
    if not _d1_state_enabled():
        return False
    try:
        body = json.dumps({'value': value}).encode('utf-8')
        url = f"{D1_STATE_API_URL}/state/{quote(state_key)}"
        req = urlrequest.Request(url, data=body, headers=_d1_state_headers(), method='PUT')
        with urlrequest.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode('utf-8') or '{}')
        return bool(payload.get('success'))
    except Exception as e:
        log_event(f'D1 state save error ({state_key}): {e}')
        return False


def load_json(path, default):
    state_key = REMOTE_STATE_KEYS.get(str(path))
    if state_key:
        remote = _d1_get_state(state_key, None)
        if remote is not None:
            return remote
        remote = _supabase_get_state(state_key, None)
        if remote is not None:
            return remote
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def save_json(path, data):
    state_key = REMOTE_STATE_KEYS.get(str(path))
    if state_key:
        _d1_set_state(state_key, data)
        _supabase_set_state(state_key, data)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def encrypt_secret_value(value):
    text = str(value or '').strip()
    if not text:
        return ''
    if text.startswith('enc:v1:'):
        return text
    iv = os.urandom(16)
    cipher = AES.new(DATA_SECRET, AES.MODE_CBC, iv)
    encrypted = cipher.encrypt(pad(text.encode('utf-8'), AES.block_size))
    return 'enc:v1:' + base64.b64encode(iv + encrypted).decode('utf-8')


def decrypt_secret_value(value):
    text = str(value or '').strip()
    if not text:
        return ''
    if not text.startswith('enc:v1:'):
        return text
    try:
        raw = base64.b64decode(text.split(':', 2)[2])
        iv = raw[:16]
        data = raw[16:]
        cipher = AES.new(DATA_SECRET, AES.MODE_CBC, iv)
        return unpad(cipher.decrypt(data), AES.block_size).decode('utf-8')
    except Exception:
        return ''


def uid_hash_text(uid):
    return hashlib.sha256((str(uid or '').strip().lower() + '|uid').encode('utf-8')).hexdigest()


def _decode_license_row(row):
    row = dict(row or {})
    row['uid'] = decrypt_secret_value(row.get('uid'))
    row['telegram_token'] = decrypt_secret_value(row.get('telegram_token'))
    row['telegram_chat_id'] = decrypt_secret_value(row.get('telegram_chat_id'))
    return row


def _encode_license_row(row):
    row = dict(row or {})
    raw_uid = str(row.get('uid') or '').strip().lower()
    row['uid_hash'] = uid_hash_text(raw_uid) if raw_uid else ''
    row['uid'] = encrypt_secret_value(raw_uid)
    row['telegram_token'] = encrypt_secret_value(row.get('telegram_token'))
    row['telegram_chat_id'] = encrypt_secret_value(row.get('telegram_chat_id'))
    return row


def _decode_user_row(row):
    row = dict(row or {})
    row['uid'] = decrypt_secret_value(row.get('uid'))
    return row


def _encode_user_row(row):
    row = dict(row or {})
    raw_uid = str(row.get('uid') or '').strip().lower()
    row['uid_hash'] = uid_hash_text(raw_uid) if raw_uid else ''
    row['uid'] = encrypt_secret_value(raw_uid)
    return row


def load_users():
    data = load_json(USERS_FILE, {})
    if not isinstance(data, dict):
        return {}
    decoded = {}
    for storage_key, row in data.items():
        row = _decode_user_row(row)
        uid = str(row.get('uid') or '').strip().lower() or str(storage_key or '').strip().lower()
        if uid:
            decoded[uid] = row
    return decoded


def save_users(data):
    payload = data if isinstance(data, dict) else {}
    encoded = {}
    for uid, row in payload.items():
        row = dict(row or {})
        row['uid'] = str(row.get('uid') or uid or '').strip().lower()
        key = uid_hash_text(row['uid']) if row['uid'] else str(uid or '').strip().lower()
        encoded[key] = _encode_user_row(row)
    save_json(USERS_FILE, encoded)


def load_licenses():
    data = load_json(LICENSES_FILE, {})
    if not isinstance(data, dict):
        return {}
    return {lid: _decode_license_row(row) for lid, row in data.items()}


def save_licenses(data):
    payload = data if isinstance(data, dict) else {}
    save_json(LICENSES_FILE, {lid: _encode_license_row(row) for lid, row in payload.items()})


def load_notice():
    data = load_json(NOTICE_FILE, {'id': '', 'text': '', 'created_at': '', 'links': {}, 'links_active': False})
    if not isinstance(data, dict):
        data = {'id': '', 'text': '', 'created_at': '', 'links': {}, 'links_active': False}
    data.setdefault('links', {})
    data.setdefault('links_active', False)
    return data


def save_notice(data):
    payload = data if isinstance(data, dict) else {'id': '', 'text': '', 'created_at': '', 'links': {}, 'links_active': False}
    payload.setdefault('links', {})
    payload.setdefault('links_active', False)
    save_json(NOTICE_FILE, payload)


def load_quick_links():
    data = load_json(QUICK_LINKS_FILE, {
        'active': False,
        'telegram': '', 'youtube': '', 'login': '', 'normal': '', 'error_link': '',
        'login_telegram': '', 'login_youtube': '', 'login_normal': '',
        'login_telegram_enabled': False, 'login_youtube_enabled': False, 'login_normal_enabled': False,
        'key_telegram': '', 'key_youtube': '', 'key_normal': '', 'key_error_link': '', 'key_warning_text': 'LUTFEN YONETICIDEN KEY TALEP EDINIZ',
        'key_telegram_enabled': False, 'key_youtube_enabled': False, 'key_normal_enabled': False,
        'telegram_screen_telegram': '', 'telegram_screen_youtube': '', 'telegram_screen_normal': '',
        'telegram_screen_telegram_enabled': False, 'telegram_screen_youtube_enabled': False, 'telegram_screen_normal_enabled': False,
        'show_key_telegram': False
    })
    src = data or {}
    return {
        'active': bool(src.get('active', False)),
        'telegram': str(src.get('telegram') or '').strip(),
        'youtube': str(src.get('youtube') or '').strip(),
        'login': str(src.get('login') or '').strip(),
        'normal': str(src.get('normal') or '').strip(),
        'error_link': str(src.get('error_link') or '').strip(),
        'login_telegram': str(src.get('login_telegram') or '').strip(),
        'login_youtube': str(src.get('login_youtube') or '').strip(),
        'login_normal': str(src.get('login_normal') or '').strip(),
        'login_telegram_enabled': bool(src.get('login_telegram_enabled', False)),
        'login_youtube_enabled': bool(src.get('login_youtube_enabled', False)),
        'login_normal_enabled': bool(src.get('login_normal_enabled', False)),
        'key_telegram': str(src.get('key_telegram') or '').strip(),
        'key_youtube': str(src.get('key_youtube') or '').strip(),
        'key_normal': str(src.get('key_normal') or '').strip(),
        'key_telegram_enabled': bool(src.get('key_telegram_enabled', False)),
        'key_youtube_enabled': bool(src.get('key_youtube_enabled', False)),
        'key_normal_enabled': bool(src.get('key_normal_enabled', False)),
        'key_error_link': str(src.get('key_error_link') or '').strip(),
        'key_warning_text': str(src.get('key_warning_text') or 'LUTFEN YONETICIDEN KEY TALEP EDINIZ').strip(),
        'telegram_screen_telegram': str(src.get('telegram_screen_telegram') or '').strip(),
        'telegram_screen_youtube': str(src.get('telegram_screen_youtube') or '').strip(),
        'telegram_screen_normal': str(src.get('telegram_screen_normal') or '').strip(),
        'telegram_screen_telegram_enabled': bool(src.get('telegram_screen_telegram_enabled', False)),
        'telegram_screen_youtube_enabled': bool(src.get('telegram_screen_youtube_enabled', False)),
        'telegram_screen_normal_enabled': bool(src.get('telegram_screen_normal_enabled', False)),
        'show_key_telegram': bool(src.get('show_key_telegram', False)),
    }


def save_quick_links(data):
    src = data or {}
    save_json(QUICK_LINKS_FILE, {
        'active': bool(src.get('active', False)),
        'telegram': str(src.get('telegram') or '').strip(),
        'youtube': str(src.get('youtube') or '').strip(),
        'login': str(src.get('login') or '').strip(),
        'normal': str(src.get('normal') or '').strip(),
        'error_link': str(src.get('error_link') or '').strip(),
        'login_telegram': str(src.get('login_telegram') or '').strip(),
        'login_youtube': str(src.get('login_youtube') or '').strip(),
        'login_normal': str(src.get('login_normal') or '').strip(),
        'login_telegram_enabled': bool(src.get('login_telegram_enabled', False)),
        'login_youtube_enabled': bool(src.get('login_youtube_enabled', False)),
        'login_normal_enabled': bool(src.get('login_normal_enabled', False)),
        'key_telegram': str(src.get('key_telegram') or '').strip(),
        'key_youtube': str(src.get('key_youtube') or '').strip(),
        'key_normal': str(src.get('key_normal') or '').strip(),
        'key_telegram_enabled': bool(src.get('key_telegram_enabled', False)),
        'key_youtube_enabled': bool(src.get('key_youtube_enabled', False)),
        'key_normal_enabled': bool(src.get('key_normal_enabled', False)),
        'key_error_link': str(src.get('key_error_link') or '').strip(),
        'key_warning_text': str(src.get('key_warning_text') or 'LUTFEN YONETICIDEN KEY TALEP EDINIZ').strip(),
        'telegram_screen_telegram': str(src.get('telegram_screen_telegram') or '').strip(),
        'telegram_screen_youtube': str(src.get('telegram_screen_youtube') or '').strip(),
        'telegram_screen_normal': str(src.get('telegram_screen_normal') or '').strip(),
        'telegram_screen_telegram_enabled': bool(src.get('telegram_screen_telegram_enabled', False)),
        'telegram_screen_youtube_enabled': bool(src.get('telegram_screen_youtube_enabled', False)),
        'telegram_screen_normal_enabled': bool(src.get('telegram_screen_normal_enabled', False)),
        'show_key_telegram': bool(src.get('show_key_telegram', False)),
    })


def load_revoked_licenses():
    data = load_json(REVOKED_LICENSES_FILE, [])
    return data if isinstance(data, list) else []


def save_revoked_licenses(items):
    save_json(REVOKED_LICENSES_FILE, items if isinstance(items, list) else [])


def load_banned_uids():
    data = load_json(BANNED_UIDS_FILE, {})
    if isinstance(data, list):
        data = {str(uid or '').strip().lower(): {'uid': str(uid or '').strip().lower(), 'status': 'banned'} for uid in data}
    if not isinstance(data, dict):
        return {}
    normalized = {}
    for uid, row in data.items():
        key = str((row or {}).get('uid') or uid or '').strip().lower()
        if not key:
            continue
        normalized[key] = {
            'uid': key,
            'status': 'banned',
            'reason': str((row or {}).get('reason') or 'admin').strip(),
            'created_at': str((row or {}).get('created_at') or datetime.now().isoformat()),
            'license_id': str((row or {}).get('license_id') or '').strip(),
            'client_name': str((row or {}).get('client_name') or '').strip(),
        }
    return normalized


def save_banned_uids(items):
    payload = items if isinstance(items, dict) else {}
    normalized = {}
    for uid, row in payload.items():
        key = str((row or {}).get('uid') or uid or '').strip().lower()
        if not key:
            continue
        normalized[key] = {
            'uid': key,
            'status': 'banned',
            'reason': str((row or {}).get('reason') or 'admin').strip(),
            'created_at': str((row or {}).get('created_at') or datetime.now().isoformat()),
            'license_id': str((row or {}).get('license_id') or '').strip(),
            'client_name': str((row or {}).get('client_name') or '').strip(),
        }
    save_json(BANNED_UIDS_FILE, normalized)


def is_banned_uid(uid):
    uid = str(uid or '').strip().lower()
    return bool(uid) and uid in load_banned_uids()


def load_tasks_config():
    default = {'routes': dict(DEFAULT_TASK_ROUTES), 'licenses': {}}
    if _supabase_enabled():
        remote = _supabase_get_state('tasks_config', None)
        if isinstance(remote, dict):
            return {
                'routes': dict(remote.get('routes') or DEFAULT_TASK_ROUTES),
                'licenses': dict(remote.get('licenses') or {})
            }
    try:
        data = json.loads(TASKS_CONFIG_FILE.read_text(encoding='utf-8'))
        return {
            'routes': dict((data or {}).get('routes') or DEFAULT_TASK_ROUTES),
            'licenses': dict((data or {}).get('licenses') or {})
        }
    except Exception:
        return default


def save_tasks_config(data):
    payload = {
        'routes': dict((data or {}).get('routes') or DEFAULT_TASK_ROUTES),
        'licenses': dict((data or {}).get('licenses') or {})
    }
    if _supabase_enabled():
        _supabase_set_state('tasks_config', payload)
    TASKS_CONFIG_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def merge_task_routes(base_routes=None, override_routes=None):
    merged = dict(DEFAULT_TASK_ROUTES)
    if isinstance(base_routes, dict):
        for key, value in base_routes.items():
            value = str(value or '').strip()
            if value:
                merged[str(key)] = value
    if isinstance(override_routes, dict):
        for key, value in override_routes.items():
            value = str(value or '').strip()
            if value:
                merged[str(key)] = value
    return merged


def secure_equals(left, right):
    left = str(left or '')
    right = str(right or '')
    return bool(left) and bool(right) and hmac.compare_digest(left, right)


def _client_ip(req):
    forwarded = str(req.headers.get('X-Forwarded-For') or '').split(',')[0].strip()
    return forwarded or str(req.remote_addr or '').strip()


def _rate_limit_ok(scope, key, limit_per_min):
    now = datetime.now().timestamp()
    bucket_key = f'{scope}:{key}'
    entries = [ts for ts in request_buckets.get(bucket_key, []) if now - ts < 60]
    if len(entries) >= max(1, int(limit_per_min or 1)):
        request_buckets[bucket_key] = entries
        return False
    entries.append(now)
    request_buckets[bucket_key] = entries
    return True


@app.before_request
def harden_request_gate():
    ip = _client_ip(request)
    path = str(request.path or '')
    if path.startswith('/admin/'):
        if not _rate_limit_ok('admin', ip, ADMIN_RATE_LIMIT_PER_MIN):
            return jsonify({'success': False, 'error': 'cok fazla istek'}), 429
    elif path in {'/api/auth', '/api/heartbeat', '/api/client/command', '/api/telegram/register', '/api/telegram/screenshot', '/api/notice/next', '/api/notice/ack', '/api/tasks/analyze', '/api/tasks/config', '/api/bot/plan'}:
        if not _rate_limit_ok('api', ip, AUTH_RATE_LIMIT_PER_MIN):
            return jsonify({'success': False, 'error': 'cok fazla istek'}), 429
    return None


@app.after_request
def apply_security_headers(resp):
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    resp.headers['X-Frame-Options'] = 'DENY'
    resp.headers['Referrer-Policy'] = 'no-referrer'
    resp.headers['Cache-Control'] = 'no-store'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    return resp


def check_admin(req):
    token = str(req.headers.get('X-Admin-Token') or '').strip() or str(req.headers.get('Authorization') or '').replace('Bearer ', '').strip() or str(req.args.get('token') or '').strip()
    if not (bool(ADMIN_TOKEN) and bool(token) and hmac.compare_digest(token, ADMIN_TOKEN)):
        return False
    if ADMIN_ALLOWED_IPS:
        return _client_ip(req) in ADMIN_ALLOWED_IPS
    return True


def encrypt_license_for_server(payload: dict):
    plaintext = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    cipher = AES.new(LICENSE_SECRET, AES.MODE_CBC, IV)
    encrypted = cipher.encrypt(pad(plaintext, AES.block_size))
    return base64.urlsafe_b64encode(encrypted).decode('utf-8')


def decrypt_license_for_server(token: str):
    try:
        raw = base64.urlsafe_b64decode(str(token).encode('utf-8'))
        cipher = AES.new(LICENSE_SECRET, AES.MODE_CBC, IV)
        plaintext = unpad(cipher.decrypt(raw), AES.block_size).decode('utf-8')
        return json.loads(plaintext)
    except Exception:
        return None


def build_session_token(license_id, uid):
    raw = f"{license_id}|{uid}|{datetime.now().isoformat()}|{secrets.token_hex(16)}"
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def derive_runtime_uid(license_id, client_id, fallback_uid=''):
    raw_uid = str(fallback_uid or '').strip().lower()
    if raw_uid:
        return raw_uid
    seed = f"{license_id}|{client_id}|guest"
    return 'guest_' + hashlib.sha256(seed.encode('utf-8')).hexdigest()[:24]


def identity_label_text(identity):
    text = str(identity or '').strip()
    return text or 'guest'


def evp_bytes_to_key(password, salt, key_len, iv_len):
    d = d_i = b''
    while len(d) < key_len + iv_len:
        d_i = hashlib.md5(d_i + password + salt).digest()
        d += d_i
    return d[:key_len], d[key_len:key_len + iv_len]


def encrypt_with_uid(data, uid):
    plaintext = json.dumps(data, separators=(',', ':')) if isinstance(data, (dict, list)) else str(data)
    salt = os.urandom(8)
    password = str(uid or '').encode('utf-8')
    key, iv = evp_bytes_to_key(password, salt, 32, 16)
    pad_len = 16 - (len(plaintext) % 16)
    padded = plaintext.encode('utf-8') + bytes([pad_len] * pad_len)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    ciphertext = cipher.encrypt(padded)
    encrypted = b'Salted__' + salt + ciphertext
    return base64.b64encode(encrypted).decode('utf-8')


def encrypt_bot_for_uid(bot_code, uid):
    key_bytes = (str(uid or '').encode('utf-8') * 128)
    src = str(bot_code or '').encode('utf-8')
    xored = bytes(b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(src))
    return base64.b64encode(xored).decode('utf-8')


def patch_bot_content(content: str):
    server_url = request.host_url.rstrip('/') if request else ''
    content = str(content or '')
    if '__SERVER_URL__' in content:
        content = content.replace('__SERVER_URL__', server_url)
    return content


def _looks_like_userscript(content):
    text = str(content or '').strip()
    return bool(text) and (('// ==UserScript==' in text and '@match' in text) or '(function()' in text or 'GM_xmlhttpRequest' in text)


def load_bot_content():
    try:
        content = load_json(BOT_FILE, '') if (_d1_state_enabled() or _supabase_enabled()) else BOT_FILE.read_text(encoding='utf-8', errors='ignore')
        if isinstance(content, dict):
            content = ''
        content = str(content or '')
        return content if _looks_like_userscript(content) else ''
    except Exception:
        return ''


def save_bot_content(content):
    normalized = str(content or '')
    save_json(BOT_FILE, normalized)
    BOT_FILE.write_text(normalized, encoding='utf-8')


def _cleanup_sessions(user):
    user = dict(user or {})
    sessions = []
    now = datetime.now()
    for session in (user.get('sessions') or []):
        session = dict(session or {})
        try:
            session_time = datetime.fromisoformat(str(session.get('time') or ''))
            if (now - session_time).total_seconds() <= SESSION_TTL_SECONDS:
                sessions.append(session)
        except Exception:
            continue
    user['sessions'] = sessions[-MAX_SESSIONS_PER_USER:]
    return user


def get_session_entry(user, token):
    token = str(token or '').strip()
    if not token or not isinstance(user, dict):
        return None
    user = _cleanup_sessions(user)
    for session in (user.get('sessions') or []):
        if secure_equals(str((session or {}).get('token') or '').strip(), token):
            return session
    return None


def valid_session(user, token):
    return get_session_entry(user, token) is not None


def resolve_session_license(user, token):
    session = get_session_entry(user, token)
    license_id = str((session or {}).get('license_id') or user.get('active_license_id') or user.get('license_id') or '').strip()
    return license_id, session


def is_license_online(row):
    hb = str((row or {}).get('last_heartbeat') or '').strip()
    if not hb:
        return False
    try:
        return (datetime.now() - datetime.fromisoformat(hb)).total_seconds() <= 45
    except Exception:
        return False


def pop_client_command_for_license(license_id):
    license_id = str(license_id or '').strip()
    for index, command in enumerate(pending_client_commands):
        cmd_license_id = str((command or {}).get('license_id') or '').strip()
        if not cmd_license_id or cmd_license_id == license_id:
            return pending_client_commands.pop(index)
    return None


def queue_client_command(command, license_id=''):
    pending_client_commands.append({
        'command': str(command or '').strip(),
        'license_id': str(license_id or '').strip(),
        'time': datetime.now().isoformat(),
        'source': 'admin'
    })


def queue_bot_command(command, license_id='', uid=''):
    pending_bot_commands.append({
        'command': str(command or '').strip().lower(),
        'license_id': str(license_id or '').strip(),
        'uid': str(uid or '').strip().lower(),
        'time': datetime.now().isoformat(),
        'source': 'telegram'
    })


def pop_bot_command(license_id='', uid=''):
    license_id = str(license_id or '').strip()
    uid = str(uid or '').strip().lower()
    for index, command in enumerate(pending_bot_commands):
        cmd_license_id = str((command or {}).get('license_id') or '').strip()
        cmd_uid = str((command or {}).get('uid') or '').strip().lower()
        if (license_id and cmd_license_id == license_id) or (uid and cmd_uid == uid) or (not cmd_license_id and not cmd_uid):
            return pending_bot_commands.pop(index)
    return None


def telegram_lang(license_row):
    lang = str((license_row or {}).get('language') or 'tr').strip().lower()
    return lang if lang in BOT_TELEGRAM_I18N else 'tr'


def tg_text(license_row, key, **kwargs):
    lang = telegram_lang(license_row)
    text = BOT_TELEGRAM_I18N.get(lang, BOT_TELEGRAM_I18N['tr']).get(key) or BOT_TELEGRAM_I18N['tr'].get(key) or key
    try:
        return str(text).format(**kwargs)
    except Exception:
        return str(text)


def build_license_telegram_menu(license_row=None):
    return {
        'keyboard': [
            [tg_text(license_row, 'status_button')],
            [tg_text(license_row, 'start_button'), tg_text(license_row, 'stop_button')],
            [tg_text(license_row, 'screenshot_button'), tg_text(license_row, 'refresh_button')],
        ],
        'resize_keyboard': True,
        'one_time_keyboard': False,
        'is_persistent': True
    }


def send_telegram_api(token, method, payload):
    token = str(token or '').strip()
    if not token:
        return False, {'error': 'telegram token bos'}
    try:
        body = json.dumps(payload or {}).encode('utf-8')
        req = urlrequest.Request(
            f'https://api.telegram.org/bot{token}/{method}',
            data=body,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        with urlrequest.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        return bool(data.get('ok')), data
    except (HTTPError, URLError) as e:
        return False, {'error': str(e)}
    except Exception as e:
        return False, {'error': str(e)}


def send_license_telegram_menu(license_row, text=None):
    token = str(license_row.get('telegram_token') or '').strip()
    chat_id = str(license_row.get('telegram_chat_id') or '').strip()
    if not token or not chat_id:
        return False, {'error': 'telegram bilgisi eksik'}
    return send_telegram_api(token, 'sendMessage', {
        'chat_id': chat_id,
        'text': text or tg_text(license_row, 'menu_ready'),
        'reply_markup': build_license_telegram_menu(license_row)
    })


def send_captcha_telegram_menu(license_row, game_id=None):
    token = str(license_row.get('telegram_token') or '').strip()
    chat_id = str(license_row.get('telegram_chat_id') or '').strip()
    if not token or not chat_id:
        return False, {'error': 'telegram bilgisi eksik'}
    send_license_telegram_menu(license_row, tg_text(license_row, 'menu_hint'))
    text = tg_text(license_row, 'captcha_detected', game=game_id or '-')
    return send_telegram_api(token, 'sendMessage', {
        'chat_id': chat_id,
        'text': text,
        'reply_markup': {
            'inline_keyboard': [
                [{'text': tg_text(license_row, 'captcha_inline'), 'callback_data': 'captcha_solved'}]
            ]
        }
    })


def send_telegram_photo(token, chat_id, photo_bytes, caption=''):
    token = str(token or '').strip()
    chat_id = str(chat_id or '').strip()
    if not token or not chat_id:
        return False, {'error': 'telegram bilgisi eksik'}
    boundary = '----SunflowerBoundary' + secrets.token_hex(8)
    body = BytesIO()

    def _write_field(name, value):
        body.write(f'--{boundary}\r\n'.encode('utf-8'))
        body.write(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode('utf-8'))
        body.write(str(value).encode('utf-8'))
        body.write(b'\r\n')

    _write_field('chat_id', chat_id)
    if caption:
        _write_field('caption', caption)
    body.write(f'--{boundary}\r\n'.encode('utf-8'))
    body.write(b'Content-Disposition: form-data; name="photo"; filename="sunflower.jpg"\r\n')
    body.write(b'Content-Type: image/jpeg\r\n\r\n')
    body.write(photo_bytes)
    body.write(b'\r\n')
    body.write(f'--{boundary}--\r\n'.encode('utf-8'))

    try:
        req = urlrequest.Request(
            f'https://api.telegram.org/bot{token}/sendPhoto',
            data=body.getvalue(),
            headers={'Content-Type': f'multipart/form-data; boundary={boundary}'},
            method='POST'
        )
        with urlrequest.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        return bool(data.get('ok')), data
    except (HTTPError, URLError) as e:
        return False, {'error': str(e)}
    except Exception as e:
        return False, {'error': str(e)}


def process_telegram_action(license_row, action):
    action = str(action or '').strip().lower()
    license_id = str(license_row.get('license_id') or '').strip()
    uid = str(license_row.get('uid') or '').strip().lower()
    if action in {'status', 'bot_status'}:
        return send_license_telegram_menu(license_row, tg_text(license_row, 'status_text', ready=last_bot_status.get('ready_games_count', 0), played=last_bot_status.get('total_played_games', 0), power=last_bot_status.get('total_power', 0)))
    if action in {'start', 'captcha_solved'}:
        queue_bot_command('start', license_id, uid)
        msg = tg_text(license_row, 'captcha_solved') if action == 'captcha_solved' else tg_text(license_row, 'start_sent')
        return send_license_telegram_menu(license_row, msg)
    if action == 'stop':
        queue_bot_command('stop', license_id, uid)
        return send_license_telegram_menu(license_row, tg_text(license_row, 'stop_sent'))
    if action == 'refresh':
        queue_client_command('refresh_page', license_id)
        return send_license_telegram_menu(license_row, tg_text(license_row, 'refresh_sent'))
    if action == 'screenshot':
        queue_client_command('send_screenshot', license_id)
        return send_license_telegram_menu(license_row, tg_text(license_row, 'screenshot_sent'))
    return send_license_telegram_menu(license_row)


def poll_all_telegram_bots():
    tg_offsets = {}
    while True:
        try:
            licenses = load_licenses()
            for lid, row in licenses.items():
                token = str((row or {}).get('telegram_token') or '').strip()
                chat_id = str((row or {}).get('telegram_chat_id') or '').strip()
                if not token or not chat_id:
                    continue
                key = token[-24:]
                offset = int(tg_offsets.get(key, 0) or 0)
                ok, data = send_telegram_api(token, 'getUpdates', {'offset': offset, 'timeout': 0, 'allowed_updates': ['message', 'callback_query']})
                if not ok:
                    continue
                for upd in data.get('result', []):
                    update_id = int(upd.get('update_id', 0) or 0)
                    if update_id >= offset:
                        tg_offsets[key] = update_id + 1
                    callback = upd.get('callback_query') or {}
                    if callback:
                        incoming_chat = str((((callback.get('message') or {}).get('chat') or {}).get('id')) or '').strip()
                        if incoming_chat == chat_id:
                            action = str(callback.get('data') or '').strip().lower()
                            if action:
                                process_telegram_action(row, action)
                            callback_id = str(callback.get('id') or '').strip()
                            if callback_id:
                                send_telegram_api(token, 'answerCallbackQuery', {'callback_query_id': callback_id, 'text': tg_text(row, 'callback_ok')})
                        continue
                    msg = upd.get('message') or {}
                    incoming_chat = str(((msg.get('chat') or {}).get('id')) or '').strip()
                    if incoming_chat != chat_id:
                        continue
                    text = str(msg.get('text') or '').strip().lower()
                    if text in {'/start', '/menu', 'menu', '🎮 bot durumu', '🎮 bot status'}:
                        process_telegram_action(row, 'status' if 'durum' in text or 'status' in text else 'menu')
                    elif text in {'▶️ başlat', '▶️ baslat', '▶️ start'}:
                        process_telegram_action(row, 'start')
                    elif text in {'✅ cozdum devam et', '✅ çözdüm devam et', 'cozdum devam et', 'çözdüm devam et', '✅ cozdum', '✅ çözdüm', '✅ solved', 'solved'}:
                        process_telegram_action(row, 'captcha_solved')
                    elif text in {'⏹️ durdur', '⏹️ stop'}:
                        process_telegram_action(row, 'stop')
                    elif text in {'📸 ekran al', '📸 screenshot'}:
                        process_telegram_action(row, 'screenshot')
                    elif text in {'🔄 sayfa yenile', '🔄 refresh page'}:
                        process_telegram_action(row, 'refresh')
        except Exception as e:
            log_event(f'Telegram polling error: {e}')
        threading.Event().wait(5)


def is_revoked_license(license_id='', encrypted_license='', client_id='', script_hash=''):
    for item in load_revoked_licenses():
        if license_id and str(item.get('license_id') or '').strip() == str(license_id).strip():
            return True
        if encrypted_license and str(item.get('encrypted_license') or '').strip() == str(encrypted_license).strip():
            return True
        if client_id and str(item.get('client_id') or '').strip() == str(client_id).strip():
            return True
        if script_hash and str(item.get('script_hash') or '').strip() == str(script_hash).strip():
            return True
    return False


def require_bot_identity(req):
    uid = str(req.headers.get('X-VIP-UID') or '').strip().lower()
    session_token = str(req.headers.get('X-VIP-Session-Token') or '').strip()
    client_id = str(req.headers.get('X-VIP-Client-ID') or '').strip()
    script_hash = str(req.headers.get('X-VIP-Script-Hash') or '').strip()
    if not uid or not session_token or not client_id:
        return None, (jsonify({'success': False, 'error': 'yetkisiz bot'}), 401)
    if is_banned_uid(uid):
        return None, (jsonify({'success': False, 'error': 'Script gecersiz Hata kodu (4003)'}), 403)
    users = load_users()
    user = users.get(uid)
    if not user or not valid_session(user, session_token):
        return None, (jsonify({'success': False, 'error': 'yetkisiz bot'}), 401)
    license_id, session = resolve_session_license(user, session_token)
    licenses = load_licenses()
    row = dict(licenses.get(license_id or '', {}))
    if not row or not row.get('active', True) or str(row.get('status') or 'active').strip().lower() != 'active':
        return None, (jsonify({'success': False, 'error': 'off'}), 403)
    if str(row.get('uid') or '').strip().lower() != uid:
        return None, (jsonify({'success': False, 'error': 'script gecersiz'}), 403)
    expected_client_id = str((session or {}).get('client_id') or row.get('client_id') or '').strip()
    if expected_client_id and client_id != expected_client_id:
        return None, (jsonify({'success': False, 'error': 'script kimligi uyusmuyor'}), 401)
    expected_hash = str((session or {}).get('script_hash') or row.get('script_hash') or '').strip()
    if expected_hash and script_hash and script_hash != expected_hash:
        return None, (jsonify({'success': False, 'error': 'script dogrulamasi basarisiz'}), 401)
    return {'uid': uid, 'license_id': license_id, 'user': user, 'license': row, 'session': session}, None


@app.get('/')
def index():
    return jsonify({'success': True, 'service': 'sunflower-server', 'status': 'ok'})


@app.get('/health')
def health():
    return jsonify({'success': True, 'service': 'sunflower-server', 'time': datetime.now().isoformat()})


@app.get('/api/health')
def api_health():
    return jsonify({'success': True, 'service': 'sunflower-server', 'time': datetime.now().isoformat()})


@app.get('/api/public-links')
def public_links():
    return jsonify({'success': True, 'quick_links': load_quick_links()})


@app.post('/api/auth')
def api_auth():
    data = request.get_json(silent=True) or {}
    uid = str(data.get('uid') or '').strip().lower()
    encrypted_license = str(data.get('license_key') or '').strip()
    client_id = str(data.get('client_id') or '').strip()
    script_hash = str(data.get('script_hash') or '').strip()
    language = str(data.get('language') or 'tr').strip().lower() or 'tr'

    if not encrypted_license:
        return jsonify({'success': False, 'error': 'Lisans gerekli'}), 400
    if is_banned_uid(uid):
        return jsonify({'success': False, 'error': 'Script gecersiz Hata kodu (4003)'}), 403

    payload = decrypt_license_for_server(encrypted_license)
    if not payload:
        return jsonify({'success': False, 'error': 'Gecersiz lisans'}), 403

    license_id = str(payload.get('license_id') or '').strip()
    if not license_id:
        return jsonify({'success': False, 'error': 'Lisans bozuk'}), 403
    if is_revoked_license(license_id, encrypted_license, client_id, script_hash):
        return jsonify({'success': False, 'error': 'Script gecersiz'}), 403

    uid = derive_runtime_uid(license_id, client_id, uid)
    if is_banned_uid(uid):
        return jsonify({'success': False, 'error': 'Script gecersiz Hata kodu (4003)'}), 403

    licenses = load_licenses()
    row = dict(licenses.get(license_id, {}))
    if not row:
        row = {
            'license_id': license_id,
            'client_name': str(payload.get('client_name') or 'Kullanici').strip(),
            'client_id': str(payload.get('client_id') or client_id).strip(),
            'encrypted_license': encrypted_license,
            'script_hash': str(payload.get('script_hash') or script_hash).strip(),
            'uid': '',
            'status': 'active',
            'active': True,
            'uid_mode': 'replace',
            'language': language,
            'created_at': datetime.now().isoformat(),
            'last_heartbeat': '',
            'telegram_token': '',
            'telegram_chat_id': '',
            'sessions': []
        }

    if not row.get('active', True) or str(row.get('status') or 'active').strip().lower() != 'active':
        return jsonify({'success': False, 'error': 'Lisans pasif'}), 403

    stored_client_id = str(row.get('client_id') or '').strip()
    if stored_client_id and client_id and stored_client_id != client_id:
        return jsonify({'success': False, 'error': 'Script gecersiz'}), 403

    stored_hash = str(row.get('script_hash') or '').strip()
    if stored_hash and script_hash and stored_hash != script_hash:
        return jsonify({'success': False, 'error': 'Script gecersiz'}), 403

    allow_uid_change = bool(row.get('allow_uid_change', str(row.get('uid_mode') or 'replace') != 'fixed'))
    current_uid = str(row.get('uid') or '').strip().lower()
    if current_uid and current_uid != uid and not allow_uid_change:
        return jsonify({'success': False, 'error': 'Script gecersiz'}), 403

    users = load_users()
    if current_uid and current_uid != uid and allow_uid_change:
        users.pop(current_uid, None)
    for other_lid, other_row in list(licenses.items()):
        if str(other_lid or '').strip() == license_id:
            continue
        other_row = dict(other_row or {})
        other_uid = str(other_row.get('uid') or '').strip().lower()
        if other_uid == uid:
            other_row['last_uid'] = other_uid
            other_row['uid'] = ''
            other_row['last_heartbeat'] = ''
            other_row['sessions'] = []
            if str(other_row.get('status') or '').strip().lower() == 'banned':
                other_row['active'] = False
            else:
                other_row['active'] = True
                other_row['status'] = 'active'
            licenses[other_lid] = other_row
    session_token = build_session_token(license_id, uid)

    user = _cleanup_sessions(dict(users.get(uid) or {}))
    user.setdefault('uid', uid)
    user.setdefault('name', str(row.get('client_name') or 'Kullanici'))
    user.setdefault('created', datetime.now().isoformat())
    user.setdefault('sessions', [])
    user.setdefault('seen_notice_ids', [])
    user.setdefault('delivered_notice_ids', [])
    user.setdefault('seen_personal_notice_ids', [])
    user.setdefault('delivered_personal_notice_ids', [])
    user['last_login'] = datetime.now().isoformat()
    user['license_id'] = license_id
    user['active_license_id'] = license_id
    user['language'] = language
    user['sessions'].append({
        'token': session_token,
        'license_id': license_id,
        'client_id': client_id,
        'script_hash': script_hash,
        'time': datetime.now().isoformat()
    })
    user['sessions'] = user['sessions'][-MAX_SESSIONS_PER_USER:]
    users[uid] = user
    save_users(users)

    row['uid'] = uid
    row['last_login'] = datetime.now().isoformat()
    row['last_heartbeat'] = datetime.now().isoformat()
    row['client_id'] = stored_client_id or client_id or ''
    row['script_hash'] = stored_hash or script_hash or ''
    row['language'] = language
    row['active'] = True
    row['status'] = 'active'
    row['sessions'] = [s for s in (row.get('sessions') or []) if isinstance(s, dict) and str((s or {}).get('time') or '').strip()]
    row.setdefault('sessions', [])
    row['sessions'].append({'token': session_token, 'uid': uid, 'time': datetime.now().isoformat()})
    row['sessions'] = row['sessions'][-MAX_SESSIONS_PER_USER:]
    licenses[license_id] = row
    save_licenses(licenses)

    patched_bot = patch_bot_content(load_bot_content())
    if not str(patched_bot or '').strip():
        return jsonify({'success': False, 'error': 'Bot bulunamadi'}), 503
    patched_bot = patched_bot.replace('__VIP_SCRIPT_CLIENT_ID__', stored_client_id or client_id or '')
    patched_bot = patched_bot.replace('__VIP_SCRIPT_HASH__', stored_hash or script_hash or '')
    patched_bot = patched_bot.replace('__VIP_SCRIPT_SESSION__', session_token)
    patched_bot = patched_bot.replace('__VIP_SCRIPT_UID__', uid)

    return jsonify({
        'success': True,
        'session_token': session_token,
        'license_id': license_id,
        'uid': uid,
        'identity': identity_label_text(uid),
        'language': row.get('language', 'tr'),
        'quick_links': load_quick_links(),
        'bot_code': encrypt_bot_for_uid(patched_bot, uid)
    })


@app.post('/api/heartbeat')
def api_heartbeat():
    data = request.get_json(silent=True) or {}
    uid = str(data.get('uid') or '').strip().lower()
    token = str(data.get('token') or '').strip()
    incoming_client_id = str(data.get('client_id') or '').strip()
    incoming_hash = str(data.get('script_hash') or '').strip()
    if not token or not uid:
        return jsonify({'success': False, 'error': 'Eksik heartbeat'}), 400
    if is_banned_uid(uid):
        return jsonify({'success': False, 'error': 'Script gecersiz Hata kodu (4003)'}), 403
    users = load_users()
    licenses = load_licenses()
    user = users.get(uid)
    if not user or not valid_session(user, token):
        return jsonify({'success': False, 'error': 'Oturum yok'}), 403
    license_id, session = resolve_session_license(user, token)
    row = dict(licenses.get(license_id, {}))
    if not row or not row.get('active', True) or str(row.get('status') or 'active').lower() != 'active':
        return jsonify({'success': False, 'error': 'off'}), 403
    if str(row.get('uid') or '').strip().lower() != uid:
        return jsonify({'success': False, 'error': 'invalid uid'}), 403
    expected_client_id = str((session or {}).get('client_id') or row.get('client_id') or '').strip()
    if expected_client_id and incoming_client_id and incoming_client_id != expected_client_id:
        return jsonify({'success': False, 'error': 'off'}), 403
    expected_hash = str((session or {}).get('script_hash') or row.get('script_hash') or '').strip()
    if expected_hash and incoming_hash and incoming_hash != expected_hash:
        return jsonify({'success': False, 'error': 'off'}), 403
    now_iso = datetime.now().isoformat()
    row['last_heartbeat'] = now_iso
    row['last_page'] = str(data.get('page') or '')
    licenses[license_id] = row
    save_licenses(licenses)
    user['last_heartbeat'] = now_iso
    user['active_license_id'] = license_id
    users[uid] = user
    save_users(users)
    return jsonify({'success': True})


@app.post('/api/client/command')
def api_client_command():
    data = request.get_json(silent=True) or {}
    uid = str(data.get('uid') or '').strip().lower()
    token = str(data.get('token') or '').strip()
    if is_banned_uid(uid):
        return jsonify({'success': False, 'error': 'Script gecersiz Hata kodu (4003)'}), 403
    users = load_users()
    user = users.get(uid)
    if not user or not valid_session(user, token):
        return jsonify({'success': False, 'error': 'Oturum yok'}), 403
    license_id, _ = resolve_session_license(user, token)
    return jsonify({'success': True, 'command': pop_client_command_for_license(license_id)})


@app.post('/api/telegram/register')
def api_telegram_register():
    data = request.get_json(silent=True) or {}
    uid = str(data.get('uid') or '').strip().lower()
    token = str(data.get('token') or '').strip()
    tg_token = str(data.get('telegram_token') or '').strip()
    tg_chat_id = str(data.get('telegram_chat_id') or '').strip()
    if is_banned_uid(uid):
        return jsonify({'success': False, 'error': 'Script gecersiz Hata kodu (4003)'}), 403
    users = load_users()
    licenses = load_licenses()
    user = users.get(uid)
    if not user or not valid_session(user, token):
        return jsonify({'success': False, 'error': 'Oturum yok'}), 403
    license_id, _ = resolve_session_license(user, token)
    row = dict(licenses.get(license_id, {}))
    if tg_token and tg_chat_id:
        ok, resp = send_telegram_api(tg_token, 'getMe', {})
        if not ok:
            return jsonify({'success': False, 'error': 'Telegram bot token gecersiz', 'detail': resp}), 400
    old_token = str(row.get('telegram_token') or '').strip()
    old_chat_id = str(row.get('telegram_chat_id') or '').strip()
    row['telegram_token'] = tg_token
    row['telegram_chat_id'] = tg_chat_id
    row['telegram_connected_at'] = datetime.now().isoformat()
    licenses[license_id] = row
    save_licenses(licenses)
    if tg_token and tg_chat_id and (tg_token != old_token or tg_chat_id != old_chat_id):
        send_license_telegram_menu(row, tg_text(row, 'telegram_connected'))
    return jsonify({'success': True})


@app.post('/api/telegram/screenshot')
def api_telegram_screenshot():
    data = request.get_json(silent=True) or {}
    uid = str(data.get('uid') or '').strip().lower()
    token = str(data.get('token') or '').strip()
    image = str(data.get('image') or '')
    if is_banned_uid(uid):
        return jsonify({'success': False, 'error': 'Script gecersiz Hata kodu (4003)'}), 403
    users = load_users()
    licenses = load_licenses()
    user = users.get(uid)
    if not user or not valid_session(user, token):
        return jsonify({'success': False, 'error': 'Oturum yok'}), 403
    license_id, _ = resolve_session_license(user, token)
    row = dict(licenses.get(license_id, {}))
    if ',' in image:
        image = image.split(',', 1)[1]
    try:
        photo_bytes = base64.b64decode(image)
    except Exception:
        return jsonify({'success': False, 'error': 'Goruntu bozuk'}), 400
    ok, resp = send_telegram_photo(str(row.get('telegram_token') or ''), str(row.get('telegram_chat_id') or ''), photo_bytes, tg_text(row, 'screenshot_caption'))
    if not ok:
        return jsonify({'success': False, 'error': 'Telegrama gonderilemedi', 'detail': resp}), 400
    return jsonify({'success': True})


@app.post('/encrypt')
def compat_encrypt():
    try:
        data = request.get_json(silent=True) or {}
        uid = str(data.get('uid') or data.get('user_id') or '').strip()
        if not uid:
            return jsonify({'success': False, 'error': 'uid gerekli'}), 400
        user_game_id = str(data.get('user_game_id') or '').strip()
        if not user_game_id:
            return jsonify({'success': False, 'error': 'user_game_id gerekli'}), 400
        payload = {
            'userGameId': int(user_game_id),
            'power': int(data.get('power') or 0),
            'winStatus': data.get('win_status', 3),
            'captchaToken': '',
            'operatingSystem': 'Windows',
            'possibleScriptedMovements': 0,
        }
        encrypted = encrypt_with_uid(payload, uid)
        return jsonify({'success': True, 'encrypted': encrypted, 'user_id': uid})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.post('/api/tasks/config')
def api_tasks_config():
    bot_auth, error = require_bot_identity(request)
    if error:
        return error
    tasks_config = load_tasks_config()
    license_id = bot_auth['license_id']
    row = dict((bot_auth.get('license') or {}))
    license_routes = dict(row.get('task_routes') or (tasks_config.get('licenses') or {}).get(license_id) or {})
    route_profile = merge_task_routes(tasks_config.get('routes') or {}, license_routes)
    return jsonify({
        'success': True,
        'uid': bot_auth['uid'],
        'license_id': license_id,
        'routes': route_profile,
        'source': 'license' if license_routes else 'global'
    })


@app.post('/api/tasks/analyze')
def api_tasks_analyze():
    bot_auth, error = require_bot_identity(request)
    if error:
        return error
    data = request.get_json(silent=True) or {}
    return jsonify({'success': True, 'analysis': data})


@app.post('/api/bot/plan')
def api_bot_plan():
    bot_auth, error = require_bot_identity(request)
    if error:
        return error
    data = request.get_json(silent=True) or {}
    available_games = [int(x) for x in (data.get('available_games') or []) if str(x).isdigit()]
    selected_games = [int(x) for x in (data.get('selected_games') or []) if str(x).isdigit()]
    planned_wait_seconds = 3 + (secrets.randbelow(13) if available_games else 0)
    next_game_id = None
    if available_games:
        preferred = [gid for gid in selected_games if gid in available_games]
        pool = preferred or available_games
        next_game_id = pool[secrets.randbelow(len(pool))]
    return jsonify({'success': True, 'plan': {'next_game_id': next_game_id, 'wait_seconds': planned_wait_seconds, 'should_win': True, 'reason': 'server_plan'}})


@app.post('/api/notice/next')
def api_notice_next():
    data = request.get_json(silent=True) or {}
    uid = str(data.get('uid') or '').strip().lower()
    token = str(data.get('token') or '').strip()
    if is_banned_uid(uid):
        return jsonify({'success': False, 'error': 'Script gecersiz Hata kodu (4003)'}), 403
    users = load_users()
    licenses = load_licenses()
    user = users.get(uid)
    if not user or not valid_session(user, token):
        return jsonify({'success': False, 'error': 'Oturum yok'}), 403
    license_id, _ = resolve_session_license(user, token)
    row = dict(licenses.get(license_id, {}))
    personal = (row.get('personal_notice') or {})
    if personal.get('id') and personal.get('text') and personal['id'] not in (user.get('seen_personal_notice_ids') or []) and personal['id'] not in (user.get('delivered_personal_notice_ids') or []):
        user.setdefault('delivered_personal_notice_ids', []).append(personal['id'])
        users[uid] = user
        save_users(users)
        row['message_status'] = 'Gonderildi'
        row['message_text'] = str(personal.get('text') or '').strip()
        licenses[license_id] = row
        save_licenses(licenses)
        return jsonify({'success': True, 'notice': personal})
    notice = load_notice()
    if not notice.get('id') or not notice.get('text'):
        return jsonify({'success': True, 'notice': None})
    if notice['id'] in (user.get('seen_notice_ids') or []) or notice['id'] in (user.get('delivered_notice_ids') or []):
        return jsonify({'success': True, 'notice': None})
    user.setdefault('delivered_notice_ids', []).append(notice['id'])
    users[uid] = user
    save_users(users)
    row['message_status'] = 'Gonderildi'
    row['message_text'] = str(notice.get('text') or '').strip()
    licenses[license_id] = row
    save_licenses(licenses)
    return jsonify({'success': True, 'notice': notice})


@app.post('/api/notice/ack')
def api_notice_ack():
    data = request.get_json(silent=True) or {}
    uid = str(data.get('uid') or '').strip().lower()
    token = str(data.get('token') or '').strip()
    notice_id = str(data.get('notice_id') or '').strip()
    if is_banned_uid(uid):
        return jsonify({'success': False, 'error': 'Script gecersiz Hata kodu (4003)'}), 403
    users = load_users()
    licenses = load_licenses()
    user = users.get(uid)
    if not user or not valid_session(user, token):
        return jsonify({'success': False, 'error': 'Oturum yok'}), 403
    license_id, _ = resolve_session_license(user, token)
    row = dict(licenses.get(license_id, {}))
    if notice_id:
        personal = dict((row or {}).get('personal_notice') or {})
        current_notice = load_notice()
        is_personal = notice_id and notice_id == str(personal.get('id') or '').strip()
        is_global = notice_id and notice_id == str((current_notice or {}).get('id') or '').strip()
        user.setdefault('seen_notice_ids', [])
        user.setdefault('seen_personal_notice_ids', [])
        if is_global and notice_id not in user['seen_notice_ids']:
            user['seen_notice_ids'].append(notice_id)
        if is_personal and notice_id not in user['seen_personal_notice_ids']:
            user['seen_personal_notice_ids'].append(notice_id)
        users[uid] = user
        save_users(users)
        if row:
            row['message_status'] = 'Okundu'
            licenses[license_id] = row
            save_licenses(licenses)
    return jsonify({'success': True})


@app.get('/admin/licenses')
def admin_licenses():
    if not check_admin(request):
        return jsonify({'success': False, 'error': 'yetkisiz'}), 403
    licenses = load_licenses()
    users = load_users()
    result = {}
    for lid, row in licenses.items():
        row = dict(row or {})
        linked_user = {}
        for _, user_row in users.items():
            user_row = dict(user_row or {})
            if str(user_row.get('active_license_id') or user_row.get('license_id') or '').strip() == str(lid):
                linked_user = user_row
                break
        if linked_user:
            if linked_user.get('last_heartbeat'):
                row['last_heartbeat'] = linked_user.get('last_heartbeat')
            if linked_user.get('uid'):
                row['uid'] = linked_user.get('uid')
            if linked_user.get('language'):
                row['language'] = linked_user.get('language')
        row['runtime_online'] = is_license_online(row)
        row['display_uid'] = str(row.get('uid') or '').strip() if row['runtime_online'] else ''
        row['uid_hash'] = uid_hash_text(row.get('uid')) if row.get('uid') else ''
        row.pop('sessions', None)
        row['row_tag'] = 'online' if row['runtime_online'] else ('banned' if str(row.get('status') or '').strip().lower() == 'banned' else ('passive' if not row.get('active', True) else 'active'))
        row['status_text'] = 'Online' if row['runtime_online'] else ('Banned' if str(row.get('status') or '').strip().lower() == 'banned' else ('Off' if not row.get('active', True) else 'Bekliyor'))
        result[lid] = row
    return jsonify({'success': True, 'licenses': result})


@app.get('/admin/users')
def admin_users():
    if not check_admin(request):
        return jsonify({'success': False, 'error': 'yetkisiz'}), 403
    users = load_users()
    sanitized = {}
    for uid, row in users.items():
        row = dict(row or {})
        row.pop('sessions', None)
        sanitized[uid] = row
    return jsonify({'success': True, 'users': sanitized})


@app.post('/admin/license/create')
def admin_license_create():
    if not check_admin(request):
        return jsonify({'success': False, 'error': 'yetkisiz'}), 403
    data = request.get_json(silent=True) or {}
    license_id = 'SFL-' + secrets.token_hex(8).upper()
    payload = {
        'license_id': license_id,
        'client_name': str(data.get('client_name') or '').strip(),
        'client_id': str(data.get('client_id') or '').strip(),
        'script_hash': str(data.get('script_hash') or '').strip(),
        'issued_at': datetime.now().isoformat()
    }
    encrypted_license = encrypt_license_for_server(payload)
    licenses = load_licenses()
    row = {
        'license_id': license_id,
        'client_name': str(data.get('client_name') or '').strip(),
        'client_id': str(data.get('client_id') or '').strip(),
        'encrypted_license': encrypted_license,
        'script_hash': str(data.get('script_hash') or '').strip(),
        'script_file': str(data.get('script_file') or '').strip(),
        'uid': '',
        'active': str(data.get('status') or 'active').strip() == 'active',
        'status': str(data.get('status') or 'active').strip() or 'active',
        'uid_mode': str(data.get('uid_mode') or 'replace').strip() or 'replace',
        'allow_uid_change': str(data.get('uid_mode') or 'replace').strip() != 'fixed',
        'language': str(data.get('language') or 'tr').strip() or 'tr',
        'created_at': datetime.now().isoformat(),
        'last_heartbeat': '',
        'message_status': '',
        'message_text': '',
        'telegram_token': '',
        'telegram_chat_id': '',
        'sessions': []
    }
    licenses[license_id] = row
    save_licenses(licenses)
    return jsonify({'success': True, 'license_id': license_id, 'encrypted_license': encrypted_license, 'license': row})


@app.get('/admin/tasks/config')
def admin_tasks_config_get():
    if not check_admin(request):
        return jsonify({'success': False, 'error': 'yetkisiz'}), 403
    return jsonify({'success': True, 'config': load_tasks_config()})


@app.post('/admin/tasks/config')
def admin_tasks_config_set():
    if not check_admin(request):
        return jsonify({'success': False, 'error': 'yetkisiz'}), 403
    data = request.get_json(silent=True) or {}
    config = load_tasks_config()
    global_routes = dict(config.get('routes') or {})
    incoming_routes = dict(data.get('routes') or {})
    for key in ['games_page', 'preview_page', 'status_page', 'claim_pattern']:
        if key in incoming_routes:
            value = str(incoming_routes.get(key) or '').strip()
            if value:
                global_routes[key] = value
    license_id = str(data.get('license_id') or '').strip()
    if license_id:
        config.setdefault('licenses', {})
        config['licenses'][license_id] = merge_task_routes({}, dict(data.get('license_routes') or {}))
        licenses = load_licenses()
        row = dict(licenses.get(license_id, {}))
        if row:
            row['task_routes'] = dict(config['licenses'][license_id])
            licenses[license_id] = row
            save_licenses(licenses)
    config['routes'] = merge_task_routes(global_routes, {})
    save_tasks_config(config)
    return jsonify({'success': True, 'config': config})


@app.post('/admin/notice')
def admin_notice():
    if not check_admin(request):
        return jsonify({'success': False, 'error': 'yetkisiz'}), 403
    data = request.get_json(silent=True) or {}
    notice = {
        'id': str(data.get('id') or secrets.token_hex(8)),
        'text': str(data.get('text') or '').strip(),
        'created_at': str(data.get('created_at') or datetime.now().isoformat()),
        'links': dict(data.get('links') or {}),
        'links_active': bool(data.get('links_active', True))
    }
    save_notice(notice)
    licenses = load_licenses()
    for lid, row in list(licenses.items()):
        row = dict(row or {})
        row['message_status'] = 'Gonderildi'
        row['message_text'] = str(notice.get('text') or '').strip()
        licenses[lid] = row
    save_licenses(licenses)
    return jsonify({'success': True, 'notice': notice})


@app.post('/admin/notice/user')
def admin_notice_user():
    if not check_admin(request):
        return jsonify({'success': False, 'error': 'yetkisiz'}), 403
    data = request.get_json(silent=True) or {}
    license_id = str(data.get('license_id') or '').strip()
    text = str(data.get('text') or '').strip()
    if not license_id or not text:
        return jsonify({'success': False, 'error': 'eksik alan'}), 400
    licenses = load_licenses()
    row = dict(licenses.get(license_id, {}))
    if not row:
        return jsonify({'success': False, 'error': 'lisans yok'}), 404
    row['personal_notice'] = {
        'id': secrets.token_hex(8),
        'text': text,
        'created_at': datetime.now().isoformat(),
        'links': dict(data.get('links') or {}),
        'links_active': bool(data.get('links_active', True))
    }
    row['message_status'] = 'Gonderildi'
    row['message_text'] = text
    licenses[license_id] = row
    save_licenses(licenses)
    return jsonify({'success': True})


@app.post('/admin/bot')
def admin_bot():
    if not check_admin(request):
        return jsonify({'success': False, 'error': 'yetkisiz'}), 403
    data = request.get_json(silent=True) or {}
    content = str(data.get('content') or '')
    save_bot_content(content)
    return jsonify({'success': True})


@app.post('/admin/sync-all')
def admin_sync_all():
    if not check_admin(request):
        return jsonify({'success': False, 'error': 'yetkisiz'}), 403
    data = request.get_json(silent=True) or {}
    incoming_licenses = data.get('licenses') or {}
    incoming_users = data.get('users') or {}
    if isinstance(incoming_licenses, dict):
        current = load_licenses()
        for lid, row in incoming_licenses.items():
            base = dict(current.get(lid, {}))
            base.update(dict(row or {}))
            current[lid] = base
        save_licenses(current)
    if isinstance(incoming_users, dict):
        current_users = load_users()
        for uid, row in incoming_users.items():
            base = dict(current_users.get(uid, {}))
            base.update(dict(row or {}))
            current_users[uid] = base
        save_users(current_users)
    if isinstance(data.get('notice'), dict):
        save_notice(data.get('notice'))
    if isinstance(data.get('quick_links'), dict):
        save_quick_links(data.get('quick_links'))
    if 'bot_content' in data:
        save_bot_content(str(data.get('bot_content') or ''))
    return jsonify({'success': True})


@app.post('/admin/license/state')
def admin_license_state():
    if not check_admin(request):
        return jsonify({'success': False, 'error': 'yetkisiz'}), 403
    data = request.get_json(silent=True) or {}
    license_id = str(data.get('license_id') or '').strip()
    active = bool(data.get('active', True))
    licenses = load_licenses()
    row = dict(licenses.get(license_id, {}))
    if not row:
        return jsonify({'success': False, 'error': 'lisans yok'}), 404
    row['active'] = active
    row['status'] = 'active' if active else 'passive'
    licenses[license_id] = row
    save_licenses(licenses)
    return jsonify({'success': True})


@app.post('/admin/license/uid-mode')
def admin_license_uid_mode():
    if not check_admin(request):
        return jsonify({'success': False, 'error': 'yetkisiz'}), 403
    data = request.get_json(silent=True) or {}
    license_id = str(data.get('license_id') or '').strip()
    uid_mode = str(data.get('uid_mode') or 'replace').strip() or 'replace'
    licenses = load_licenses()
    row = dict(licenses.get(license_id, {}))
    if not row:
        return jsonify({'success': False, 'error': 'lisans yok'}), 404
    row['uid_mode'] = uid_mode
    row['allow_uid_change'] = uid_mode != 'fixed'
    licenses[license_id] = row
    save_licenses(licenses)
    return jsonify({'success': True})


@app.post('/admin/license/delete')
def admin_license_delete():
    if not check_admin(request):
        return jsonify({'success': False, 'error': 'yetkisiz'}), 403
    data = request.get_json(silent=True) or {}
    license_id = str(data.get('license_id') or '').strip()
    licenses = load_licenses()
    row = dict(licenses.get(license_id, {}))
    uid = str(row.get('uid') or '').strip().lower()
    revoked = load_revoked_licenses()
    if row:
        revoked.append({
            'license_id': license_id,
            'encrypted_license': str(row.get('encrypted_license') or '').strip(),
            'client_id': str(row.get('client_id') or '').strip(),
            'script_hash': str(row.get('script_hash') or '').strip(),
            'deleted_at': datetime.now().isoformat(),
            'reason': 'admin_delete'
        })
        save_revoked_licenses(revoked)
    if license_id in licenses:
        del licenses[license_id]
        save_licenses(licenses)
    if uid:
        users = load_users()
        users.pop(uid, None)
        save_users(users)
    return jsonify({'success': True, 'revoked': True})


@app.get('/admin/banned-uids')
def admin_banned_uids():
    if not check_admin(request):
        return jsonify({'success': False, 'error': 'yetkisiz'}), 403
    return jsonify({'success': True, 'items': load_banned_uids()})


@app.post('/admin/uid/ban')
def admin_uid_ban():
    if not check_admin(request):
        return jsonify({'success': False, 'error': 'yetkisiz'}), 403
    data = request.get_json(silent=True) or {}
    uid = str(data.get('uid') or '').strip().lower()
    if not uid:
        return jsonify({'success': False, 'error': 'uid gerekli'}), 400
    banned = load_banned_uids()
    licenses = load_licenses()
    users = load_users()
    matched_license_id = ''
    client_name = ''
    for lid, row in list(licenses.items()):
        row = dict(row or {})
        if str(row.get('uid') or '').strip().lower() == uid:
            row['active'] = False
            row['status'] = 'banned'
            row['last_heartbeat'] = ''
            row['sessions'] = []
            licenses[lid] = row
            matched_license_id = lid
            client_name = str(row.get('client_name') or '').strip()
    if uid in users:
        user = dict(users.get(uid) or {})
        user['status'] = 'banned'
        user['sessions'] = []
        user['active_license_id'] = ''
        users[uid] = user
        save_users(users)
    save_licenses(licenses)
    banned[uid] = {
        'uid': uid,
        'status': 'banned',
        'reason': str(data.get('reason') or 'admin').strip(),
        'created_at': datetime.now().isoformat(),
        'license_id': matched_license_id,
        'client_name': client_name,
    }
    save_banned_uids(banned)
    return jsonify({'success': True, 'uid': uid})


@app.post('/admin/uid/unban')
def admin_uid_unban():
    if not check_admin(request):
        return jsonify({'success': False, 'error': 'yetkisiz'}), 403
    data = request.get_json(silent=True) or {}
    uid = str(data.get('uid') or '').strip().lower()
    if not uid:
        return jsonify({'success': False, 'error': 'uid gerekli'}), 400
    banned = load_banned_uids()
    banned.pop(uid, None)
    save_banned_uids(banned)
    users = load_users()
    if uid in users:
        user = dict(users.get(uid) or {})
        if str(user.get('status') or '').strip().lower() == 'banned':
            user['status'] = 'active'
        users[uid] = user
        save_users(users)
    licenses = load_licenses()
    for lid, row in list(licenses.items()):
        row = dict(row or {})
        if str(row.get('uid') or '').strip().lower() == uid and str(row.get('status') or '').strip().lower() == 'banned':
            row['active'] = True
            row['status'] = 'active'
            row['last_heartbeat'] = ''
            row['sessions'] = []
            licenses[lid] = row
    save_licenses(licenses)
    return jsonify({'success': True, 'uid': uid})


@app.post('/admin/client-command')
def admin_client_command():
    if not check_admin(request):
        return jsonify({'success': False, 'error': 'yetkisiz'}), 403
    data = request.get_json(silent=True) or {}
    queue_client_command(data.get('command'), data.get('license_id'))
    return jsonify({'success': True})


@app.post('/check_command')
def compat_check_command_post():
    return api_check_command()


@app.get('/check_command')
def compat_check_command_get():
    return api_check_command()


def api_check_command():
    bot_auth, error = require_bot_identity(request)
    if error:
        return error
    uid = bot_auth['uid']
    license_id = bot_auth['license_id']
    command = pop_bot_command(license_id, uid)
    if command:
        return jsonify({'command': command.get('command') or 'wait'})
    if last_bot_status.get('level_missing'):
        return jsonify({'command': 'reload_levels'})
    return jsonify({'command': 'wait'})


@app.post('/captcha_alert')
def compat_captcha_alert():
    bot_auth, error = require_bot_identity(request)
    if error:
        return error
    data = request.get_json(silent=True) or {}
    last_bot_status['captcha_waiting'] = True
    last_bot_status['captcha_game_id'] = data.get('game_id')
    row = dict(bot_auth.get('license') or {})
    if row and str(row.get('telegram_token') or '').strip() and str(row.get('telegram_chat_id') or '').strip():
        send_captcha_telegram_menu(row, data.get('game_id'))
    return jsonify({'success': True, 'license_id': bot_auth['license_id']})


@app.post('/level_missing')
def compat_level_missing():
    bot_auth, error = require_bot_identity(request)
    if error:
        return error
    data = request.get_json(silent=True) or {}
    last_bot_status['level_missing'] = True
    last_bot_status['missing_level_info'] = data
    row = dict(bot_auth.get('license') or {})
    if row and str(row.get('telegram_token') or '').strip() and str(row.get('telegram_chat_id') or '').strip():
        send_license_telegram_menu(row, tg_text(row, 'level_missing', game=data.get('game_id'), level=data.get('level')))
    return jsonify({'success': True, 'license_id': bot_auth['license_id']})


@app.route('/bot/status', methods=['GET', 'POST'])
def compat_bot_status():
    bot_auth, error = require_bot_identity(request)
    if error:
        return error
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        last_bot_status.update({
            'updated_at': datetime.now().isoformat(),
            'uid': bot_auth['uid'],
            'license_id': bot_auth['license_id'],
            'status_text': str(data.get('status_text') or last_bot_status.get('status_text') or 'Ready'),
            'captcha_waiting': bool(data.get('captcha_waiting', last_bot_status.get('captcha_waiting', False))),
            'captcha_game_id': data.get('current_game') if data.get('captcha_waiting') else last_bot_status.get('captcha_game_id'),
            'ready_games_count': int(data.get('ready_games_count', last_bot_status.get('ready_games_count', 0)) or 0),
            'total_loaded_games': int(data.get('total_loaded_games', last_bot_status.get('total_loaded_games', 0)) or 0),
            'total_played_games': int(data.get('total_played_games', last_bot_status.get('total_played_games', 0)) or 0),
            'total_power': int(data.get('total_power', last_bot_status.get('total_power', 0)) or 0),
            'history_count': int(data.get('history_count', last_bot_status.get('history_count', 0)) or 0),
        })
        return jsonify({'success': True, 'status': last_bot_status})
    return jsonify({'success': True, 'status': last_bot_status})


@app.post('/bot/command')
def compat_bot_command():
    bot_auth, error = require_bot_identity(request)
    if error:
        return error
    data = request.get_json(silent=True) or {}
    command = str(data.get('command') or '').strip().lower()
    queue_client_command(command, bot_auth['license_id'])
    return jsonify({'success': True, 'license_id': bot_auth['license_id']})


if __name__ == '__main__':
    log_event(f'sunflower server started on {HOST}:{PORT}')
    threading.Thread(target=poll_all_telegram_bots, daemon=True).start()
    app.run(host=HOST, port=PORT, debug=False)
