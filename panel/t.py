#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import base64
import hashlib
import json
import secrets
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import ttk, messagebox, filedialog, scrolledtext
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent
SETTINGS_FILE = BASE_DIR / 'panel_settings.json'
SECRETS_FILE = BASE_DIR / 'panel_secrets.local.json'
GENERATED_DIR = BASE_DIR / 'generated_scripts'
GENERATED_DIR.mkdir(exist_ok=True)

DEFAULT_SETTINGS = {
    'server_url': 'https://sunflower-panel-server-ufpg.onrender.com',
    'selected_bot_path': 'C:/Users/User/Desktop/Yeni klasör (7)/bot.txt',
    'selected_bot_name': 'bot.txt'
}

DEFAULT_SECRETS = {
    'admin_token': 'sunflower_admin_2026_super_secure_91x'
}

CLIENT_TEMPLATE = r'''// ==UserScript==
// @name         __CLIENT_NAME__
// @match        https://sunflower-land.com/*
// @grant        GM_xmlhttpRequest
// @grant        GM_setValue
// @grant        GM_getValue
// @grant        GM_addStyle
// @grant        unsafeWindow
// @connect      __SERVER_HOST__
// @require      https://html2canvas.hertzen.com/dist/html2canvas.min.js
// @run-at       document-start
// ==/UserScript==

(function() {
    'use strict';

    const __edgeRoute = 'https://cdn-sunflower-static.example/assets';
    const __fallbackPing = 'https://status-sunflower.example/ping';
    const __assetMirror = ['https://mirror-sunflower.example/a', 'https://mirror-sunflower.example/b'];
    const __routeHints = { cdn: __edgeRoute, ping: __fallbackPing, mirrors: __assetMirror };
    const _mixBag = (bag, keyText) => {
        const src = bag && typeof bag === 'object' ? bag : {};
        const names = String(src.k || '').split('|').filter(Boolean);
        let order = [];
        try { order = JSON.parse(atob(String(src.o || 'W10='))); } catch(e) { order = []; }
        const seed = String(keyText || '').split('').reduce((n, ch, idx) => n + ch.charCodeAt(0) + idx, 0) || 17;
        return order.map((slot) => {
            const row = src[names[slot]] || {};
            let text = '';
            try { text = atob(String(row.q || '')); } catch(e) { text = ''; }
            if (((parseInt(row.m || 0, 10) ^ seed) & 1) === 1) text = text.split('').reverse().join('');
            return text;
        }).join('');
    };
    const SERVER_URL = _mixBag({ __SERVER_URL_PACK__ }, __SERVER_URL_HINT__);
    const CLIENT_NAME = _mixBag({ __CLIENT_NAME_PACK__ }, __CLIENT_NAME_HINT__);
    const CLIENT_ID = _mixBag({ __CLIENT_ID_PACK__ }, __CLIENT_ID_HINT__);
    const SCRIPT_HASH = _mixBag({ __SCRIPT_HASH_PACK__ }, __SCRIPT_HASH_HINT__);
    const STORAGE_KEY = 'sunflower_vip_auth_' + btoa(CLIENT_ID).slice(0, 18);
    const TG_KEY = STORAGE_KEY + '_tg';
    const NOTICE_KEY = STORAGE_KEY + '_notice_seen';
    const BOT_CACHE_KEY = STORAGE_KEY + '_bot_cache';
    const PAGE_LOCK_KEY = '__NEXUS_SUNFLOWER_PAGE_LOCK__';

    let sessionToken = null;
    let extractedUID = null;
    let selectedLanguage = __LANG__;
    let helperStarted = false;

    const I18N = {
        tr: {
            title:'SUNFLOWER VIP GIRIS', subtitle:'Devam etmek icin lisans key gir.', login:'GIRIS', wait:'BEKLE', needKey:'Lisans key gir', uidMissing:'Kullanici adi bulunamadi. Sunflower oturumu acik olmali.', authWait:'Sunucuya baglaniliyor...', authOk:'Giris basarili', authFail:'Giris basarisiz', tgTitle:'TELEGRAM BAGLANTI', tgSave:'KAYDET', tgSkip:'ATLA', tgNeed:'Token ve chat id gerekli', tgOk:'Telegram baglandi', notice:'Mesaj Merkezi', keyHelp:'LUTFEN YONETICIDEN KEY TALEP EDINIZ'
        },
        en: {
            title:'SUNFLOWER VIP LOGIN', subtitle:'Enter license key to continue.', login:'LOGIN', wait:'WAIT', needKey:'Enter license key', uidMissing:'Username not found. Sunflower session must be open.', authWait:'Connecting server...', authOk:'Login successful', authFail:'Login failed', tgTitle:'TELEGRAM CONNECT', tgSave:'SAVE', tgSkip:'SKIP', tgNeed:'Token and chat id required', tgOk:'Telegram connected', notice:'Message Center', keyHelp:'PLEASE REQUEST A KEY FROM THE ADMIN'
        }
    };

    function t(key) {
        return (I18N[selectedLanguage] && I18N[selectedLanguage][key]) || (I18N.tr[key]) || key;
    }

    function gmRequest(method, url, body) {
        return new Promise((resolve) => {
            GM_xmlhttpRequest({
                method,
                url,
                headers: { 'Content-Type': 'application/json' },
                data: body ? JSON.stringify(body) : undefined,
                onload: (res) => { try { resolve(JSON.parse(res.responseText || '{}')); } catch(e) { resolve({ success:false, error:'Bozuk yanit' }); } },
                onerror: () => resolve({ success:false, error:'Baglanti hatasi' }),
                ontimeout: () => resolve({ success:false, error:'Zaman asimi' })
            });
        });
    }

    function saveLocal(key, value) {
        try { localStorage.setItem(key, value); } catch(e) {}
        try { if (typeof GM_setValue === 'function') GM_setValue(key, value); } catch(e) {}
    }
    function loadLocal(key) {
        try { const raw = localStorage.getItem(key); if (raw) return raw; } catch(e) {}
        try { if (typeof GM_getValue === 'function') { const raw = GM_getValue(key); if (raw) return raw; } } catch(e) {}
        return '';
    }
    function saveAuthState(payload) { saveLocal(STORAGE_KEY, JSON.stringify(payload || {})); }
    function loadAuthState() { try { const raw = loadLocal(STORAGE_KEY); return raw ? JSON.parse(raw) : null; } catch(e) { return null; } }
    function clearAuthState() { try { localStorage.removeItem(STORAGE_KEY); } catch(e) {} try { if (typeof GM_setValue === 'function') GM_setValue(STORAGE_KEY, ''); } catch(e) {} }
    function saveBotCache(code) { saveLocal(BOT_CACHE_KEY, String(code || '')); }
    function loadBotCache() { return String(loadLocal(BOT_CACHE_KEY) || ''); }
    function clearBotCache() { try { localStorage.removeItem(BOT_CACHE_KEY); } catch(e) {} try { if (typeof GM_setValue === 'function') GM_setValue(BOT_CACHE_KEY, ''); } catch(e) {} }
    function saveTelegram(token, chatId) { saveLocal(TG_KEY, JSON.stringify({ token:String(token||'').trim(), chatId:String(chatId||'').trim() })); }
    function loadTelegram() { try { const raw = loadLocal(TG_KEY); return raw ? JSON.parse(raw) : { token:'', chatId:'' }; } catch(e) { return { token:'', chatId:'' }; } }
    function getSeenNoticeIds() { try { const raw = localStorage.getItem(NOTICE_KEY); const arr = raw ? JSON.parse(raw) : []; return Array.isArray(arr) ? arr : []; } catch(e) { return []; } }
    function markNoticeSeen(id) { if (!id) return; try { const arr = getSeenNoticeIds(); if (!arr.includes(id)) arr.push(id); localStorage.setItem(NOTICE_KEY, JSON.stringify(arr.slice(-50))); } catch(e) {} }

    function simpleHash(text) {
        let h = 0;
        const src = String(text || '');
        for (let i = 0; i < src.length; i++) { h = ((h << 5) - h) + src.charCodeAt(i); h |= 0; }
        return 'h' + Math.abs(h).toString(16);
    }

    function extractUID() {
        const candidates = [];
        const pushName = (value) => {
            const text = String(value || '').trim();
            if (!text) return;
            if (text.length < 2 || text.length > 60) return;
            if (!candidates.includes(text)) candidates.push(text);
        };
        const readText = (selector) => {
            try {
                const el = document.querySelector(selector);
                if (el) pushName(el.textContent || '');
            } catch(e) {}
        };
        [
            '[data-testid="username"]',
            '.username',
            '.player-name',
            '.profile-name',
            '.playerName',
            'h1'
        ].forEach(readText);
        try {
            const text = document.body ? document.body.innerText : '';
            const m = text.match(/Farm\s+ID\s*:?\s*([A-Za-z0-9_.-]{2,60})/i);
            if (m) pushName(m[1]);
        } catch(e) {}
        const keys = ['username', 'user_name', 'nickname', 'name', 'farm_name', 'sunflower_username', 'player_name'];
        for (const key of keys) {
            try { pushName(localStorage.getItem(key)); } catch(e) {}
            try { pushName(sessionStorage.getItem(key)); } catch(e) {}
        }
        try {
            const maybeValues = [unsafeWindow?.user?.username, unsafeWindow?.user?.name, unsafeWindow?.USER?.username, unsafeWindow?.USER?.name, unsafeWindow?.username, unsafeWindow?.accountName, unsafeWindow?.farmId, unsafeWindow?.gameState?.farmId, unsafeWindow?.state?.farmId];
            maybeValues.forEach(pushName);
        } catch(e) {}
        try {
            const cookieMatch = document.cookie.match(/(?:^|;\s*)(?:username|user_name|nickname)=([^;]+)/i);
            if (cookieMatch) pushName(decodeURIComponent(cookieMatch[1] || ''));
        } catch(e) {}
        return candidates.find(Boolean) || '';
    }

    function decodeBotCode(encoded, uid) {
        const raw = atob(String(encoded || ''));
        const key = String(uid || '');
        const bytes = new Uint8Array(raw.length);
        for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i) ^ key.charCodeAt(i % key.length);
        try {
            return new TextDecoder('utf-8').decode(bytes);
        } catch(e) {
            let out = '';
            for (let i = 0; i < bytes.length; i++) out += String.fromCharCode(bytes[i]);
            return out;
        }
    }

    function normalizeQuickLinks(links) {
        const src = links && typeof links === 'object' ? links : {};
        const telegram = String(src.telegram || '').trim();
        const youtube = String(src.youtube || '').trim();
        const normal = String(src.normal || '').trim();
        return {
            active: !!(src.active || telegram || youtube || normal || src.login_telegram || src.key_telegram || src.telegram_screen_telegram),
            telegram, youtube, login: String(src.login || '').trim(), normal,
            error_link: String(src.error_link || '').trim(),
            show_key_telegram: !!src.show_key_telegram,
            key_warning_text: String(src.key_warning_text || '').trim(),
            login_telegram: String(src.login_telegram || telegram || '').trim(),
            login_youtube: String(src.login_youtube || youtube || '').trim(),
            login_normal: String(src.login_normal || normal || '').trim(),
            login_telegram_enabled: src.login_telegram_enabled !== undefined ? !!src.login_telegram_enabled : !!String(src.login_telegram || telegram || '').trim(),
            login_youtube_enabled: src.login_youtube_enabled !== undefined ? !!src.login_youtube_enabled : !!String(src.login_youtube || youtube || '').trim(),
            login_normal_enabled: src.login_normal_enabled !== undefined ? !!src.login_normal_enabled : !!String(src.login_normal || normal || '').trim(),
            key_telegram: String(src.key_telegram || telegram || '').trim(),
            key_youtube: String(src.key_youtube || youtube || '').trim(),
            key_normal: String(src.key_normal || normal || '').trim(),
            key_telegram_enabled: src.key_telegram_enabled !== undefined ? !!src.key_telegram_enabled : !!String(src.key_telegram || telegram || '').trim(),
            key_youtube_enabled: src.key_youtube_enabled !== undefined ? !!src.key_youtube_enabled : !!String(src.key_youtube || youtube || '').trim(),
            key_normal_enabled: src.key_normal_enabled !== undefined ? !!src.key_normal_enabled : !!String(src.key_normal || normal || '').trim(),
            key_error_link: String(src.key_error_link || src.error_link || normal || telegram || '').trim(),
            telegram_screen_telegram: String(src.telegram_screen_telegram || telegram || '').trim(),
            telegram_screen_youtube: String(src.telegram_screen_youtube || youtube || '').trim(),
            telegram_screen_normal: String(src.telegram_screen_normal || normal || '').trim(),
            telegram_screen_telegram_enabled: src.telegram_screen_telegram_enabled !== undefined ? !!src.telegram_screen_telegram_enabled : !!String(src.telegram_screen_telegram || telegram || '').trim(),
            telegram_screen_youtube_enabled: src.telegram_screen_youtube_enabled !== undefined ? !!src.telegram_screen_youtube_enabled : !!String(src.telegram_screen_youtube || youtube || '').trim(),
            telegram_screen_normal_enabled: src.telegram_screen_normal_enabled !== undefined ? !!src.telegram_screen_normal_enabled : !!String(src.telegram_screen_normal || normal || '').trim(),
        };
    }

    function getScreenLinks(links, screenName) {
        const data = normalizeQuickLinks(links);
        const key = String(screenName || 'login').trim().toLowerCase();
        if (key === 'key') {
            return { telegram: data.key_telegram_enabled ? data.key_telegram : '', youtube: data.key_youtube_enabled ? data.key_youtube : '', normal: data.key_normal_enabled ? data.key_normal : '', error_link: data.key_error_link, warning_text: data.key_warning_text || t('keyHelp'), show_key_telegram: data.show_key_telegram, active: !!((data.key_telegram_enabled && data.key_telegram) || (data.key_youtube_enabled && data.key_youtube) || (data.key_normal_enabled && data.key_normal)) };
        }
        if (key === 'telegram') {
            return { telegram: data.telegram_screen_telegram_enabled ? data.telegram_screen_telegram : '', youtube: data.telegram_screen_youtube_enabled ? data.telegram_screen_youtube : '', normal: data.telegram_screen_normal_enabled ? data.telegram_screen_normal : '', error_link: data.telegram_screen_normal, warning_text: '', show_key_telegram: false, active: !!((data.telegram_screen_telegram_enabled && data.telegram_screen_telegram) || (data.telegram_screen_youtube_enabled && data.telegram_screen_youtube) || (data.telegram_screen_normal_enabled && data.telegram_screen_normal)) };
        }
        return { telegram: data.login_telegram_enabled ? data.login_telegram : '', youtube: data.login_youtube_enabled ? data.login_youtube : '', normal: data.login_normal_enabled ? data.login_normal : '', error_link: data.login_normal, warning_text: '', show_key_telegram: false, active: !!((data.login_telegram_enabled && data.login_telegram) || (data.login_youtube_enabled && data.login_youtube) || (data.login_normal_enabled && data.login_normal)) };
    }

    function quickLinksHtml(links, compact, forceShow, screenName) {
        const data = getScreenLinks(links, screenName);
        const currentScreen = String(screenName || 'login').trim().toLowerCase();
        const hasAny = !!(data.telegram || data.youtube || data.normal);
        if (((!data.active && !forceShow) || !hasAny)) return '';
        const iconStyle = compact ? 'width:38px;height:38px;object-fit:contain;display:block;filter:drop-shadow(0 2px 6px rgba(0,0,0,.25));' : 'width:24px;height:24px;object-fit:contain;display:block;filter:drop-shadow(0 2px 4px rgba(0,0,0,.22));';
        const iconBtn = (label, url, tone, extraId) => url ? `<a ${extraId || ''} href="${String(url).replace(/"/g, '&quot;')}" target="_blank" rel="noopener noreferrer" style="text-decoration:none;display:inline-flex;align-items:center;justify-content:center;width:${compact ? '58px' : '42px'};height:${compact ? '58px' : '42px'};background:transparent;border:1px solid ${tone};border-radius:${compact ? '16px' : '14px'};box-shadow:none;">${label}</a>` : '';
        const textBtn = (url) => url ? `<a href="${String(url).replace(/"/g, '&quot;')}" target="_blank" rel="noopener noreferrer" style="text-decoration:none;display:inline-flex;align-items:center;justify-content:center;padding:${compact ? '12px 16px' : '10px 14px'};background:linear-gradient(135deg,#0ea5e9,#2563eb);color:#fff;border-radius:16px;font-size:${compact ? '14px' : '12px'};font-weight:900;box-shadow:0 10px 24px rgba(0,0,0,.20);">Tikla</a>` : '';
        const telegramId = (currentScreen === 'key' && data.show_key_telegram && data.telegram) ? 'id="sunflower-key-telegram-link"' : '';
        const items = [iconBtn(`<img src="https://web.telegram.org/a/favicon.ico" alt="Telegram" style="${iconStyle}">`, data.telegram, 'rgba(34,197,94,.55)', telegramId), iconBtn(`<img src="https://www.gstatic.com/youtube/img/branding/favicon/favicon_144x144_v2.png" alt="YouTube" style="${iconStyle}">`, data.youtube, 'rgba(239,68,68,.55)'), textBtn(data.normal)].filter(Boolean);
        if (!items.length) return '';
        return `<div style="display:flex;gap:${compact ? '10px' : '8px'};justify-content:flex-end;align-items:center;flex-wrap:wrap;width:100%;">${items.join('')}</div>`;
    }

    function keyTelegramHtml(links) {
        const data = getScreenLinks(links, 'key');
        if (!data.show_key_telegram && !data.key_error_link && !data.error_link && !data.normal) return '';
        return `<div style="width:100%;display:flex;flex-direction:column;align-items:flex-end;justify-content:flex-end;margin-top:8px;"><a id="sunflower-key-help-text" href="#" target="_blank" rel="noopener noreferrer" style="display:none;color:#f59e0b;font-size:12px;font-weight:800;text-align:right;max-width:260px;text-decoration:none;"></a></div>`;
    }

    function setKeyHelpState(links, warningText) {
        const data = getScreenLinks(links, 'key');
        const help = document.getElementById('sunflower-key-help-text');
        const link = document.getElementById('sunflower-key-telegram-link');
        const hasWarning = !!String(warningText || '').trim();
        if (help) {
            help.style.display = hasWarning ? 'block' : 'none';
            help.textContent = hasWarning ? String(data.warning_text || warningText || t('keyHelp')) : '';
        }
        if (link) {
            const targetLink = String(hasWarning ? (data.error_link || data.normal || data.telegram) : data.telegram).trim();
            if (targetLink) link.href = targetLink;
            if (help && targetLink) help.href = targetLink;
        }
    }

    function executeBot(code) {
        if (window.__SUNFLOWER_BOT_RUNNING__) return true;
        if (document.getElementById('nxMaster') || document.getElementById('nxDockIcon')) {
            window.__SUNFLOWER_BOT_RUNNING__ = true;
            return true;
        }

        const gmAddStyleFallback = function(css) {
            try {
                const style = document.createElement('style');
                style.textContent = String(css || '');
                (document.head || document.documentElement || document.body).appendChild(style);
                return style;
            } catch(e) {
                return null;
            }
        };
        const safeGMAddStyle = (typeof GM_addStyle === 'function') ? GM_addStyle : gmAddStyleFallback;
        const safeGMXmlhttpRequest = (typeof GM_xmlhttpRequest === 'function') ? GM_xmlhttpRequest : null;
        const safeGMSetValue = (typeof GM_setValue === 'function') ? GM_setValue : function(){};
        const safeGMGetValue = (typeof GM_getValue === 'function') ? GM_getValue : function(){ return ''; };
        const preparedCode = [
            'var unsafeWindow = (typeof unsafeWindow !== "undefined" ? unsafeWindow : window);',
            'var GM_addStyle = (typeof GM_addStyle === "function" ? GM_addStyle : arguments[0]);',
            'var GM_xmlhttpRequest = (typeof GM_xmlhttpRequest === "function" ? GM_xmlhttpRequest : arguments[1]);',
            'var GM_setValue = (typeof GM_setValue === "function" ? GM_setValue : arguments[2]);',
            'var GM_getValue = (typeof GM_getValue === "function" ? GM_getValue : arguments[3]);',
            String(code || '')
        ].join('\n');

        const runError = (label, err) => {
            window.__SUNFLOWER_BOT_RUNNING__ = false;
            window.__SUNFLOWER_LAST_BOT_ERROR__ = {
                label,
                message: String(err && err.message || err || 'unknown error'),
                stack: String(err && err.stack || '')
            };
            console.error('Sunflower bot execute error [' + label + ']:', err);
        };

        try {
            window.__SUNFLOWER_BOT_RUNNING__ = true;
            eval(preparedCode);
            return true;
        } catch (err2) {
            runError('eval', err2);
        }

        try {
            window.__SUNFLOWER_BOT_RUNNING__ = true;
            const runner = new Function(preparedCode);
            runner.call(window, safeGMAddStyle, safeGMXmlhttpRequest, safeGMSetValue, safeGMGetValue);
            return true;
        } catch (err1) {
            runError('prepared', err1);
            return false;
        }
    }

    function saveAuthStateAndRun(payload, botCode, uid) {
        sessionToken = String(payload.session_token || '');
        extractedUID = String(payload.uid || uid || '');
        saveAuthState({ token: sessionToken, uid: extractedUID, clientId: CLIENT_ID, scriptHash: SCRIPT_HASH, time: Date.now() });
        const decoded = decodeBotCode(botCode, extractedUID);
        if (!decoded) throw new Error(t('authFail'));
        saveBotCache(decoded);
        closeAuthModal();
        const started = executeBot(decoded);
        if (!started) throw new Error('Bot execute failed');
        helperStarted = true;
    }

    function toast(msg, ok = true) {
        const el = document.createElement('div');
        el.textContent = msg;
        el.style.cssText = `position:fixed;right:18px;bottom:18px;z-index:999999;background:${ok ? '#16a34a' : '#dc2626'};color:#fff;padding:10px 14px;border-radius:12px;font:700 13px Arial;box-shadow:0 10px 26px rgba(0,0,0,.25)`;
        document.body.appendChild(el);
        setTimeout(() => el.remove(), 2800);
    }

    function authCardHtml(links, warningText) {
        const quick = quickLinksHtml(links, false, false, 'login');
        const keyQuick = quickLinksHtml(links, false, false, 'key');
        const keyHelp = keyTelegramHtml(links);
        return `
        <div id="sunflower-auth-shell" style="position:fixed;inset:0;z-index:2147483646;background:radial-gradient(circle at top, rgba(30,41,59,.42), rgba(2,6,23,.92));display:flex;align-items:center;justify-content:center;padding:18px;backdrop-filter:blur(6px);">
          <div style="width:min(100%,420px);background:linear-gradient(180deg,#0b1424 0%,#09111f 100%);border:1px solid rgba(59,130,246,.35);border-radius:22px;box-shadow:0 28px 80px rgba(0,0,0,.55);padding:22px 20px 18px;color:#e5f2ff;font-family:Inter,Arial,sans-serif;position:relative;overflow:hidden;">
            <div style="position:absolute;inset:-120px auto auto -60px;width:220px;height:220px;background:radial-gradient(circle, rgba(56,189,248,.24), transparent 70%);pointer-events:none;"></div>
            <div style="position:absolute;inset:auto -80px -100px auto;width:220px;height:220px;background:radial-gradient(circle, rgba(59,130,246,.18), transparent 70%);pointer-events:none;"></div>
            <div style="position:relative;z-index:1;">
              <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;">
                <div>
                  <div style="font-size:13px;font-weight:900;letter-spacing:2px;color:#7dd3fc;">NEXUS</div>
                  <div style="font-size:24px;line-height:1.1;font-weight:900;color:#fff;margin-top:4px;">${t('title')}</div>
                  <div style="font-size:13px;color:#93c5fd;margin-top:8px;">${t('subtitle')}</div>
                </div>
                <div style="width:62px;height:62px;border-radius:18px;background:linear-gradient(135deg,#0ea5e9,#2563eb);display:flex;align-items:center;justify-content:center;box-shadow:0 12px 28px rgba(37,99,235,.38);font-size:30px;">🌻</div>
              </div>
              <div style="margin-top:16px;display:flex;flex-direction:column;gap:10px;">
                <input id="sunflower-key-input" type="text" placeholder="${t('needKey')}" style="width:100%;height:48px;border-radius:16px;border:1px solid rgba(148,163,184,.22);background:rgba(15,23,42,.88);padding:0 16px;color:#fff;font-size:14px;font-weight:700;outline:none;box-sizing:border-box;">
                <button id="sunflower-login-btn" style="height:48px;border:none;border-radius:16px;background:linear-gradient(135deg,#2563eb,#0ea5e9);color:#fff;font-weight:900;font-size:14px;letter-spacing:.4px;cursor:pointer;box-shadow:0 12px 26px rgba(37,99,235,.35);">${t('login')}</button>
                <div id="sunflower-auth-status" style="min-height:18px;font-size:12px;color:${warningText ? '#fca5a5' : '#93c5fd'};font-weight:700;">${warningText || ''}</div>
              </div>
              ${quick ? `<div style="margin-top:14px;">${quick}</div>` : ''}
              ${keyQuick || keyHelp ? `<div style="margin-top:10px;">${keyQuick}${keyHelp}</div>` : ''}
            </div>
          </div>
        </div>`;
    }

    function closeAuthModal() {
        const shell = document.getElementById('sunflower-auth-shell');
        if (shell) shell.remove();
    }

    function renderAuth(links = {}, warningText = '') {
        closeAuthModal();
        const wrap = document.createElement('div');
        wrap.innerHTML = authCardHtml(links, warningText);
        document.body.appendChild(wrap.firstElementChild);
        setKeyHelpState(links, warningText);
        const btn = document.getElementById('sunflower-login-btn');
        const input = document.getElementById('sunflower-key-input');
        const status = document.getElementById('sunflower-auth-status');
        const submit = async () => {
            const key = String(input?.value || '').trim();
            if (!key) {
                status.textContent = t('needKey');
                status.style.color = '#fca5a5';
                setKeyHelpState(links, t('needKey'));
                return;
            }
            extractedUID = extractUID();
            status.textContent = t('authWait');
            status.style.color = '#93c5fd';
            const resp = await gmRequest('POST', SERVER_URL + '/api/auth', { uid: extractedUID || '', license_key: key, client_id: CLIENT_ID, script_hash: SCRIPT_HASH, language: selectedLanguage });
            if (!resp.success || !resp.bot_code || !resp.session_token) {
                const err = String(resp.error || t('authFail'));
                status.textContent = err;
                status.style.color = '#fca5a5';
                setKeyHelpState((resp && resp.quick_links) || links, err);
                return;
            }
            try {
                saveAuthStateAndRun(resp, resp.bot_code, extractedUID);
                toast(t('authOk'), true);
                setTimeout(() => checkNotice((resp && resp.quick_links) || {}, extractedUID, resp.session_token), 1200);
            } catch(e) {
                const lastErr = window.__SUNFLOWER_LAST_BOT_ERROR__ || {};
                const detail = lastErr.message || e.message || 'unknown error';
                status.textContent = e.message || t('authFail');
                status.style.color = '#fca5a5';
                toast('Bot calismadi: ' + detail, false);
                console.error('Sunflower last bot error detail:', lastErr);
            }
        };
        btn?.addEventListener('click', submit);
        input?.addEventListener('keydown', (e) => { if (e.key === 'Enter') submit(); });
        input?.focus();
    }

    async function openTelegramConnect(links = {}) {
        const saved = loadTelegram();
        const container = document.createElement('div');
        container.innerHTML = `
        <div id="sunflower-tg-shell" style="position:fixed;inset:0;z-index:2147483646;background:rgba(2,6,23,.78);display:flex;align-items:center;justify-content:center;padding:18px;backdrop-filter:blur(6px);">
          <div style="width:min(100%,420px);background:linear-gradient(180deg,#0b1424 0%,#09111f 100%);border:1px solid rgba(59,130,246,.35);border-radius:22px;box-shadow:0 28px 80px rgba(0,0,0,.55);padding:22px 20px 18px;color:#e5f2ff;font-family:Inter,Arial,sans-serif;">
            <div style="font-size:24px;font-weight:900;color:#fff;">${t('tgTitle')}</div>
            <div style="margin-top:14px;display:flex;flex-direction:column;gap:10px;">
              <input id="sunflower-tg-token" type="text" placeholder="Bot token" value="${String(saved.token || '').replace(/"/g, '&quot;')}" style="width:100%;height:48px;border-radius:16px;border:1px solid rgba(148,163,184,.22);background:rgba(15,23,42,.88);padding:0 16px;color:#fff;font-size:14px;font-weight:700;outline:none;box-sizing:border-box;">
              <input id="sunflower-tg-chat" type="text" placeholder="Chat ID" value="${String(saved.chatId || '').replace(/"/g, '&quot;')}" style="width:100%;height:48px;border-radius:16px;border:1px solid rgba(148,163,184,.22);background:rgba(15,23,42,.88);padding:0 16px;color:#fff;font-size:14px;font-weight:700;outline:none;box-sizing:border-box;">
              <div style="display:flex;gap:10px;">
                <button id="sunflower-tg-save" style="flex:1;height:46px;border:none;border-radius:16px;background:linear-gradient(135deg,#2563eb,#0ea5e9);color:#fff;font-weight:900;cursor:pointer;">${t('tgSave')}</button>
                <button id="sunflower-tg-skip" style="flex:1;height:46px;border:none;border-radius:16px;background:#1e293b;color:#fff;font-weight:900;cursor:pointer;">${t('tgSkip')}</button>
              </div>
              <div id="sunflower-tg-status" style="min-height:18px;font-size:12px;color:#93c5fd;font-weight:700;"></div>
              ${quickLinksHtml(links, false, false, 'telegram') || ''}
            </div>
          </div>
        </div>`;
        document.body.appendChild(container.firstElementChild);
        const close = () => document.getElementById('sunflower-tg-shell')?.remove();
        document.getElementById('sunflower-tg-skip')?.addEventListener('click', close);
        document.getElementById('sunflower-tg-save')?.addEventListener('click', async () => {
            const token = String(document.getElementById('sunflower-tg-token')?.value || '').trim();
            const chatId = String(document.getElementById('sunflower-tg-chat')?.value || '').trim();
            const status = document.getElementById('sunflower-tg-status');
            if (!token || !chatId) {
                status.textContent = t('tgNeed');
                status.style.color = '#fca5a5';
                return;
            }
            status.textContent = t('wait');
            const resp = await gmRequest('POST', SERVER_URL + '/api/telegram/register', { uid: extractedUID, token: sessionToken, telegram_token: token, telegram_chat_id: chatId });
            if (!resp.success) {
                status.textContent = String(resp.error || t('authFail'));
                status.style.color = '#fca5a5';
                return;
            }
            saveTelegram(token, chatId);
            close();
            toast(t('tgOk'), true);
        });
    }

    async function checkNotice(links, uid, token) {
        const resp = await gmRequest('POST', SERVER_URL + '/api/notice/next', { uid, token });
        if (!resp.success || !resp.notice || !resp.notice.id) return;
        const notice = resp.notice;
        const seen = getSeenNoticeIds();
        if (seen.includes(notice.id)) return;
        const wrap = document.createElement('div');
        wrap.innerHTML = `
        <div id="sunflower-notice-shell" style="position:fixed;inset:0;z-index:2147483646;background:rgba(2,6,23,.78);display:flex;align-items:center;justify-content:center;padding:18px;backdrop-filter:blur(6px);">
          <div style="width:min(100%,430px);background:linear-gradient(180deg,#0b1424 0%,#09111f 100%);border:1px solid rgba(59,130,246,.35);border-radius:22px;box-shadow:0 28px 80px rgba(0,0,0,.55);padding:22px 20px 18px;color:#e5f2ff;font-family:Inter,Arial,sans-serif;">
            <div style="font-size:24px;font-weight:900;color:#fff;">${t('notice')}</div>
            <div style="margin-top:12px;color:#dbeafe;font-size:14px;line-height:1.6;white-space:pre-wrap;">${String(notice.text || '').replace(/[<>&]/g, '')}</div>
            <div style="margin-top:14px;">${quickLinksHtml(notice.links || links || {}, false, true, 'login') || ''}</div>
            <button id="sunflower-notice-close" style="margin-top:16px;width:100%;height:46px;border:none;border-radius:16px;background:linear-gradient(135deg,#2563eb,#0ea5e9);color:#fff;font-weight:900;cursor:pointer;">${t('login') === 'GIRIS' ? 'TAMAM' : 'OK'}</button>
          </div>
        </div>`;
        document.body.appendChild(wrap.firstElementChild);
        document.getElementById('sunflower-notice-close')?.addEventListener('click', async () => {
            markNoticeSeen(notice.id);
            document.getElementById('sunflower-notice-shell')?.remove();
            await gmRequest('POST', SERVER_URL + '/api/notice/ack', { uid, token, notice_id: notice.id });
        });
    }

    async function restoreSession() {
        const auth = loadAuthState();
        if (!auth || !auth.token || !auth.uid) return false;
        const resp = await gmRequest('POST', SERVER_URL + '/api/heartbeat', { uid: auth.uid, token: auth.token, client_id: CLIENT_ID, script_hash: SCRIPT_HASH, page: location.pathname + location.search });
        if (!resp.success) {
            clearAuthState();
            clearBotCache();
            return false;
        }
        extractedUID = auth.uid;
        sessionToken = auth.token;
        const current = await gmRequest('POST', SERVER_URL + '/api/bot/current', { uid: auth.uid, token: auth.token });
        if (current && current.success && current.bot_code) {
            const freshBot = decodeBotCode(current.bot_code, auth.uid);
            if (freshBot) {
                saveBotCache(freshBot);
                helperStarted = executeBot(freshBot);
                return helperStarted;
            }
        }
        const cachedBot = loadBotCache();
        if (cachedBot) {
            helperStarted = executeBot(cachedBot);
            return helperStarted;
        }
        return false;
    }

    async function boot() {
        if (helperStarted) return;
        if (window.top !== window.self) return;
        if (!/sunflower-land\.com$/i.test(location.hostname)) return;
        if (window[PAGE_LOCK_KEY]) return;
        window[PAGE_LOCK_KEY] = CLIENT_ID;
        if (document.getElementById('nxMaster') || document.getElementById('nxDockIcon')) {
            helperStarted = true;
            return;
        }
        if (await restoreSession()) return;
        const publicLinks = await gmRequest('GET', SERVER_URL + '/api/public-links');
        renderAuth((publicLinks && publicLinks.quick_links) || {}, '');
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
    else boot();
})();
'''


