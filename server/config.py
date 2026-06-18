import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = BASE_DIR / 'workspace'
WORKSPACE_DIR.mkdir(exist_ok=True)

HOST = os.environ.get('HOST', '0.0.0.0')
PORT = int(os.environ.get('PORT', '10000'))
ADMIN_TOKEN = os.environ.get('ADMIN_TOKEN', '').strip()
SERVER_LICENSE_SECRET = os.environ.get('SERVER_LICENSE_SECRET', '').strip()
SUPABASE_URL = os.environ.get('SUPABASE_URL', '').rstrip('/')
SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_KEY', '').strip()
D1_STATE_API_URL = os.environ.get('D1_STATE_API_URL', '').rstrip('/')
D1_STATE_API_TOKEN = os.environ.get('D1_STATE_API_TOKEN', '').strip()
ALLOWED_ORIGINS = os.environ.get('ALLOWED_ORIGINS', '*')
ADMIN_ALLOWED_IPS = tuple(ip.strip() for ip in os.environ.get('ADMIN_ALLOWED_IPS', '').split(',') if ip.strip())
SESSION_TTL_SECONDS = int(os.environ.get('SESSION_TTL_SECONDS', '21600'))
ADMIN_RATE_LIMIT_PER_MIN = int(os.environ.get('ADMIN_RATE_LIMIT_PER_MIN', '120'))
AUTH_RATE_LIMIT_PER_MIN = int(os.environ.get('AUTH_RATE_LIMIT_PER_MIN', '240'))

USERS_FILE = WORKSPACE_DIR / 'users.json'
LICENSES_FILE = WORKSPACE_DIR / 'licenses.json'
NOTICE_FILE = WORKSPACE_DIR / 'notice.json'
LOGS_FILE = WORKSPACE_DIR / 'server_logs.txt'
BOT_FILE = WORKSPACE_DIR / 'bot.txt'
REVOKED_LICENSES_FILE = WORKSPACE_DIR / 'revoked_licenses.json'
QUICK_LINKS_FILE = WORKSPACE_DIR / 'quick_links.json'
TASKS_CONFIG_FILE = WORKSPACE_DIR / 'tasks_config.json'
BANNED_UIDS_FILE = WORKSPACE_DIR / 'banned_uids.json'

for path, default in (
    (USERS_FILE, '{}'),
    (LICENSES_FILE, '{}'),
    (NOTICE_FILE, '{"id":"","text":"","created_at":"","links":{},"links_active":false}'),
    (LOGS_FILE, ''),
    (BOT_FILE, ''),
    (REVOKED_LICENSES_FILE, '[]'),
    (QUICK_LINKS_FILE, '{"active": false, "telegram": "", "youtube": "", "login": "", "normal": "", "show_key_telegram": false}'),
    (TASKS_CONFIG_FILE, '{}'),
    (BANNED_UIDS_FILE, '[]')
):
    if not path.exists():
        path.write_text(default, encoding='utf-8')