def load_json_file(path, default):
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            if isinstance(data, dict):
                merged = dict(default)
                merged.update(data)
                return merged
        except Exception:
            pass
    return dict(default)


def save_json_file(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


class SunflowerPanel:
    def __init__(self, root):
        self.root = root
        self.settings = load_json_file(SETTINGS_FILE, DEFAULT_SETTINGS)
        self.secrets = load_json_file(SECRETS_FILE, DEFAULT_SECRETS)
        self.current_rows = {}
        self.log_lines = []
        self.script_logs = []
        self.bot_logs = []
        self.root.title('Sunflower Panel')
        self.root.geometry('1320x820')
        self.root.configure(bg='#0f172a')
        self._build_ui()
        self.refresh_users(silent=True)
        self.refresh_generated_list()
        self.load_selected_bot_preview_if_exists()
        self.log('Panel hazir knk', 'script')
        self.start_auto_refresh()

    def save_state(self):
        save_json_file(SETTINGS_FILE, self.settings)
        save_json_file(SECRETS_FILE, self.secrets)

    def get_secret(self, key):
        return str(self.secrets.get(key) or '').strip()

    def request_json(self, method, path, payload=None, need_admin=False):
        server_url = str(self.settings.get('server_url') or '').strip().rstrip('/')
        if not server_url:
            raise RuntimeError('server url yok knk')
        headers = {'Content-Type': 'application/json'}
        if need_admin:
            token = self.get_secret('admin_token')
            if not token:
                raise RuntimeError('admin token yok knk')
            headers['X-Admin-Token'] = token
        data = None if payload is None else json.dumps(payload).encode('utf-8')
        req = urlrequest.Request(server_url + path, data=data, headers=headers, method=method)
        try:
            with urlrequest.urlopen(req, timeout=35) as resp:
                return json.loads(resp.read().decode('utf-8') or '{}')
        except HTTPError as e:
            raw = e.read().decode('utf-8', errors='ignore')
            try:
                return json.loads(raw or '{}')
            except Exception:
                raise RuntimeError(f'HTTP {e.code}: {raw}')
        except URLError as e:
            raise RuntimeError(str(e))

    def log(self, text, channel='script'):
        line = f'[{datetime.now().strftime("%H:%M:%S")}] {text}'
        self.log_lines.append(line)
        if channel == 'bot':
            self.bot_logs.append(line)
        else:
            self.script_logs.append(line)
        if len(self.log_lines) > 500:
            self.log_lines = self.log_lines[-500:]
        if len(self.bot_logs) > 250:
            self.bot_logs = self.bot_logs[-250:]
        if len(self.script_logs) > 250:
            self.script_logs = self.script_logs[-250:]
        self.render_logs()

    def render_logs(self):
        if not hasattr(self, 'log_text'):
            return
        lines = self.script_logs if self.active_left_panel == 'script' else self.bot_logs if self.active_left_panel == 'bot' else self.log_lines
        self.log_text.delete('1.0', 'end')
        self.log_text.insert('1.0', '\n'.join(lines[-200:]))
        self.log_text.see('end')

    def _build_ui(self):
        self.active_left_panel = 'script'
        top = tk.Frame(self.root, bg='#0f172a')
        top.pack(fill='x', padx=14, pady=10)
        tk.Label(top, text='NEXUS SUNFLOWER PANEL', bg='#0f172a', fg='#FFD700', font=('Consolas', 20, 'bold')).pack(side='left')

        main = tk.Frame(self.root, bg='#0f172a')
        main.pack(fill='both', expand=True, padx=14, pady=(0, 14))
        main.pack_propagate(False)

        left = tk.Frame(main, bg='#101c31', highlightbackground='#18314f', highlightthickness=1, width=430)
        left.pack(side='left', fill='y', padx=(0, 12))
        left.pack_propagate(False)

        right = tk.Frame(main, bg='#101c31', highlightbackground='#18314f', highlightthickness=1)
        right.pack(side='left', fill='both', expand=True)

        nav = tk.Frame(left, bg='#101c31')
        nav.pack(fill='x', padx=12, pady=(12, 8))
        self.left_nav_buttons = {}
        for key, text, color in [
            ('bot', 'BOT SEC', '#0ea5e9'),
            ('script', 'SCRIPT URET', '#22c55e'),
            ('all', 'DETAYLAR', '#a855f7')
        ]:
            btn = tk.Button(nav, text=text, command=lambda k=key: self.switch_left_panel(k), bg='#132238', fg='#dbeafe', relief='flat', font=('Consolas', 10, 'bold'), cursor='hand2')
            btn.pack(side='left', padx=(0, 8), ipadx=8, ipady=6)
            self.left_nav_buttons[key] = (btn, color)

        self.left_host = tk.Frame(left, bg='#101c31')
        self.left_host.pack(fill='both', expand=True, padx=12)
        self.left_panels = {}
        self._build_left_bot_panel()
        self._build_left_script_panel()
        self._build_left_all_logs_panel()

        detail_wrap = tk.Frame(left, bg='#101c31', height=210)
        detail_wrap.pack(side='bottom', fill='x', padx=12, pady=12)
        detail_wrap.pack_propagate(False)
        self.log_title_var = tk.StringVar(value='KULLANICI DETAYLARI')
        tk.Label(detail_wrap, textvariable=self.log_title_var, bg='#101c31', fg='#fde68a', font=('Consolas', 11, 'bold')).pack(anchor='w', pady=(0, 6))
        self.log_text = scrolledtext.ScrolledText(detail_wrap, height=10, bg='#06090f', fg='#5eead4', font=('Consolas', 9), relief='flat')
        self.log_text.pack(fill='both', expand=True)

        self._build_right_panel(right)
        self.switch_left_panel('bot')

    def _build_left_bot_panel(self):
        panel = tk.Frame(self.left_host, bg='#101c31')
        self.left_panels['bot'] = panel
        tk.Label(panel, text='BOT DOSYASI', bg='#101c31', fg='#fde68a', font=('Consolas', 11, 'bold')).pack(anchor='w', pady=(0, 6))
        row = tk.Frame(panel, bg='#101c31')
        row.pack(fill='x', pady=(0, 10))
        self.bot_path_var = tk.StringVar(value=self.settings.get('selected_bot_path', ''))
        tk.Entry(row, textvariable=self.bot_path_var, bg='#09111f', fg='white', insertbackground='white', relief='flat', font=('Consolas', 10)).pack(side='left', fill='x', expand=True, ipady=8)
        tk.Button(row, text='SEC', command=self.select_bot_file, bg='#2563eb', fg='white', relief='flat', font=('Consolas', 9, 'bold')).pack(side='left', padx=(8, 0), ipadx=10, ipady=8)
        btn_row = tk.Frame(panel, bg='#101c31')
        btn_row.pack(fill='x', pady=(0, 10))
        tk.Button(btn_row, text='YUKLE', command=self.upload_bot, bg='#22c55e', fg='#04110a', relief='flat', font=('Consolas', 10, 'bold')).pack(side='left', ipadx=12, ipady=8)
        tk.Button(btn_row, text='OKU', command=self.preview_bot_file, bg='#334155', fg='white', relief='flat', font=('Consolas', 10, 'bold')).pack(side='left', padx=(8, 0), ipadx=12, ipady=8)
        self.bot_preview = scrolledtext.ScrolledText(panel, height=26, bg='#09111f', fg='#dbeafe', insertbackground='white', font=('Consolas', 9), relief='flat')
        self.bot_preview.pack(fill='both', expand=True)

    def _build_left_script_panel(self):
        panel = tk.Frame(self.left_host, bg='#101c31')
        self.left_panels['script'] = panel
        tk.Label(panel, text='SCRIPT URET', bg='#101c31', fg='#fde68a', font=('Consolas', 11, 'bold')).pack(anchor='w', pady=(0, 6))
        tk.Label(panel, text='Username', bg='#101c31', fg='#cbd5e1', font=('Consolas', 10, 'bold')).pack(anchor='w')
        self.name_entry = tk.Entry(panel, bg='#09111f', fg='white', insertbackground='white', relief='flat', font=('Consolas', 12))
        self.name_entry.pack(fill='x', ipady=8, pady=(6, 10))
        self.name_entry.insert(0, self.get_next_available_username())
        lang_row = tk.Frame(panel, bg='#101c31')
        lang_row.pack(fill='x', pady=(0, 8))
        tk.Label(lang_row, text='Dil', bg='#101c31', fg='#cbd5e1', font=('Consolas', 10, 'bold')).pack(side='left')
        self.lang_var = tk.StringVar(value='tr')
        ttk.Combobox(lang_row, textvariable=self.lang_var, values=['tr', 'en'], state='readonly', width=8).pack(side='left', padx=10)
        tk.Label(panel, text='Uretilen script varsayilan olarak SABIT kullanici olur.', bg='#101c31', fg='#94a3b8', font=('Consolas', 9, 'bold')).pack(anchor='w', pady=(0, 10))
        tk.Button(panel, text='URET', command=self.generate_script, bg='#22c55e', fg='#04110a', relief='flat', font=('Consolas', 11, 'bold')).pack(anchor='w', ipadx=18, ipady=8, pady=(0, 10))
        self.script_preview = scrolledtext.ScrolledText(panel, height=26, bg='#09111f', fg='#dbeafe', insertbackground='white', font=('Consolas', 9), relief='flat')
        self.script_preview.pack(fill='both', expand=True)

    def _build_left_all_logs_panel(self):
        panel = tk.Frame(self.left_host, bg='#101c31')
        self.left_panels['all'] = panel
        tk.Label(panel, text='SECILI KULLANICI DETAYLARI', bg='#101c31', fg='#fde68a', font=('Consolas', 11, 'bold')).pack(anchor='w', pady=(0, 6))
        self.all_log_text = scrolledtext.ScrolledText(panel, height=34, bg='#09111f', fg='#dbeafe', insertbackground='white', font=('Consolas', 9), relief='flat')
        self.all_log_text.pack(fill='both', expand=True)

    def _build_right_panel(self, parent):
        top = tk.Frame(parent, bg='#101c31')
        top.pack(fill='x', padx=12, pady=(12, 8))
        tk.Label(top, text='KULLANICILAR', bg='#101c31', fg='#fde68a', font=('Consolas', 12, 'bold')).pack(side='left')
        tk.Button(top, text='TUMUNU TEMIZLE', command=self.clear_all_scripts, bg='#7f1d1d', fg='white', relief='flat', font=('Consolas', 9, 'bold')).pack(side='right', ipadx=8, ipady=6)

        cols = ('Kullanici', 'Key', 'Kullanici Adi', 'Tur', 'Dosya')
        self.tree = ttk.Treeview(parent, columns=cols, show='headings', style='Vip.Treeview')
        for col in cols:
            self.tree.heading(col, text=col)
        self.tree.column('Kullanici', width=180, anchor='w')
        self.tree.column('Key', width=230, anchor='w')
        self.tree.column('Kullanici Adi', width=140, anchor='center')
        self.tree.column('Tur', width=110, anchor='center')
        self.tree.column('Dosya', width=180, anchor='w')
        self.tree.pack(fill='both', expand=True, padx=12, pady=(0, 12))
        self.tree.bind('<<TreeviewSelect>>', lambda e: self.on_tree_select())
        self.tree.bind('<Button-3>', self.on_tree_right_click)

        style = ttk.Style()
        try:
            style.theme_use('clam')
        except Exception:
            pass
        style.configure('Vip.Treeview', background='#09111f', fieldbackground='#09111f', foreground='#e5e7eb', rowheight=28, borderwidth=0, font=('Consolas', 10))
        style.configure('Vip.Treeview.Heading', background='#132238', foreground='#fde68a', font=('Consolas', 10, 'bold'))
        self.tree.tag_configure('online', foreground='#22c55e')
        self.tree.tag_configure('passive', foreground='#ef4444')
        self.tree.tag_configure('active', foreground='#f59e0b')
        self.tree.tag_configure('banned', foreground='#ef4444')

        self.tree_menu = tk.Menu(self.root, tearoff=0, bg='#0f172a', fg='#e5e7eb', activebackground='#1e293b', activeforeground='#FFD700')
        self.tree_menu.add_command(label='📋 Key Kopyala', command=self.copy_selected_key)
        self.tree_menu.add_command(label='📋 UID Kopyala', command=self.copy_selected_uid)
        self.tree_menu.add_separator()
        self.tree_menu.add_command(label='✅ On', command=lambda: self.set_selected_license_state(True))
        self.tree_menu.add_command(label='⛔ Off', command=lambda: self.set_selected_license_state(False))
        self.tree_menu.add_separator()
        self.tree_menu.add_command(label='👤 Sabit Kullanici', command=lambda: self.set_selected_uid_mode('fixed'))
        self.tree_menu.add_command(label='🔁 Coklu Kullanici', command=lambda: self.set_selected_uid_mode('replace'))
        self.tree_menu.add_separator()
        self.tree_menu.add_command(label='🗑 Script Sil', command=self.delete_selected_license)

    def switch_left_panel(self, key):
        for panel in self.left_panels.values():
            panel.pack_forget()
        for btn, _ in self.left_nav_buttons.values():
            btn.config(bg='#132238', fg='#dbeafe')
        self.active_left_panel = key
        if key == 'bot':
            self.log_title_var.set('KULLANICI DETAYLARI')
        elif key == 'script':
            self.log_title_var.set('KULLANICI DETAYLARI')
        else:
            self.log_title_var.set('KULLANICI DETAYLARI')
            self.render_selected_details()
        self.left_panels[key].pack(fill='both', expand=True)
        btn, color = self.left_nav_buttons[key]
        btn.config(bg=color, fg='white')
        self.render_selected_details()

    def get_next_available_username(self):
        used = set()
        for path in GENERATED_DIR.glob('user*.user.js'):
            name = path.stem.lower().replace('.user', '')
            if name.startswith('user'):
                num = name[4:]
                if num.isdigit():
                    used.add(int(num))
        n = 1
        while n in used:
            n += 1
        return f'user{n}'

    def load_selected_bot_preview_if_exists(self):
        path = str(self.settings.get('selected_bot_path') or '').strip()
        if not path or not Path(path).exists():
            return
        try:
            text = Path(path).read_text(encoding='utf-8', errors='ignore')
            self.bot_preview.delete('1.0', 'end')
            self.bot_preview.insert('1.0', text)
        except Exception:
            pass

    def select_bot_file(self):
        path = filedialog.askopenfilename(title='Bot TXT Sec', initialdir=str(BASE_DIR), filetypes=[('Text Files', '*.txt *.js'), ('All Files', '*.*')])
        if not path:
            return
        self.bot_path_var.set(path)
        self.settings['selected_bot_path'] = path
        self.settings['selected_bot_name'] = Path(path).name
        self.save_state()
        self.preview_bot_file()
        self.log(f'Bot secildi: {Path(path).name}', 'bot')

    def preview_bot_file(self):
        path = self.bot_path_var.get().strip()
        if not path:
            messagebox.showwarning('Uyari', 'Bot sec knk')
            return
        try:
            text = Path(path).read_text(encoding='utf-8', errors='ignore')
        except Exception as e:
            messagebox.showerror('Hata', str(e))
            return
        self.bot_preview.delete('1.0', 'end')
        self.bot_preview.insert('1.0', text)
        self.log('Bot okundu', 'bot')

    def upload_bot(self):
        path = self.bot_path_var.get().strip()
        if not path:
            messagebox.showwarning('Uyari', 'Bot sec knk')
            return
        try:
            content = Path(path).read_text(encoding='utf-8', errors='ignore')
            res = self.request_json('POST', '/admin/bot', {'content': content}, need_admin=True)
            if not res.get('success'):
                raise RuntimeError(res.get('error') or 'bot yuklenemedi')
            self.settings['selected_bot_path'] = path
            self.settings['selected_bot_name'] = Path(path).name
            self.save_state()
            self.log(f'Bot yuklendi: {Path(path).name}', 'bot')
            messagebox.showinfo('Tamam', 'Bot servera yuklendi knk')
        except Exception as e:
            self.log(f'Bot yukleme hata: {e}', 'bot')
            messagebox.showerror('Hata', str(e))

    def client_hash_text(self, text):
        return hashlib.sha256(text.encode('utf-8')).hexdigest()[:24]

    def _make_obfuscated_js_pack(self, text, chunk_size=6, hint='seed'):
        src = str(text or '')
        parts = [src[i:i + chunk_size] for i in range(0, len(src), chunk_size)] or ['']
        seed = sum(ord(ch) + idx for idx, ch in enumerate(str(hint or 'seed'))) or 17
        real_rows = []
        for idx, part in enumerate(parts):
            reverse_flag = idx % 2 == 1
            cooked = part[::-1] if reverse_flag else part
            real_rows.append({'q': base64.b64encode(cooked.encode('utf-8')).decode('ascii'), 'm': seed ^ (1 if reverse_flag else 0)})
        bait_rows = [
            {'q': base64.b64encode(b'https://status.invalid').decode('ascii'), 'm': seed ^ 0},
            {'q': base64.b64encode(b'sunflower-shadow').decode('ascii'), 'm': seed ^ 1},
            {'q': base64.b64encode(b'noop-route').decode('ascii'), 'm': seed ^ 0},
            {'q': base64.b64encode(b'cdn-edge').decode('ascii'), 'm': seed ^ 1},
        ]
        mixed = []
        order = []
        bait_index = 0
        for idx, row in enumerate(real_rows):
            if idx % 2 == 0 and bait_index < len(bait_rows):
                mixed.append(bait_rows[bait_index])
                bait_index += 1
            mixed.append(row)
            order.append(len(mixed) - 1)
        while bait_index < len(bait_rows):
            mixed.append(bait_rows[bait_index])
            bait_index += 1
        key_names = [f'_{(idx + 3) * 7:x}' for idx in range(len(mixed))]
        payload = {name: mixed[idx] for idx, name in enumerate(key_names)}
        payload['k'] = '|'.join(key_names)
        payload['o'] = base64.b64encode(json.dumps(order).encode('utf-8')).decode('ascii')
        return ', '.join(f'{json.dumps(key)}: {json.dumps(value, ensure_ascii=False)}' for key, value in payload.items())

    def build_client_script(self, client_name, client_id, script_hash, license_key, lang):
        server_url = str(self.settings.get('server_url') or '').strip().rstrip('/')
        host = urlparse(server_url).hostname or 'sunflower-panel-server.onrender.com'
        script = CLIENT_TEMPLATE
        server_pack = self._make_obfuscated_js_pack(server_url, 7, 'server_url')
        name_pack = self._make_obfuscated_js_pack(client_name, 5, 'client_name')
        client_pack = self._make_obfuscated_js_pack(client_id, 4, 'client_id')
        hash_pack = self._make_obfuscated_js_pack(script_hash, 6, 'script_hash')
        replacements = {
            '__CLIENT_NAME__': client_name,
            '__SERVER_URL_PACK__': server_pack,
            '__CLIENT_NAME_PACK__': name_pack,
            '__CLIENT_ID_PACK__': client_pack,
            '__SCRIPT_HASH_PACK__': hash_pack,
            '__SERVER_URL_HINT__': json.dumps('server_url'),
            '__CLIENT_NAME_HINT__': json.dumps('client_name'),
            '__CLIENT_ID_HINT__': json.dumps('client_id'),
            '__SCRIPT_HASH_HINT__': json.dumps('script_hash'),
            '__SERVER_HOST__': host,
            '__LANG__': json.dumps(lang),
        }
        for old, new in replacements.items():
            script = script.replace(old, str(new))
        return script

    def generate_script(self):
        name = self.name_entry.get().strip()
        if not name:
            messagebox.showwarning('Uyari', 'Username gir knk')
            return
        client_id = 'sf_' + secrets.token_hex(8)
        script_hash = self.client_hash_text(name + '|' + client_id)
        filename = f'{name}.user.js'
        payload = {
            'client_name': name,
            'client_id': client_id,
            'script_hash': script_hash,
            'script_file': filename,
            'language': self.lang_var.get().strip() or 'tr',
            'uid_mode': 'fixed',
            'status': 'active'
        }
        try:
            res = self.request_json('POST', '/admin/license/create', payload, need_admin=True)
            if not res.get('success'):
                raise RuntimeError(res.get('error') or 'lisans olusmadi')
            license_key = str(res.get('encrypted_license') or '').strip()
            if not license_key:
                raise RuntimeError('key donmedi knk')
            script_content = self.build_client_script(name, client_id, script_hash, license_key, payload['language'])
            out_path = GENERATED_DIR / filename
            out_path.write_text(script_content, encoding='utf-8')
            self.script_preview.delete('1.0', 'end')
            self.script_preview.insert('1.0', script_content)
            self.log(f'Script uretildi: {filename}', 'script')
            self.log(f'Key hazir: {res.get("license_id", "-")}', 'script')
            self.refresh_generated_list()
            self.refresh_users()
            messagebox.showinfo('Basarili', f'Script uretildi knk\n\nDosya: {filename}\n\nKULLANICIYA VERECEGIN KEY:\n{license_key}')
            self.name_entry.delete(0, 'end')
            self.name_entry.insert(0, self.get_next_available_username())
        except Exception as e:
            self.log(f'Script uretim hata: {e}', 'script')
            messagebox.showerror('Hata', str(e))

    def refresh_generated_list(self):
        if not hasattr(self, 'generated_list'):
            return
        self.generated_list.delete(0, 'end')
        files = sorted(GENERATED_DIR.glob('*.user.js'), key=lambda p: p.stat().st_mtime, reverse=True)
        for path in files:
            self.generated_list.insert('end', path.name)

    def start_auto_refresh(self):
        def tick():
            try:
                self.refresh_users(silent=True)
            except Exception:
                pass
            finally:
                if self.root.winfo_exists():
                    self.root.after(3500, tick)
        self.root.after(3500, tick)

    def shorten_key(self, text):
        value = str(text or '').strip()
        if len(value) <= 14:
            return value
        return value[:7] + '...' + value[-4:]

    def refresh_users(self, silent=False):
        try:
            res = self.request_json('GET', '/admin/licenses', need_admin=True)
            if not res.get('success'):
                if not silent:
                    raise RuntimeError(res.get('error') or 'liste alinamadi')
                return
            rows = res.get('licenses') or {}
            selected_license = None
            selected = self.tree.selection()
            if selected and selected[0] in self.current_rows:
                selected_license = str(self.current_rows[selected[0]].get('license_id') or '').strip()
            for item in self.tree.get_children():
                self.tree.delete(item)
            self.current_rows = {}
            first = ''
            chosen = ''
            ordered = sorted(rows.items(), key=lambda kv: str((kv[1] or {}).get('created_at') or ''), reverse=True)
            for license_id, row in ordered:
                row = dict(row or {})
                row['license_id'] = license_id
                key_text = str(row.get('encrypted_license') or '')
                shown_uid = str(row.get('display_uid') or row.get('uid') or row.get('last_uid') or '').strip() or '-'
                mode_text = 'Sabit' if str(row.get('uid_mode') or 'fixed').strip().lower() == 'fixed' else 'Coklu'
                file_name = str(row.get('script_file') or '-').strip()
                tag = str(row.get('row_tag') or 'active')
                item_id = self.tree.insert('', 'end', values=(str(row.get('client_name') or '-'), self.shorten_key(key_text), shown_uid, mode_text, file_name), tags=(tag,))
                self.current_rows[item_id] = row
                if not first:
                    first = item_id
                if selected_license and selected_license == license_id:
                    chosen = item_id
            target = chosen or first
            if target:
                self.tree.selection_set(target)
                self.tree.focus(target)
            if self.active_left_panel == 'all':
                self.all_log_text.delete('1.0', 'end')
                self.all_log_text.insert('1.0', '\n'.join(self.log_lines[-300:]))
        except Exception as e:
            if not silent:
                self.log(f'Liste yenileme hata: {e}', 'script')
                messagebox.showerror('Hata', str(e))

    def render_selected_details(self):
        license_id, row = self.get_selected_license()
        self.log_text.delete('1.0', 'end')
        self.all_log_text.delete('1.0', 'end')
        if not license_id or not row:
            text = 'Kullanici sec knk'
        else:
            mode_text = 'Sabit' if str(row.get('uid_mode') or 'fixed').strip().lower() == 'fixed' else 'Coklu'
            text = '\n'.join([
                f'Kullanici      : {row.get("client_name") or "-"}',
                f'Kullanici Adi  : {row.get("display_uid") or row.get("uid") or row.get("last_uid") or "-"}',
                f'Key            : {row.get("encrypted_license") or "-"}',
                f'Tur            : {mode_text}',
                f'Durum          : {row.get("status_text") or row.get("status") or "-"}',
                f'Dosya          : {row.get("script_file") or "-"}',
                f'Lisans ID      : {row.get("license_id") or "-"}',
            ])
        self.log_text.insert('1.0', text)
        self.all_log_text.insert('1.0', text)

    def on_tree_select(self):
        self.render_selected_details()

    def on_tree_right_click(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.tree.focus(item)
            try:
                self.tree_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self.tree_menu.grab_release()

    def get_selected_license(self):
        sel = self.tree.selection()
        if not sel:
            return None, None
        item_id = sel[0]
        row = self.current_rows.get(item_id)
        if not row:
            return None, None
        return str(row.get('license_id') or '').strip(), row

    def copy_selected_key(self):
        _, row = self.get_selected_license()
        if not row:
            return
        value = str(row.get('encrypted_license') or '').strip()
        if not value:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(value)
        self.log('Key kopyalandi', 'script')

    def copy_selected_uid(self):
        _, row = self.get_selected_license()
        if not row:
            return
        value = str(row.get('display_uid') or row.get('uid') or row.get('last_uid') or '').strip()
        if not value:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(value)
        self.log('UID kopyalandi', 'script')

    def set_selected_license_state(self, active):
        license_id, row = self.get_selected_license()
        if not license_id:
            messagebox.showwarning('Secim yok', 'Script sec knk')
            return
        try:
            res = self.request_json('POST', '/admin/license/state', {'license_id': license_id, 'active': bool(active)}, need_admin=True)
            if not res.get('success'):
                raise RuntimeError(res.get('error') or 'durum degismedi')
            self.log(f'Lisans durum degisti: {license_id} -> {"on" if active else "off"}', 'script')
            self.refresh_users()
        except Exception as e:
            self.log(f'Durum degistirme hata: {e}', 'script')
            messagebox.showerror('Hata', str(e))

    def set_selected_uid_mode(self, uid_mode):
        license_id, row = self.get_selected_license()
        if not license_id:
            messagebox.showwarning('Secim yok', 'Script sec knk')
            return
        try:
            res = self.request_json('POST', '/admin/license/uid-mode', {'license_id': license_id, 'uid_mode': uid_mode}, need_admin=True)
            if not res.get('success'):
                raise RuntimeError(res.get('error') or 'mod degismedi')
            self.log(f'Kullanici modu degisti: {license_id} -> {uid_mode}', 'script')
            self.refresh_users()
        except Exception as e:
            self.log(f'Mod degistirme hata: {e}', 'script')
            messagebox.showerror('Hata', str(e))

    def delete_selected_license(self):
        license_id, row = self.get_selected_license()
        if not license_id:
            messagebox.showwarning('Secim yok', 'Script sec knk')
            return
        if not messagebox.askyesno('Sil', f'{license_id} silinsin mi knk?'):
            return
        try:
            res = self.request_json('POST', '/admin/license/delete', {'license_id': license_id}, need_admin=True)
            if not res.get('success'):
                raise RuntimeError(res.get('error') or 'silinemedi')
            script_file = str(row.get('script_file') or '').strip()
            if script_file:
                local_path = GENERATED_DIR / script_file
                if local_path.exists():
                    local_path.unlink()
            self.log(f'Script/lisans silindi: {license_id}', 'script')
            self.refresh_generated_list()
            self.refresh_users()
        except Exception as e:
            self.log(f'Silme hata: {e}', 'script')
            messagebox.showerror('Hata', str(e))

    def clear_all_scripts(self):
        if not messagebox.askyesno('Tumunu Temizle', 'Tum scriptler ve lisanslar silinsin mi knk?'):
            return
        errors = []
        rows = list(self.current_rows.values())
        seen = set()
        for row in rows:
            license_id = str((row or {}).get('license_id') or '').strip()
            if not license_id or license_id in seen:
                continue
            seen.add(license_id)
            try:
                res = self.request_json('POST', '/admin/license/delete', {'license_id': license_id}, need_admin=True)
                if not res.get('success'):
                    errors.append(f'{license_id}: {res.get("error") or "silinemedi"}')
            except Exception as e:
                errors.append(f'{license_id}: {e}')
        for path in GENERATED_DIR.glob('*.user.js'):
            try:
                path.unlink()
            except Exception as e:
                errors.append(f'{path.name}: {e}')
        self.refresh_generated_list()
        self.refresh_users(silent=True)
        if errors:
            self.log('Tum temizle bazi hatalarla bitti', 'script')
            messagebox.showwarning('Uyari', 'Bazi scriptler silinemedi knk\n\n' + '\n'.join(errors[:15]))
            return
        self.log('Tum scriptler/lisanslar temizlendi', 'script')
        messagebox.showinfo('Tamam', 'Tum scriptler temizlendi knk')


if __name__ == '__main__':
    root = tk.Tk()
    try:
        ttk.Style().theme_use('clam')
    except Exception:
        pass
    app = SunflowerPanel(root)
    root.mainloop()
