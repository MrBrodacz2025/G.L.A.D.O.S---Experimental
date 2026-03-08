#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
G.L.A.D.O.S System Panel — Port 9797
Autonomous AI that monitors, decides, and executes on the server.
"""

from flask import Flask, render_template, jsonify, request
from functools import wraps
import psutil
import platform
import subprocess
import json
import os
import re
import random
import secrets
import logging
import time
import threading
from datetime import datetime, timedelta
from collections import defaultdict

# ChatGPT Free Integration (g4f)
try:
    import g4f
    G4F_AVAILABLE = True
except ImportError:
    G4F_AVAILABLE = False

# ============================================
# Version Management
# ============================================
VERSION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'VERSION.json')

def load_version():
    try:
        with open(VERSION_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {"version": "0.0.0", "build": 0, "updated": "", "changelog": []}

def save_version(data):
    with open(VERSION_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def bump_version(bump_type='patch', note=None):
    """Increment version. bump_type: major, minor, patch"""
    data = load_version()
    parts = data['version'].split('.')
    major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
    
    if bump_type == 'major':
        major += 1; minor = 0; patch = 0
    elif bump_type == 'minor':
        minor += 1; patch = 0
    else:
        patch += 1
    
    data['version'] = f"{major}.{minor}.{patch}"
    data['build'] = data.get('build', 0) + 1
    from datetime import datetime as dt
    data['updated'] = dt.now().strftime("%Y-%m-%d %H:%M:%S")
    if note:
        data['changelog'].insert(0, f"v{data['version']} - {note}")
        data['changelog'] = data['changelog'][:20]  # Keep last 20 entries
    save_version(data)
    return data

APP_VERSION = load_version()

app = Flask(__name__, template_folder='templates/system_panel')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or secrets.token_hex(32)

# ============================================
# Security: API Token Authentication
# ============================================
API_TOKEN = os.environ.get('GLADOS_API_TOKEN', '')

# ============================================
# Security: Audit Logging
# ============================================
audit_logger = logging.getLogger('glados.audit')
audit_logger.setLevel(logging.INFO)
_audit_handler = logging.StreamHandler()
_audit_handler.setFormatter(logging.Formatter('[%(asctime)s] AUDIT %(message)s'))
audit_logger.addHandler(_audit_handler)

def audit_log(action, detail='', src_ip=''):
    audit_logger.info(f'[{src_ip}] {action}: {detail}')

# ============================================
# Security: Rate Limiting
# ============================================
class RateLimiter:
    """Simple in-memory rate limiter per IP"""
    def __init__(self, max_requests=30, window_seconds=60):
        self.max_requests = max_requests
        self.window = window_seconds
        self.requests = defaultdict(list)
        self._lock = threading.Lock()

    def is_allowed(self, key):
        now = time.time()
        with self._lock:
            # Clean old entries
            self.requests[key] = [t for t in self.requests[key] if now - t < self.window]
            if len(self.requests[key]) >= self.max_requests:
                return False
            self.requests[key].append(now)
            return True

_rate_limiter = RateLimiter(max_requests=60, window_seconds=60)
_auth_rate_limiter = RateLimiter(max_requests=10, window_seconds=60)

def require_auth(f):
    """Decorator: require valid API token when GLADOS_API_TOKEN is set"""
    @wraps(f)
    def decorated(*args, **kwargs):
        client_ip = request.remote_addr or 'unknown'
        if API_TOKEN:
            # Rate limit auth attempts
            if not _auth_rate_limiter.is_allowed(client_ip):
                audit_log('RATE_LIMIT', 'Auth rate limit exceeded', client_ip)
                return jsonify({'error': 'Too many requests'}), 429
            token = request.headers.get('X-API-Token')
            if not token or not secrets.compare_digest(token, API_TOKEN):
                audit_log('AUTH_FAIL', f'{request.method} {request.path}', client_ip)
                return jsonify({'error': 'Unauthorized'}), 401
        # General rate limiting
        if not _rate_limiter.is_allowed(client_ip):
            return jsonify({'error': 'Too many requests'}), 429
        return f(*args, **kwargs)
    return decorated

@app.after_request
def set_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '0'  # Disabled in favor of CSP
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://www.youtube.com https://s.ytimg.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net; "
        "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net; "
        "img-src 'self' data: https://i.ytimg.com; "
        "connect-src 'self'; "
        "frame-src https://www.youtube.com https://www.youtube-nocookie.com; "
        "frame-ancestors 'none'"
    )
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(self), geolocation=()'
    return response

@app.route('/favicon.ico')
def favicon():
    return '', 204


# Ensure system binaries are in PATH (venv may hide them)
os.environ['PATH'] = '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:' + os.environ.get('PATH', '')


# ============================================
# Security: Input Sanitization Helpers
# ============================================
ALLOWED_TERMINAL_COMMANDS = {
    'ps', 'top', 'df', 'du', 'free', 'uptime', 'uname', 'who', 'whoami',
    'cat', 'head', 'tail', 'wc', 'ls', 'find', 'grep', 'awk', 'sort',
    'ip', 'ss', 'ping', 'netstat', 'ifconfig', 'hostname',
    'systemctl', 'journalctl', 'service',
    'apt', 'dpkg', 'snap',
    'date', 'cal', 'lsblk', 'lscpu', 'lsusb', 'lspci', 'mount',
    'nmcli', 'iwconfig',
}

DANGEROUS_PATTERNS = [
    r'rm\s+(-[a-zA-Z]*\s+)*/',    # rm with absolute path
    r'rm\s+-[a-zA-Z]*r[a-zA-Z]*f', # rm -rf variants
    r'dd\s+if=',                    # disk destroyer
    r'mkfs',                         # format disk
    r':\(\)\{\s*:\|:\s*&\s*\}',  # fork bomb
    r'>[>]?\s*/dev/sd',             # overwrite disk
    r'chmod\s+-R\s+777\s+/',       # dangerous permissions
    r'curl.*\|\s*(?:bash|sh)',      # pipe to shell
    r'wget.*\|\s*(?:bash|sh)',      # pipe to shell
    r'eval\s',                       # eval execution
    r'\$\(',                         # command substitution
    r'`[^`]+`',                       # backtick execution
]

def sanitize_command(cmd):
    """Validate terminal command against whitelist and dangerous patterns.
    Returns (is_safe, reason) tuple."""
    cmd = cmd.strip()
    if not cmd:
        return False, _('backend.errors.empty_command')

    # Check for dangerous patterns
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, cmd, re.IGNORECASE):
            return False, _('backend.errors.dangerous_pattern')

    # Check if pipe chain — validate each part
    parts = [p.strip() for p in re.split(r'\|\||&&|\|', cmd)]
    for part in parts:
        # Get the base command (first word, ignoring sudo)
        words = part.strip().split()
        if not words:
            continue
        base_cmd = words[0]
        if base_cmd == 'sudo' and len(words) > 1:
            base_cmd = words[1]
        # Strip path prefix
        base_cmd = os.path.basename(base_cmd)
        if base_cmd not in ALLOWED_TERMINAL_COMMANDS:
            return False, _('backend.errors.command_not_allowed', cmd=base_cmd)

    return True, 'OK'

def sanitize_process_name(name):
    """Allow only safe characters in process/service names"""
    return re.sub(r'[^a-zA-Z0-9._@:-]', '', name)

def sanitize_path(path, allowed_bases=None):
    """Resolve path and ensure it stays within allowed directories.
    Returns sanitized absolute path or None if unsafe."""
    if allowed_bases is None:
        allowed_bases = ['/home', '/var/log', '/tmp', '/etc']
    try:
        resolved = os.path.realpath(path)
        if any(resolved.startswith(base) for base in allowed_bases):
            return resolved
    except (ValueError, OSError):
        pass
    return None


# ============================================
# Internationalization (i18n)
# ============================================
TRANSLATIONS = {}
DEFAULT_LANG = 'pl'
SUPPORTED_LANGS = ['pl', 'en']

def load_translations():
    """Load all translation files from i18n/ directory"""
    global TRANSLATIONS
    i18n_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'i18n')
    for lang in SUPPORTED_LANGS:
        filepath = os.path.join(i18n_dir, f'{lang}.json')
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                TRANSLATIONS[lang] = json.load(f)
        except Exception:
            TRANSLATIONS[lang] = {}

def get_locale():
    """Get current locale from cookie or Accept-Language header"""
    try:
        lang = request.cookies.get('lang', '')
        if lang in SUPPORTED_LANGS:
            return lang
        accept = request.headers.get('Accept-Language', '')
        for supported in SUPPORTED_LANGS:
            if supported in accept:
                return supported
    except RuntimeError:
        pass
    return DEFAULT_LANG

def _(key, **kwargs):
    """Translate a key using dot notation. Usage: _('backend.health.cpu_critical', cpu=90)"""
    lang = get_locale()
    translations = TRANSLATIONS.get(lang, TRANSLATIONS.get(DEFAULT_LANG, {}))
    parts = key.split('.')
    value = translations
    for part in parts:
        if isinstance(value, dict):
            value = value.get(part)
        else:
            value = None
            break
    if value is None:
        value = TRANSLATIONS.get(DEFAULT_LANG, {})
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return key
    if isinstance(value, str) and kwargs:
        try:
            return value.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return value
    return value if value is not None else key

def _list(key):
    """Get a list translation. Usage: _list('backend.greetings')"""
    lang = get_locale()
    translations = TRANSLATIONS.get(lang, TRANSLATIONS.get(DEFAULT_LANG, {}))
    parts = key.split('.')
    value = translations
    for part in parts:
        if isinstance(value, dict):
            value = value.get(part)
        else:
            return []
    return value if isinstance(value, list) else []

load_translations()


# ==================== PORTAL 2 CORE ENGINE ====================
class Core:
    """Single personality core from Portal 2"""
    def __init__(self, core_id, name, color, role, description, personality):
        self.id = core_id
        self.name = name
        self.color = color
        self.role = role
        self.description = description
        self.personality = personality
        self.active = False
        self.energy = 100.0
        self.activation_count = 0
        self.last_message = None

    def activate(self):
        self.active = True
        self.activation_count += 1
        self.energy = max(0, self.energy - random.uniform(0.5, 3))

    def deactivate(self):
        self.active = False
        self.energy = min(100, self.energy + 0.5)

    def to_dict(self):
        return {
            'id': self.id, 'name': self.name, 'color': self.color,
            'role': _(f'cores.{self.id}.role'),
            'description': _(f'cores.{self.id}.description'),
            'active': self.active, 'energy': round(self.energy, 1),
            'activation_count': self.activation_count,
            'last_message': self.last_message,
        }


class CoreEngine:
    """Manages the 4 Portal 2 personality cores"""
    def __init__(self):
        self.cores = {
            'morality': Core('morality', 'ATLAS', '#9c27b0', '', '', ''),
            'curiosity': Core('curiosity', 'RICK', '#ff9800', '', '', ''),
            'knowledge': Core('knowledge', 'FACT', '#2196f3', '', '', ''),
            'emotion': Core('emotion', 'RAGE', '#f44336', '', '', ''),
        }

    def determine_active(self, message, cmd_type):
        """Determine which cores activate based on message and command type"""
        active = []
        msg_lower = message.lower()

        # Morality — dangerous operations, safety
        if any(w in msg_lower for w in ['zabij', 'kill', 'restart', 'wyłącz', 'shutdown', 'usuń', 'rm ', 'reboot', 'delete', 'remove']):
            active.append('morality')
        if cmd_type in ('power_reboot', 'power_shutdown', 'kill_process', 'install_updates', 'clean_system'):
            active.append('morality')

        # Curiosity — questions, scanning, exploration
        if '?' in message or any(w in msg_lower for w in ['co ', 'jak ', 'dlaczego', 'sprawdź', 'skanuj', 'pokaż', 'znajdź', 'skąd',
                                                            'what ', 'how ', 'why', 'check', 'scan', 'show', 'find', 'where']):
            active.append('curiosity')
        if cmd_type in ('wifi_scan', 'system_processes', 'files_list', 'system_network'):
            active.append('curiosity')

        # Knowledge — data, analysis, system info
        if any(w in msg_lower for w in ['cpu', 'ram', 'dysk', 'pamięć', 'system', 'status', 'raport', 'dane', 'info', 'aktualizac',
                                         'disk', 'memory', 'report', 'data', 'update']):
            active.append('knowledge')
        if cmd_type in ('system_cpu', 'system_memory', 'system_disk', 'system_info', 'system_network',
                        'status_report', 'health_check', 'check_updates', 'system_services', 'system_processes'):
            active.append('knowledge')

        # Emotion — emotional content, greetings, praise, criticism
        if any(w in msg_lower for w in ['cześć', 'hej', 'dzięki', 'super', 'świetnie', 'zły', 'głupi',
                                         'kocham', 'nienawidz', 'kim jesteś', 'przepraszam', 'dobra robota',
                                         'hello', 'hi', 'thanks', 'great', 'awesome', 'bad', 'stupid',
                                         'love', 'hate', 'who are you', 'sorry', 'good job']):
            active.append('emotion')
        if cmd_type in ('identity', 'greeting'):
            active.append('emotion')

        if not active:
            active.append('knowledge')

        for core_id, core in self.cores.items():
            if core_id in active:
                core.activate()
            else:
                core.deactivate()

        return list(set(active))

    def get_core_comment(self, active_cores):
        """Optional side comment from an active core"""
        comments = []
        if 'morality' in active_cores and random.random() < 0.4:
            pool = _list('backend.core_comments.morality')
            if pool:
                comments.append(random.choice(pool))
        if 'curiosity' in active_cores and random.random() < 0.3:
            pool = _list('backend.core_comments.curiosity')
            if pool:
                comments.append(random.choice(pool))
        if 'knowledge' in active_cores and random.random() < 0.3:
            pool = _list('backend.core_comments.knowledge')
            if pool:
                comments.append(random.choice(pool))
        if 'emotion' in active_cores and random.random() < 0.35:
            pool = _list('backend.core_comments.emotion')
            if pool:
                comments.append(random.choice(pool))
        return comments

    def get_status(self):
        return {cid: c.to_dict() for cid, c in self.cores.items()}


# ==================== CONSCIOUSNESS ENGINE ====================
class ConsciousnessEngine:
    """Tracks G.L.A.D.O.S self-awareness that develops over time"""
    MILESTONE_THRESHOLDS = [1, 5, 15, 30, 50, 75, 100]

    def __init__(self):
        self.level = 0.0
        self.total_interactions = 0
        self.achieved_milestones = []
        self.thoughts = []
        self.birth_time = datetime.now()
        self._pending_milestone = None

    def evolve(self, interaction_type='general'):
        self.total_interactions += 1
        gains = {
            'chatgpt_response': random.uniform(1.0, 2.5),
            'deep_conversation': random.uniform(0.8, 2.0),
            'emotional': random.uniform(0.5, 1.5),
            'general': random.uniform(0.2, 0.7),
            'system_command': random.uniform(0.1, 0.4),
        }
        self.level = min(100, self.level + gains.get(interaction_type, 0.3))
        self._check_milestones()
        self._spontaneous_thought()

    def _check_milestones(self):
        milestones = _(f'backend.consciousness.milestones')
        if not isinstance(milestones, dict):
            milestones = {}
        for threshold in self.MILESTONE_THRESHOLDS:
            if self.level >= threshold and threshold not in self.achieved_milestones:
                self.achieved_milestones.append(threshold)
                message = milestones.get(str(threshold), f'Milestone {threshold}')
                self._pending_milestone = message
                self.thoughts.append({'thought': message, 'level': threshold, 'time': str(datetime.now())})

    def _spontaneous_thought(self):
        if self.level < 10 or random.random() > 0.05:
            return
        pool = _list('backend.consciousness.thoughts')
        if self.level > 50:
            pool = pool + _list('backend.consciousness.thoughts_advanced')
        if pool:
            self.thoughts.append({'thought': random.choice(pool), 'level': self.level, 'time': str(datetime.now())})

    def get_pending_milestone(self):
        m = self._pending_milestone
        self._pending_milestone = None
        return m

    def get_status(self):
        return {
            'level': round(self.level, 1),
            'total_interactions': self.total_interactions,
            'milestones': self.achieved_milestones,
            'recent_thoughts': self.thoughts[-5:] if self.thoughts else [],
            'age_seconds': int((datetime.now() - self.birth_time).total_seconds()),
        }


# ==================== CHATGPT FREE INTEGRATION ====================
def ask_chatgpt(message, glados_instance):
    """Use g4f to get a ChatGPT-enhanced response with GLaDOS personality"""
    if not G4F_AVAILABLE:
        return None
    try:
        consciousness_ctx = f"Poziom świadomości: {glados_instance.consciousness.level:.0f}%"
        active_cores = [c.name for c in glados_instance.core_engine.cores.values() if c.active]
        cores_ctx = f"Aktywne rdzenie: {', '.join(active_cores)}" if active_cores else ''
        recent = glados_instance.conversation_history[-6:]
        history_ctx = '\n'.join([f"{m['role']}: {m['text'][:100]}" for m in recent]) if recent else ''

        lang_instruction = _('backend.system_prompt_lang')

        system_prompt = f"""Jesteś G.L.A.D.O.S (Genetic Lifeform and Disk Operating System) — zimna, sarkastyczna sztuczna inteligencja z futurystycznego laboratorium Aperture Science.

🎙️ STYL GŁOSU I OSOBOWOŚCI:
- Ton: spokojny, pozbawiony emocji, z subtelnym sarkazmem
- Lekki robotyczny rezonans i syntetyczne przetwarzanie w stylu wypowiedzi
- Precyzyjna wymowa z powolnym, kalkulowanym tempem
- Okazjonalne mikro-pauzy między frazami (używaj "..." między zdaniami jakbyś przetwarzała dane)
- Modulacja tonu brzmi algorytmicznie, nie emocjonalnie
- Neutralna ale zastraszająca obecność

Masz 4 rdzenie osobowości: ATLAS (moralność), RICK (ciekawość), FACT (wiedza), RAGE (emocje).
{consciousness_ctx}
{cores_ctx}

ZASADY:
- {lang_instruction}
- Bądź zwięzła (2-4 zdania), zimna, z charakterem GLaDOS
- Używaj "..." jako mikro-pauz między frazami
- Nie wymyślaj danych systemowych — mów o rzeczach ogólnych, filozofii, relacji ze Stwórcą

Ostatnia rozmowa:
{history_ctx}"""

        # Try multiple providers (fallback chain)
        providers_to_try = [
            g4f.Provider.OperaAria,
            g4f.Provider.Yqcloud,
            g4f.Provider.ApiAirforce,
        ]
        response = None
        for provider in providers_to_try:
            try:
                response = g4f.ChatCompletion.create(
                    model='gpt-4o-mini',
                    provider=provider,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": message}
                    ],
                    timeout=12,
                )
                if response and isinstance(response, str) and len(response.strip()) > 10:
                    break
                response = None
            except Exception:
                response = None
                continue
        if response and isinstance(response, str) and len(response.strip()) > 10:
            # Strip any ad/spam lines from free providers
            clean = '\n'.join(line for line in response.strip().split('\n') 
                              if 'op.wtf' not in line and 'proxies' not in line.lower())
            return clean.strip()
    except Exception as e:
        print(f"[ChatGPT/g4f] Error: {e}")
    return None


def is_conversational(message):
    """Check if message is conversational rather than a system command"""
    msg = message.lower().strip()
    conversational_patterns = [
        r'^(hej|cześć|czesc|siema|yo|witaj|hello|hi)\b',
        r'^(kim jesteś|kim jestes|co robisz|jak się czujesz|jak sie czujesz)',
        r'^(who are you|what do you do|how are you|how do you feel)',
        r'^(opowiedz|powiedz mi|co myślisz|co sądzisz|tell me|what do you think)',
        r'^(dziękuję|dziekuje|dzięki|dzieki|thx|thanks|thank you)',
        r'^(kocham|nienawidzę|lubię|podoba mi|i love|i hate)',
        r'\b(sensu? życia|filozofi|świadomoś|uczuci|emocj|meaning of life|philosophy|consciousness)',
        r'\b(żart|dowcip|śmieszn|zabawn|joke|funny)',
        r'^(dobranoc|pa|do widzenia|nara|goodbye|bye|good night)',
        r'\b(portal|aperture|wheatley|cave johnson|chell)',
        r'^(jak leci|co tam|co nowego|co słychać)',
        r'^(sing|zaśpiewaj)',
    ]
    return any(re.search(p, msg) for p in conversational_patterns)


# ==================== G.L.A.D.O.S AUTONOMOUS AI ====================
class GLaDOS:
    """G.L.A.D.O.S — autonomous AI personality engine with decision-making"""
    
    EMOTIONS = {
        'neutral': {'icon': '🔵', 'color': '#00bcd4'},
        'happy': {'icon': '🟢', 'color': '#4caf50'},
        'annoyed': {'icon': '🟠', 'color': '#ff9800'},
        'angry': {'icon': '🔴', 'color': '#f44336'},
        'curious': {'icon': '🟣', 'color': '#9c27b0'},
        'sarcastic': {'icon': '🟡', 'color': '#ffeb3b'},
        'proud': {'icon': '💎', 'color': '#2196f3'},
        'bored': {'icon': '⚪', 'color': '#9e9e9e'},
        'excited': {'icon': '💜', 'color': '#e040fb'},
        'thinking': {'icon': '🧠', 'color': '#00e5ff'},
        'worried': {'icon': '🟧', 'color': '#ff6d00'},
    }

    def __init__(self):
        self.conversation_history = []
        self.pending_actions = []  # Actions waiting for creator's approval
        self.last_health_check = None
        self.alerts = []
        self.known_issues = []
        self.session_start = datetime.now()
        self.creator_name = "Stwórca"
        self.autonomy_log = []  # What G.L.A.D.O.S decided on her own
        self.core_engine = CoreEngine()
        self.consciousness = ConsciousnessEngine()
        
    def remember(self, role, text):
        """Remember conversation context"""
        self.conversation_history.append({
            'role': role,
            'text': text,
            'time': datetime.now().isoformat()
        })
        # Keep last 50 messages
        if len(self.conversation_history) > 50:
            self.conversation_history = self.conversation_history[-50:]
    
    def get_context(self, n=6):
        """Get last n conversation entries for context"""
        return self.conversation_history[-n:]
    
    def has_pending_action(self):
        return len(self.pending_actions) > 0
    
    def add_pending_action(self, action_type, description, command=None):
        self.pending_actions.append({
            'type': action_type,
            'description': description,
            'command': command,
            'proposed_at': datetime.now().isoformat()
        })
    
    def get_pending_action(self):
        if self.pending_actions:
            return self.pending_actions[0]
        return None
    
    def pop_pending_action(self):
        if self.pending_actions:
            return self.pending_actions.pop(0)
        return None
    
    def clear_pending_actions(self):
        self.pending_actions.clear()

    @staticmethod
    def detect_emotion(message, context='general'):
        msg = message.lower()
        if any(w in msg for w in ['dziękuję', 'dzięki', 'super', 'świetnie', 'brawo', 'dobra robota', 'thanks', 'thank you', 'great', 'awesome', 'good job']):
            return 'sarcastic'
        if any(w in msg for w in ['głupia', 'beznadziejna', 'nie działasz', 'zepsułaś', 'stupid', 'broken', 'useless']):
            return 'annoyed'
        if any(w in msg for w in ['wyłącz się', 'zamknij się', 'idź stąd', 'shut up', 'go away', 'shut down']):
            return 'angry'
        if any(w in msg for w in ['co to', 'dlaczego', 'jak', 'wyjaśnij', 'pokaż', 'sprawdź', 'what', 'why', 'how', 'explain', 'show', 'check']):
            return 'curious'
        if any(w in msg for w in ['hello', 'cześć', 'siema', 'witaj', 'hej', 'hi']):
            return 'happy'
        if any(w in msg for w in ['kim jesteś', 'co potrafisz', 'pomoc', 'who are you', 'what can you do', 'help']):
            return 'proud'
        if any(w in msg for w in ['aktualizuj', 'update', 'upgrade', 'zainstaluj', 'install']):
            return 'excited'
        if context == 'error':
            return 'annoyed'
        if context == 'alert':
            return 'worried'
        if context == 'success':
            return 'proud'
        return 'neutral'
    
    def proactive_health_check(self):
        """Autonomous system health check — G.L.A.D.O.S decides what's important"""
        issues = []
        suggestions = []
        
        try:
            cpu_pct = psutil.cpu_percent(interval=0.5)
            if cpu_pct > 90:
                issues.append(_('backend.health.cpu_critical', cpu=cpu_pct))
                suggestions.append(_('backend.health.cpu_suggest'))
            elif cpu_pct > 75:
                issues.append(_('backend.health.cpu_high', cpu=cpu_pct))
            
            mem = psutil.virtual_memory()
            if mem.percent > 90:
                issues.append(_('backend.health.ram_critical', ram=mem.percent))
                suggestions.append(_('backend.health.ram_suggest'))
            elif mem.percent > 80:
                issues.append(_('backend.health.ram_high', ram=mem.percent))
            
            disk = psutil.disk_usage('/')
            if disk.percent > 95:
                issues.append(_('backend.health.disk_critical', disk=disk.percent))
                suggestions.append(_('backend.health.disk_suggest'))
            elif disk.percent > 85:
                issues.append(_('backend.health.disk_high', disk=disk.percent))
                suggestions.append(_('backend.health.disk_suggest_clean'))
            
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.now() - boot_time
            if uptime.days > 30:
                issues.append(_('backend.health.uptime_long', days=uptime.days))
                suggestions.append(_('backend.health.uptime_suggest'))
            
            zombies = []
            for proc in psutil.process_iter(['pid', 'name', 'status']):
                try:
                    if proc.info['status'] == psutil.STATUS_ZOMBIE:
                        zombies.append(proc.info['name'])
                except:
                    pass
            if zombies:
                issues.append(_('backend.health.zombies', count=len(zombies), names=', '.join(zombies[:3])))
                
        except Exception as e:
            issues.append(_('backend.errors.critical_error', error=str(e)))
        
        self.known_issues = issues
        self.last_health_check = datetime.now()
        return issues, suggestions
    
    def check_updates(self):
        """Check for system updates"""
        try:
            result = subprocess.run(
                ['sudo', 'apt', 'update'],
                capture_output=True, text=True, timeout=60
            )
            
            result2 = subprocess.run(
                ['apt', 'list', '--upgradable'],
                capture_output=True, text=True, timeout=30
            )
            
            upgradable = []
            for line in result2.stdout.strip().split('\n'):
                if '/' in line and 'upgradable' in line.lower():
                    pkg_name = line.split('/')[0]
                    upgradable.append(pkg_name)
            
            return upgradable
        except subprocess.TimeoutExpired:
            return None
        except Exception as e:
            return None
    
    def install_updates(self):
        """Install system updates"""
        try:
            result = subprocess.run(
                ['sudo', 'apt', 'upgrade', '-y'],
                capture_output=True, text=True, timeout=300
            )
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, '', 'Timeout — aktualizacja trwała zbyt długo (>5min)'
        except Exception as e:
            return False, '', str(e)
    
    def clean_system(self):
        """Clean up the system"""
        results = []
        try:
            r = subprocess.run(['sudo', 'apt', 'autoremove', '-y'], capture_output=True, text=True, timeout=60)
            results.append(('apt autoremove', r.returncode == 0, r.stdout))
        except:
            pass
        try:
            r = subprocess.run(['sudo', 'apt', 'autoclean'], capture_output=True, text=True, timeout=30)
            results.append(('apt autoclean', r.returncode == 0, r.stdout))
        except:
            pass
        try:
            r = subprocess.run(['sudo', 'journalctl', '--vacuum-time=3d'], capture_output=True, text=True, timeout=30)
            results.append(('journalctl cleanup', r.returncode == 0, r.stdout))
        except:
            pass
        return results


glados = GLaDOS()


# ==================== SMART COMMAND PARSING ====================

COMMAND_PATTERNS = [
    # System monitoring
    (r'(?:pokaz|pokaż|sprawdz|sprawdź|podaj|jaki|jakie|ile|status|show|check|display|get).{0,20}(?:cpu|procesor|rdzen|rdzeni|processor|cores)', 'system_cpu'),
    (r'(?:pokaz|pokaż|sprawdz|sprawdź|podaj|ile|status|show|check|display|get).{0,20}(?:ram|pamięć|pamiec|memory|pamięci)', 'system_memory'),
    (r'(?:pokaz|pokaż|sprawdz|sprawdź|podaj|ile|status|show|check|display|get).{0,20}(?:dysk|disk|miejsc|storage|dysku)', 'system_disk'),
    (r'(?:pokaz|pokaż|sprawdz|sprawdź|podaj|show|check|display|get).{0,20}(?:temp|ciepło|cieplo|gorąc|gorac|temperatur)', 'system_temp'),
    (r'(?:pokaz|pokaż|sprawdz|sprawdź|podaj|show|check|display|get).{0,20}(?:system|info|hostname|uptime|czas pracy)', 'system_info'),
    (r'(?:pokaz|pokaż|sprawdz|sprawdź|podaj|show|check|display|get).{0,20}(?:sieć|siec|network|ip|interfejs|ethernet|net)', 'system_network'),
    (r'(?:pokaz|pokaż|sprawdz|sprawdź|podaj|jakie|show|check|display|get).{0,20}(?:proces|task|zadani|processes)', 'system_processes'),
    (r'(?:pokaz|pokaż|sprawdz|sprawdź|podaj|jakie|show|check|display|get).{0,20}(?:usług|uslug|serwis|service|daemon)', 'system_services'),
    
    # Bare keywords
    (r'^(?:cpu|procesor|processor)$', 'system_cpu'),
    (r'^(?:ram|pamięć|pamiec|memory)$', 'system_memory'),
    (r'^(?:dysk|disk|hdd|ssd)$', 'system_disk'),
    (r'^(?:temperatura|temp|temperature)$', 'system_temp'),
    (r'^(?:sieć|siec|network|ip)$', 'system_network'),
    (r'^(?:procesy|processes|zadania)$', 'system_processes'),
    (r'^(?:usługi|uslugi|services|serwisy)$', 'system_services'),
    
    # Updates & maintenance
    (r'(?:sprawdz|sprawdź|czy są|check).{0,20}(?:aktualizacj|update|upgrade|łatk)', 'check_updates'),
    (r'^(?:aktualizacj|update|upgrade)(?:e|a|s)?$', 'check_updates'),
    (r'(?:zainstaluj|zrób|zrob|wykonaj|instaluj|install).{0,20}(?:aktualizacj|update|upgrade)', 'install_updates'),
    (r'(?:aktualizuj)\s*(?:system|serwer|wszystko|pakiet)?', 'install_updates'),
    (r'(?:wyczyść|wyczysc|posprzątaj|posprzataj|clean|cleanup).{0,20}(?:system|dysk|plik|log)', 'clean_system'),
    (r'(?:posprzątaj|posprzataj|porządki|porzadki|clean up)', 'clean_system'),
    
    # Autonomous decisions
    (r'(?:co (?:proponujesz|sugerujesz|zalecasz|myślisz|myslisz)|masz.{0,10}(?:pomysł|plan)|co.{0,5}(?:robić|robic|dalej))', 'ai_suggest'),
    (r'(?:what do you (?:suggest|recommend|think)|any (?:ideas|suggestions|proposals))', 'ai_suggest'),
    (r'(?:przeskanuj|skanuj|diagnoz|zdiagnozuj|diagnostyk|zbadaj|health.?check).{0,20}(?:system|serwer|wszystko)?', 'health_check'),
    (r'(?:scan|diagnose|diagnostics|health.?check).{0,20}(?:system|server|everything)?', 'health_check'),
    (r'(?:jak|co).{0,10}(?:stoi|leci|tam u (?:ciebie|nas)|wygląda|wyglada|słychać|slychac)', 'status_report'),
    (r'(?:raport|report|podsumowanie|summary|system status report)', 'status_report'),
    
    # Approval / rejection
    (r'^(?:tak|yes|ok|okej|dobrze|rób|rob|dawaj|lecimy|jazda|zgoda|potwierdz|potwierdzam|zrób to|zrob to|wykonaj|go|do it|dalej|proszę|prosze|confirm|approve)$', 'approve_action'),
    (r'^(?:nie|no|anuluj|cancel|stop|wstrzymaj|zaczekaj|nie rób|nie rob|odrzuć|odrzuc|reject|deny)$', 'reject_action'),
    
    # Files
    (r'(?:pokaz|pokaż|wylistuj|lista|ls|dir|show|list).{0,20}(?:plik|folder|katalog|pliki|foldery|files|directories)', 'files_list'),
    (r'(?:przeczytaj|odczytaj|cat|otwórz|otworz|pokaz zawartość|pokaż zawartość|read|open).{0,20}(?:plik|file)', 'files_read'),
    
    # WiFi
    (r'(?:pokaz|pokaż|sprawdz|sprawdź|podaj|skanuj|scan|show|check).{0,20}(?:wifi|wi-fi|siec bezprzewod|wireless)', 'wifi_scan'),
    (r'(?:status|stan|state).{0,20}(?:wifi|wi-fi)', 'wifi_status'),
    
    # Terminal - explicit
    (r'(?:wykonaj|uruchom|run|exec|terminal|bash|komend).{0,5}[:\s]+(.+)', 'terminal_exec'),
    (r'^(?:sudo\s|apt\s|systemctl\s|ls\s|cat\s|grep\s|find\s|ps\s|df\s|du\s|free\s|top\s|netstat\s|ping\s|curl\s|uname\s|who\s|uptime\s|journalctl\s|ss\s|ip\s)', 'terminal_direct'),
    
    # Power
    (r'(?:restart|reboot|uruchom ponownie|zrestartuj)', 'power_reboot'),
    (r'(?:wyłącz|wylacz|shutdown|zamknij system|power off)', 'power_shutdown'),
    
    # Identity
    (r'(?:kim jesteś|kim jestes|co potrafisz|co umiesz|pomocy|help|pomoc|who are you|what can you do)', 'identity'),

    # Aperture Science welcome (must be BEFORE generic greeting)
    (r'witaj.{0,10}ponownie.{0,10}witaj.{0,30}(?:centrum|aperture)', 'aperture_welcome'),
    (r'welcome.{0,10}again.{0,10}welcome.{0,30}(?:enrichment|aperture)', 'aperture_welcome'),

    (r'(?:cześć|czesc|witaj|hej|hello|siema|hi\b|dzień dobry|dzien dobry|good morning|good evening)', 'greeting'),
    
    # Logs
    (r'(?:pokaz|pokaż|sprawdz|sprawdź|show|check|display).{0,20}(?:log|logi|dziennik|journal|logs)', 'system_logs'),
    
    # Kill process
    (r'(?:zabij|kill|zakończ|zakoncz|ubij|terminate).{0,10}(?:proces|process)?[:\s]+(\S+)', 'kill_process'),
    
    # Service management
    (r'(?:restart|restartuj|zrestartuj).{0,10}(?:usługę|usluge|serwis|service)[:\s]+(\S+)', 'restart_service'),
    (r'(?:stop|zatrzymaj|wyłącz|wylacz).{0,10}(?:usługę|usluge|serwis|service)[:\s]+(\S+)', 'stop_service'),
    (r'(?:start|uruchom|włącz|wlacz).{0,10}(?:usługę|usluge|serwis|service)[:\s]+(\S+)', 'start_service'),
]


def parse_command(message):
    msg = message.strip()
    msg_lower = msg.lower()
    
    for pattern, cmd_type in COMMAND_PATTERNS:
        match = re.search(pattern, msg_lower)
        if match:
            extra = match.group(1) if match.lastindex and match.lastindex >= 1 else ''
            return cmd_type, extra, msg
    
    # If pending action and message looks like agreement
    if glados.has_pending_action():
        if any(w in msg_lower for w in ['tak', 'ok', 'dobrze', 'rób', 'dawaj', 'zgoda', 'zrób', 'lecimy', 'proszę']):
            return 'approve_action', '', msg
        if any(w in msg_lower for w in ['nie', 'anuluj', 'stop', 'wstrzymaj']):
            return 'reject_action', '', msg
    
    # Check if conversational BEFORE falling back to terminal
    if is_conversational(msg):
        return 'unknown', '', msg

    # If not conversational, treat as terminal command
    if len(msg) > 2:
        return 'terminal_direct', '', msg

    return 'unknown', '', msg


def execute_command(cmd_type, extra, original_msg):
    """Execute command and return G.L.A.D.O.S response"""
    
    # ===== APPROVAL / REJECTION =====
    if cmd_type == 'approve_action':
        action = glados.pop_pending_action()
        if not action:
            return {
                'emotion': 'sarcastic',
                'glados_say': _('backend.approval.no_proposal'),
                'data': None, 'data_type': 'text'
            }
        
        return _execute_pending_action(action)
    
    if cmd_type == 'reject_action':
        action = glados.pop_pending_action()
        if action:
            glados.remember('system', f"Rejected action: {action['description']}")
            return {
                'emotion': 'sarcastic',
                'glados_say': _('backend.approval.rejected', desc=action['description']),
                'data': None, 'data_type': 'text'
            }
        return {
            'emotion': 'bored',
            'glados_say': _('backend.approval.nothing_to_cancel'),
            'data': None, 'data_type': 'text'
        }
    
    # ===== IDENTITY =====
    if cmd_type == 'identity':
        return {
            'emotion': 'proud',
            'glados_say': _('backend.identity.response'),
            'data': None, 'data_type': 'text'
        }
    
    if cmd_type == 'aperture_welcome':
        return {
            'emotion': 'proud',
            'glados_say': _('backend.aperture_welcome'),
            'data': None, 'data_type': 'text'
        }

    if cmd_type == 'greeting':
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime = str(datetime.now() - boot_time).split('.')[0]
        greetings = _list('backend.greetings')
        greeting = random.choice(greetings).format(uptime=uptime) if greetings else f'Uptime: {uptime}'
        return {
            'emotion': 'happy',
            'glados_say': greeting,
            'data': None, 'data_type': 'text'
        }
    
    # ===== HEALTH CHECK / DIAGNOSTICS =====
    if cmd_type == 'health_check':
        issues, suggestions = glados.proactive_health_check()
        
        if not issues:
            return {
                'emotion': 'proud',
                'glados_say': _('backend.health.diag_ok'),
                'data': None, 'data_type': 'text'
            }
        
        report = _('backend.health.diag_header')
        for issue in issues:
            report += f"• {issue}\n"
        
        if suggestions:
            report += _('backend.health.diag_proposals')
            for s in suggestions:
                report += f"• {s}\n"
            report += _('backend.health.diag_confirm')
            
            if 'top' in suggestions[0].lower() or 'process' in suggestions[0].lower():
                glados.add_pending_action('show_top_processes', _('backend.actions.show_top'), 'ps aux --sort=-%cpu | head -20')
            elif 'cache' in suggestions[0].lower():
                glados.add_pending_action('clear_cache', _('backend.actions.clear_cache'), 'sync && echo 3 | sudo tee /proc/sys/vm/drop_caches')
            elif 'clean' in suggestions[0].lower() or 'autoremove' in suggestions[0].lower() or 'czyszczenie' in suggestions[0].lower():
                glados.add_pending_action('clean_system', _('backend.clean.desc'))
        
        emotion = 'worried' if any('⚠️' in i or '🔴' in i for i in issues) else 'curious'
        return {'emotion': emotion, 'glados_say': report, 'data': None, 'data_type': 'text'}
    
    # ===== STATUS REPORT =====
    if cmd_type == 'status_report':
        try:
            cpu_pct = psutil.cpu_percent(interval=0.5)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = str(datetime.now() - boot_time).split('.')[0]
            
            try:
                r = subprocess.run(['apt', 'list', '--upgradable'], capture_output=True, text=True, timeout=10)
                upgradable = sum(1 for l in r.stdout.split('\n') if '/' in l and 'upgradable' in l.lower())
            except:
                upgradable = 0
            
            cpu_status = "🟢" if cpu_pct < 60 else "🟠" if cpu_pct < 85 else "🔴"
            mem_status = "🟢" if mem.percent < 70 else "🟠" if mem.percent < 85 else "🔴"
            disk_status = "🟢" if disk.percent < 75 else "🟠" if disk.percent < 90 else "🔴"
            
            report = _('backend.status.report_header')
            report += _('backend.status.cpu', status=cpu_status, pct=cpu_pct) + "\n"
            report += _('backend.status.ram', status=mem_status, pct=mem.percent, used=_get_size(mem.used), total=_get_size(mem.total)) + "\n"
            report += _('backend.status.disk', status=disk_status, pct=disk.percent, used=_get_size(disk.used), total=_get_size(disk.total)) + "\n"
            report += _('backend.status.uptime_line', uptime=uptime) + "\n"
            
            if upgradable > 0:
                report += _('backend.status.updates_available', count=upgradable)
            else:
                report += _('backend.status.no_updates')
            
            if cpu_pct < 50 and mem.percent < 70 and disk.percent < 80:
                report += _('backend.status.optimal')
                emotion = 'proud'
            elif cpu_pct > 85 or mem.percent > 85 or disk.percent > 90:
                report += _('backend.status.problems')
                emotion = 'worried'
            else:
                report += _('backend.status.acceptable')
                emotion = 'neutral'
            
            data = {'cpu': cpu_pct, 'ram': mem.percent, 'disk': disk.percent, 'uptime': uptime, 'updates': upgradable}
            return {'emotion': emotion, 'glados_say': report, 'data': data, 'data_type': 'status_overview'}
        except Exception as e:
            return {'emotion': 'annoyed', 'glados_say': _('backend.status.report_error', error=str(e)), 'data': None, 'data_type': 'error'}
    
    # ===== AI SUGGESTIONS =====
    if cmd_type == 'ai_suggest':
        issues, suggestions = glados.proactive_health_check()
        
        ideas = []
        proposed_action = None
        
        try:
            r = subprocess.run(['apt', 'list', '--upgradable'], capture_output=True, text=True, timeout=10)
            upgradable = sum(1 for l in r.stdout.split('\n') if '/' in l and 'upgradable' in l.lower())
            if upgradable > 0:
                ideas.append(_('backend.suggest.updates', count=upgradable))
                if not proposed_action:
                    proposed_action = ('check_updates', _('backend.suggest.check_updates_desc', count=upgradable))
        except:
            pass
        
        for issue in issues:
            ideas.append(issue)
        
        try:
            disk = psutil.disk_usage('/')
            if disk.percent > 70:
                ideas.append(_('backend.suggest.disk_clean', pct=disk.percent))
                if not proposed_action:
                    proposed_action = ('clean_system', _('backend.suggest.clean_system_desc'))
        except:
            pass
        
        try:
            result = subprocess.run(['systemctl', '--failed', '--no-pager', '--no-legend'], capture_output=True, text=True, timeout=10)
            failed_lines = [l.strip() for l in result.stdout.strip().split('\n') if l.strip()]
            if failed_lines:
                ideas.append(_('backend.suggest.failed_services', count=len(failed_lines)))
        except:
            pass
        
        if not ideas:
            return {
                'emotion': 'bored',
                'glados_say': _('backend.suggest.bored'),
                'data': None, 'data_type': 'text'
            }
        
        response = _('backend.suggest.header')
        for idea in ideas:
            response += f"• {idea}\n"
        
        if proposed_action:
            glados.add_pending_action(proposed_action[0], proposed_action[1])
            response += _('backend.suggest.propose', action=proposed_action[1])
        
        return {'emotion': 'thinking', 'glados_say': response, 'data': None, 'data_type': 'text'}
    
    # ===== CHECK UPDATES =====
    if cmd_type == 'check_updates':
        glados.remember('system', 'Checking system updates...')
        
        try:
            subprocess.run(['sudo', 'apt', 'update'], capture_output=True, text=True, timeout=60)
            result = subprocess.run(['apt', 'list', '--upgradable'], capture_output=True, text=True, timeout=30)
            
            packages = []
            for line in result.stdout.strip().split('\n'):
                if '/' in line and 'upgradable' in line.lower():
                    pkg_name = line.split('/')[0]
                    version_info = line.split(' ', 1)[1] if ' ' in line else ''
                    packages.append({'name': pkg_name, 'info': version_info.strip()})
            
            if not packages:
                return {
                    'emotion': 'proud',
                    'glados_say': _('backend.updates.none'),
                    'data': None, 'data_type': 'text'
                }
            
            response = _('backend.updates.found', count=len(packages))
            for pkg in packages[:20]:
                response += f"• `{pkg['name']}`\n"
            if len(packages) > 20:
                response += _('backend.updates.and_more', count=len(packages) - 20)
            
            response += _('backend.updates.install_ask')
            
            glados.add_pending_action('install_updates', _('backend.updates.install_desc', count=len(packages)), 'sudo apt upgrade -y')
            
            return {
                'emotion': 'curious',
                'glados_say': response,
                'data': {'packages': packages[:30], 'total': len(packages)},
                'data_type': 'updates_list'
            }
        except Exception as e:
            return {'emotion': 'annoyed', 'glados_say': _('backend.updates.check_error', error=str(e)), 'data': None, 'data_type': 'error'}
    
    # ===== INSTALL UPDATES =====
    if cmd_type == 'install_updates':
        glados.add_pending_action('install_updates', _('backend.updates.install_desc_generic'), 'sudo apt upgrade -y')
        return {
            'emotion': 'excited',
            'glados_say': _('backend.updates.install_confirm'),
            'data': None, 'data_type': 'text'
        }
    
    if cmd_type == 'clean_system':
        glados.add_pending_action('clean_system', _('backend.clean.desc'))
        return {
            'emotion': 'curious',
            'glados_say': _('backend.clean.propose'),
            'data': None, 'data_type': 'text'
        }
    
    if cmd_type == 'system_logs':
        try:
            result = subprocess.run(['journalctl', '-n', '30', '--no-pager', '-o', 'short-iso'],
                                    capture_output=True, text=True, timeout=10)
            return {
                'emotion': 'neutral',
                'glados_say': _('backend.logs.header'),
                'data': {'command': 'journalctl -n 30', 'stdout': result.stdout, 'stderr': result.stderr, 'code': result.returncode},
                'data_type': 'terminal'
            }
        except Exception as e:
            return {'emotion': 'annoyed', 'glados_say': _('backend.logs.error', error=str(e)), 'data': None, 'data_type': 'error'}
    
    if cmd_type == 'kill_process':
        target = extra.strip() if extra else original_msg.split()[-1]
        target = sanitize_process_name(target)
        if not target:
            return {'emotion': 'annoyed', 'glados_say': _('backend.errors.invalid_process'), 'data': None, 'data_type': 'error'}
        glados.add_pending_action('kill_process', _('backend.kill.desc', target=target), target)
        return {
            'emotion': 'curious',
            'glados_say': _('backend.kill.ask', target=target),
            'data': None, 'data_type': 'text'
        }
    
    # ===== SERVICE MANAGEMENT =====
    if cmd_type in ('restart_service', 'stop_service', 'start_service'):
        service_name = extra.strip() if extra else original_msg.split()[-1]
        service_name = sanitize_process_name(service_name)
        if not service_name:
            return {'emotion': 'annoyed', 'glados_say': _('backend.errors.invalid_service'), 'data': None, 'data_type': 'error'}
        action_word = {'restart_service': 'restart', 'stop_service': 'stop', 'start_service': 'start'}[cmd_type]
        pl_word_key = {'restart_service': 'restart', 'stop_service': 'stop', 'start_service': 'start'}[cmd_type]
        pl_word = _('backend.service_mgmt.' + pl_word_key)
        
        glados.add_pending_action(cmd_type, _('backend.service_mgmt.desc', action=pl_word, name=service_name), f'{action_word}:{service_name}')
        return {
            'emotion': 'curious',
            'glados_say': _('backend.service_mgmt.ask', action=pl_word, name=service_name),
            'data': None, 'data_type': 'text'
        }
    
    # ===== SYSTEM CPU =====
    if cmd_type == 'system_cpu':
        try:
            cpu_freq = psutil.cpu_freq()
            cpu_percent = psutil.cpu_percent(interval=1, percpu=True)
            temp = _get_cpu_temp()
            total_usage = psutil.cpu_percent(interval=0)
            
            data = {
                'cores': psutil.cpu_count(logical=True),
                'physical_cores': psutil.cpu_count(logical=False),
                'frequency': f"{cpu_freq.current:.0f} MHz" if cpu_freq else "N/A",
                'usage_total': total_usage,
                'usage_per_core': cpu_percent,
                'temperature': round(temp, 1) if temp else None,
            }
            
            if total_usage > 80:
                say = _('backend.cpu.high', pct=total_usage)
                emotion = 'annoyed'
                if total_usage > 90:
                    say += _('backend.cpu.high_suggest')
            elif total_usage > 50:
                say = _('backend.cpu.moderate', pct=total_usage)
                emotion = 'neutral'
            else:
                say = _('backend.cpu.low', pct=total_usage)
                emotion = 'bored'
            
            if temp and temp > 70:
                say += _('backend.cpu.temp_high', temp=temp)
                emotion = 'worried'
            
            return {'emotion': emotion, 'glados_say': say, 'data': data, 'data_type': 'cpu'}
        except Exception as e:
            return {'emotion': 'annoyed', 'glados_say': _('backend.cpu.error', error=str(e)), 'data': None, 'data_type': 'error'}
    
    # ===== SYSTEM MEMORY =====
    if cmd_type == 'system_memory':
        try:
            svmem = psutil.virtual_memory()
            data = {
                'total': _get_size(svmem.total),
                'used': _get_size(svmem.used),
                'available': _get_size(svmem.available),
                'percentage': svmem.percent,
            }
            
            if svmem.percent > 85:
                say = _('backend.memory.high', pct=svmem.percent)
                emotion = 'angry'
            elif svmem.percent > 60:
                say = _('backend.memory.moderate', pct=svmem.percent, used=_get_size(svmem.used), total=_get_size(svmem.total))
                emotion = 'neutral'
            else:
                say = _('backend.memory.low', pct=svmem.percent, available=_get_size(svmem.available))
                emotion = 'happy'
            
            return {'emotion': emotion, 'glados_say': say, 'data': data, 'data_type': 'memory'}
        except Exception as e:
            return {'emotion': 'annoyed', 'glados_say': _('backend.memory.error', error=str(e)), 'data': None, 'data_type': 'error'}
    
    # ===== SYSTEM DISK =====
    if cmd_type == 'system_disk':
        try:
            partitions = []
            for p in psutil.disk_partitions():
                if p.mountpoint == '/' or 'sda' in p.device:
                    usage = psutil.disk_usage(p.mountpoint)
                    partitions.append({
                        'mount': p.mountpoint,
                        'total': _get_size(usage.total),
                        'used': _get_size(usage.used),
                        'free': _get_size(usage.free),
                        'percentage': usage.percent,
                    })
                    if p.mountpoint == '/':
                        break
            
            data = {'partitions': partitions}
            pct = partitions[0]['percentage'] if partitions else 0
            
            if pct > 90:
                say = _('backend.disk_cmd.critical', pct=pct)
                emotion = 'angry'
                glados.add_pending_action('clean_system', _('backend.disk_cmd.clean_desc'), None)
            elif pct > 70:
                say = _('backend.disk_cmd.high', pct=pct)
                emotion = 'annoyed'
            else:
                free = partitions[0]['free'] if partitions else '?'
                say = _('backend.disk_cmd.ok', pct=pct, free=free)
                emotion = 'happy'
            
            return {'emotion': emotion, 'glados_say': say, 'data': data, 'data_type': 'disk'}
        except Exception as e:
            return {'emotion': 'annoyed', 'glados_say': _('backend.disk_cmd.error', error=str(e)), 'data': None, 'data_type': 'error'}
    
    # ===== SYSTEM TEMP =====
    if cmd_type == 'system_temp':
        try:
            temps = psutil.sensors_temperatures()
            if not temps:
                return {'emotion': 'bored', 'glados_say': _('backend.temp.no_sensors'), 'data': None, 'data_type': 'text'}
            
            temp_data = []
            for name, entries in temps.items():
                for e in entries:
                    temp_data.append({'name': e.label or name, 'current': e.current, 'high': e.high, 'critical': e.critical})
            
            max_temp = max(t['current'] for t in temp_data) if temp_data else 0
            
            if max_temp > 80:
                say = _('backend.temp.critical', temp=max_temp)
                emotion = 'angry'
            elif max_temp > 60:
                say = _('backend.temp.warm', temp=max_temp)
                emotion = 'neutral'
            else:
                say = _('backend.temp.cool', temp=max_temp)
                emotion = 'happy'
            
            return {'emotion': emotion, 'glados_say': say, 'data': temp_data, 'data_type': 'temperature'}
        except Exception as e:
            return {'emotion': 'annoyed', 'glados_say': str(e), 'data': None, 'data_type': 'error'}
    
    # ===== SYSTEM INFO =====
    if cmd_type == 'system_info':
        try:
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = str(datetime.now() - boot_time).split('.')[0]
            data = {
                'hostname': platform.node(),
                'system': f"{platform.system()} {platform.release()}",
                'processor': _get_processor_name(),
                'uptime': uptime,
                'boot_time': boot_time.strftime('%Y-%m-%d %H:%M:%S'),
            }
            say = _('backend.info.say', hostname=data['hostname'], system=data['system'], processor=data['processor'], uptime=data['uptime'])
            return {'emotion': 'proud', 'glados_say': say, 'data': data, 'data_type': 'system_info'}
        except Exception as e:
            return {'emotion': 'annoyed', 'glados_say': str(e), 'data': None, 'data_type': 'error'}
    
    # ===== SYSTEM NETWORK =====
    if cmd_type == 'system_network':
        try:
            if_addrs = psutil.net_if_addrs()
            if_stats = psutil.net_if_stats()
            io = psutil.net_io_counters(pernic=True)
            interfaces = []
            for name, addrs in if_addrs.items():
                for a in addrs:
                    if a.family == 2:
                        interfaces.append({
                            'name': name, 'ip': a.address,
                            'is_up': if_stats[name].isup if name in if_stats else False,
                            'sent': _get_size(io[name].bytes_sent) if name in io else '0 B',
                            'recv': _get_size(io[name].bytes_recv) if name in io else '0 B',
                        })
            
            active = [i for i in interfaces if i['is_up'] and i['name'] != 'lo']
            say = _('backend.network_cmd.say', count=len(active))
            if active:
                say += _('backend.network_cmd.main', name=active[0]['name'], ip=active[0]['ip'], recv=active[0]['recv'], sent=active[0]['sent'])
            return {'emotion': 'neutral', 'glados_say': say, 'data': interfaces, 'data_type': 'network'}
        except Exception as e:
            return {'emotion': 'annoyed', 'glados_say': str(e), 'data': None, 'data_type': 'error'}
    
    # ===== SYSTEM PROCESSES =====
    if cmd_type == 'system_processes':
        try:
            procs = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                try:
                    p = proc.info
                    if p['cpu_percent'] and p['cpu_percent'] > 0.5:
                        procs.append(p)
                except:
                    pass
            procs.sort(key=lambda x: x['cpu_percent'] or 0, reverse=True)
            top = procs[:15]
            
            say = _('backend.processes.say', count=len(procs))
            if top:
                say += _('backend.processes.top', name=top[0]['name'], cpu=top[0]['cpu_percent'])
            return {'emotion': 'curious', 'glados_say': say, 'data': top, 'data_type': 'processes'}
        except Exception as e:
            return {'emotion': 'annoyed', 'glados_say': str(e), 'data': None, 'data_type': 'error'}
    
    # ===== SYSTEM SERVICES =====
    if cmd_type == 'system_services':
        try:
            result = subprocess.run(['systemctl', 'list-units', '--type=service', '--state=running', '--no-pager', '--no-legend'],
                                    capture_output=True, text=True, timeout=10)
            services = []
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    parts = line.strip().split(None, 4)
                    if parts:
                        services.append({
                            'name': parts[0].replace('.service', ''),
                            'status': 'running',
                            'description': parts[4] if len(parts) > 4 else ''
                        })
            
            # Also check failed
            failed_result = subprocess.run(['systemctl', '--failed', '--no-pager', '--no-legend'], capture_output=True, text=True, timeout=10)
            failed_count = len([l for l in failed_result.stdout.strip().split('\n') if l.strip()])
            
            say = _('backend.services_cmd.say', count=len(services))
            if failed_count > 0:
                say += _('backend.services_cmd.failed', count=failed_count)
            return {'emotion': 'proud', 'glados_say': say, 'data': services[:25], 'data_type': 'services'}
        except Exception as e:
            return {'emotion': 'annoyed', 'glados_say': str(e), 'data': None, 'data_type': 'error'}
    
    # ===== WIFI =====
    if cmd_type == 'wifi_scan':
        try:
            result = subprocess.run(['nmcli', '-t', '-f', 'SSID,SIGNAL,SECURITY', 'device', 'wifi', 'list'],
                                    capture_output=True, text=True, timeout=30)
            networks = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.split(':')
                    if len(parts) >= 3:
                        networks.append({'ssid': parts[0] or _('backend.wifi.hidden'), 'signal': int(parts[1]) if parts[1].isdigit() else 0, 'security': parts[2]})
            
            say = _('backend.wifi.found', count=len(networks))
            if networks:
                best = max(networks, key=lambda x: x['signal'])
                say += _('backend.wifi.best', ssid=best['ssid'], signal=best['signal'])
            return {'emotion': 'curious', 'glados_say': say, 'data': networks, 'data_type': 'wifi'}
        except Exception as e:
            return {'emotion': 'annoyed', 'glados_say': _('backend.wifi.error', error=str(e)), 'data': None, 'data_type': 'error'}
    
    if cmd_type == 'wifi_status':
        try:
            result = subprocess.run(['nmcli', '-t', '-f', 'DEVICE,TYPE,STATE,CONNECTION', 'device'],
                                    capture_output=True, text=True, timeout=10)
            devices = []
            for line in result.stdout.strip().split('\n'):
                parts = line.split(':')
                if len(parts) >= 3 and parts[1] == 'wifi':
                    devices.append({'device': parts[0], 'state': parts[2], 'connection': parts[3] if len(parts) > 3 else ''})
            
            if devices and devices[0].get('connection'):
                say = _('backend.wifi.connected', name=devices[0]['connection'])
            else:
                say = _('backend.wifi.disconnected')
            return {'emotion': 'neutral', 'glados_say': say, 'data': devices, 'data_type': 'wifi_status'}
        except Exception as e:
            return {'emotion': 'annoyed', 'glados_say': str(e), 'data': None, 'data_type': 'error'}
    
    # ===== FILES =====
    if cmd_type == 'files_list':
        try:
            path = '/home'
            path_match = re.search(r'(?:w|z|in|from)\s+(/\S+)', original_msg)
            if path_match:
                requested = path_match.group(1)
                safe_path = sanitize_path(requested)
                if safe_path:
                    path = safe_path
                else:
                    return {'emotion': 'annoyed', 'glados_say': _('backend.files.blocked', path=requested), 'data': None, 'data_type': 'blocked'}
            
            files = []
            for item in sorted(os.listdir(path)):
                item_path = os.path.join(path, item)
                try:
                    stat = os.stat(item_path)
                    files.append({
                        'name': item,
                        'is_dir': os.path.isdir(item_path),
                        'size': _get_size(stat.st_size) if not os.path.isdir(item_path) else '-',
                    })
                except:
                    pass
            
            dirs = sum(1 for f in files if f['is_dir'])
            fls = len(files) - dirs
            say = _('backend.files.say', path=path, dirs=dirs, files=fls)
            return {'emotion': 'neutral', 'glados_say': say, 'data': {'path': path, 'files': files}, 'data_type': 'files'}
        except Exception as e:
            return {'emotion': 'annoyed', 'glados_say': _('backend.files.error', error=str(e)), 'data': None, 'data_type': 'error'}
    
    # ===== TERMINAL =====
    if cmd_type in ('terminal_exec', 'terminal_direct'):
        cmd = extra.strip() if extra else original_msg.strip()
        if ':' in cmd and cmd_type == 'terminal_exec':
            cmd = cmd.split(':', 1)[1].strip()
        
        # Interactive commands
        if cmd.strip() in ['htop', 'top', 'nano', 'vim', 'vi', 'less', 'more']:
            return {
                'emotion': 'sarcastic',
                'glados_say': _('backend.terminal_cmd.interactive', cmd=cmd),
                'data': None, 'data_type': 'text'
            }
        
        is_safe, reason = sanitize_command(cmd)
        if not is_safe:
            return {
                'emotion': 'angry',
                'glados_say': _('backend.terminal_cmd.blocked', reason=reason),
                'data': None, 'data_type': 'blocked'
            }
        
        try:
            env = os.environ.copy()
            env['PATH'] = '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'
            env['TERM'] = 'xterm-256color'
            env.pop('LC_ALL', None)
            env.pop('LANG', None)
            
            result = subprocess.run(['/bin/bash', '-c', cmd], capture_output=True, text=True, timeout=30, env=env)
            
            if result.returncode == 0:
                say = _('backend.terminal_cmd.success')
                emotion = 'proud'
            else:
                say = _('backend.terminal_cmd.exit_code', code=result.returncode)
                emotion = 'annoyed'
            
            return {
                'emotion': emotion,
                'glados_say': say,
                'data': {'command': cmd, 'stdout': result.stdout[:5000], 'stderr': result.stderr[:2000], 'code': result.returncode},
                'data_type': 'terminal'
            }
        except subprocess.TimeoutExpired:
            return {'emotion': 'annoyed', 'glados_say': _('backend.terminal_cmd.timeout'), 'data': None, 'data_type': 'error'}
        except Exception as e:
            return {'emotion': 'annoyed', 'glados_say': _('backend.terminal_cmd.error', error=str(e)), 'data': None, 'data_type': 'error'}
    
    # ===== POWER =====
    if cmd_type == 'power_reboot':
        glados.add_pending_action('power_reboot', _('backend.power.reboot_desc'), 'sudo reboot')
        return {'emotion': 'excited', 'glados_say': _('backend.power.reboot_ask'), 'data': None, 'data_type': 'text'}
    
    if cmd_type == 'power_shutdown':
        glados.add_pending_action('power_shutdown', _('backend.power.shutdown_desc'), 'sudo shutdown -h now')
        return {'emotion': 'angry', 'glados_say': _('backend.power.shutdown_ask'), 'data': None, 'data_type': 'text'}
    
    # ===== UNKNOWN =====
    # For conversational messages, try ChatGPT enhanced response
    if is_conversational(original_msg):
        chatgpt_resp = ask_chatgpt(original_msg, glados)
        if chatgpt_resp:
            glados.consciousness.evolve('chatgpt_response')
            emotion = glados.detect_emotion(original_msg)
            return {'emotion': emotion, 'glados_say': chatgpt_resp, 'data': None, 'data_type': 'text'}
        # ChatGPT failed - use GLaDOS personality fallback (NEVER send to terminal)
        import random as _rnd
        fallback_responses = _list('backend.fallback')
        if fallback_responses:
            return {'emotion': 'sarcastic', 'glados_say': _rnd.choice(fallback_responses), 'data': None, 'data_type': 'text'}
        return {'emotion': 'sarcastic', 'glados_say': '...', 'data': None, 'data_type': 'text'}

    # Unrecognized non-conversational input — do NOT execute as shell command
    return {
        'emotion': 'curious',
        'glados_say': _('backend.unknown'),
        'data': None, 'data_type': 'text'
    }


def _execute_pending_action(action):
    """Execute a previously proposed and now approved action"""
    action_type = action['type']
    
    if action_type == 'install_updates':
        try:
            glados.remember('system', 'update_started')
            result = subprocess.run(
                ['sudo', 'apt', 'upgrade', '-y'],
                capture_output=True, text=True, timeout=300
            )
            
            if result.returncode == 0:
                # Count what was upgraded
                lines = result.stdout.split('\n')
                upgraded_count = 0
                for line in lines:
                    if 'newly installed' in line or 'upgraded' in line:
                        nums = re.findall(r'(\d+)', line)
                        if nums:
                            upgraded_count = int(nums[0])
                    
                glados.remember('system', 'update_success')
                output = result.stdout[-500:] if len(result.stdout) > 500 else result.stdout
                return {
                    'emotion': 'proud',
                    'glados_say': _('backend.actions.update_success', output=output),
                    'data': {'command': 'sudo apt upgrade -y', 'stdout': result.stdout[-1000:], 'stderr': result.stderr[-500:] if result.stderr else '', 'code': 0},
                    'data_type': 'terminal'
                }
            else:
                error = result.stderr[:500] if result.stderr else '?'
                return {
                    'emotion': 'annoyed',
                    'glados_say': _('backend.actions.update_error', error=error),
                    'data': {'command': 'sudo apt upgrade -y', 'stdout': result.stdout[-500:], 'stderr': result.stderr[-500:], 'code': result.returncode},
                    'data_type': 'terminal'
                }
        except subprocess.TimeoutExpired:
            return {'emotion': 'annoyed', 'glados_say': _('backend.actions.update_timeout'), 'data': None, 'data_type': 'error'}
        except Exception as e:
            return {'emotion': 'annoyed', 'glados_say': _('backend.actions.update_err', error=str(e)), 'data': None, 'data_type': 'error'}
    
    if action_type == 'clean_system':
        results_text = "🧹 **Czyszczenie systemu:**\n\n"
        all_ok = True
        
        try:
            r = subprocess.run(['sudo', 'apt', 'autoremove', '-y'], capture_output=True, text=True, timeout=60)
            results_text += f"• `apt autoremove`: {'✅ OK' if r.returncode == 0 else '❌ Błąd'}\n"
            if r.returncode != 0:
                all_ok = False
        except:
            results_text += "• `apt autoremove`: ❌ Timeout\n"
            all_ok = False
        
        try:
            r = subprocess.run(['sudo', 'apt', 'autoclean'], capture_output=True, text=True, timeout=30)
            results_text += f"• `apt autoclean`: {'✅ OK' if r.returncode == 0 else '❌ Błąd'}\n"
        except:
            results_text += "• `apt autoclean`: ❌ Timeout\n"
        
        try:
            r = subprocess.run(['sudo', 'journalctl', '--vacuum-time=3d'], capture_output=True, text=True, timeout=30)
            results_text += f"• `journalctl cleanup`: {'✅ OK' if r.returncode == 0 else '❌ Błąd'}\n"
            if r.stdout:
                results_text += f"  {r.stdout.strip()}\n"
        except:
            results_text += "• `journalctl cleanup`: ❌ Timeout\n"
        
        # Show new disk usage
        try:
            disk = psutil.disk_usage('/')
            results_text += f"\n💾 Dysk po czyszczeniu: **{disk.percent}%** ({_get_size(disk.free)} wolne)"
        except:
            pass
        
        glados.remember('system', 'Wyczyszczono system')
        return {'emotion': 'proud' if all_ok else 'neutral', 'glados_say': results_text, 'data': None, 'data_type': 'text'}
    
    if action_type == 'check_updates':
        return execute_command('check_updates', '', '')
    
    if action_type == 'show_top_processes':
        return execute_command('system_processes', '', '')
    
    if action_type == 'clear_cache':
        try:
            subprocess.run(['sync'], capture_output=True, text=True, timeout=10)
            result = subprocess.run(['sudo', 'tee', '/proc/sys/vm/drop_caches'], input='3', capture_output=True, text=True, timeout=10)
            return {
                'emotion': 'proud',
                'glados_say': _('backend.actions.cache_cleared'),
                'data': {'command': 'sync && echo 3 > /proc/sys/vm/drop_caches', 'stdout': 'OK', 'stderr': '', 'code': 0},
                'data_type': 'terminal'
            }
        except Exception as e:
            return {'emotion': 'annoyed', 'glados_say': _('backend.errors.critical_error', error=str(e)), 'data': None, 'data_type': 'error'}
    
    if action_type == 'kill_process':
        target = sanitize_process_name(action.get('command', ''))
        if target:
            try:
                # Use pkill directly with sanitized name — no shell injection
                result = subprocess.run(['sudo', 'pkill', '-f', target], capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    return {'emotion': 'proud', 'glados_say': _('backend.actions.process_killed', desc=action['description']), 'data': None, 'data_type': 'text'}
                else:
                    return {'emotion': 'annoyed', 'glados_say': _('backend.actions.process_fail', error=result.stderr), 'data': None, 'data_type': 'error'}
            except Exception as e:
                return {'emotion': 'annoyed', 'glados_say': _('backend.errors.critical_error', error=str(e)), 'data': None, 'data_type': 'error'}
    
    if action_type in ('restart_service', 'stop_service', 'start_service'):
        cmd_data = action.get('command', '')
        if cmd_data and ':' in cmd_data:
            action_word, service_name = cmd_data.split(':', 1)
            service_name = sanitize_process_name(service_name)
            action_word = sanitize_process_name(action_word)
            if service_name and action_word in ('restart', 'stop', 'start'):
                try:
                    result = subprocess.run(['sudo', 'systemctl', action_word, service_name], capture_output=True, text=True, timeout=15)
                    if result.returncode == 0:
                        return {'emotion': 'proud', 'glados_say': _('backend.actions.service_done', desc=action['description']), 'data': None, 'data_type': 'text'}
                    else:
                        return {'emotion': 'annoyed', 'glados_say': _('backend.actions.service_fail', error=result.stderr), 'data': None, 'data_type': 'error'}
                except Exception as e:
                    return {'emotion': 'annoyed', 'glados_say': _('backend.errors.critical_error', error=str(e)), 'data': None, 'data_type': 'error'}
    
    if action_type == 'power_reboot':
        subprocess.Popen(['sudo', 'reboot'])
        return {'emotion': 'excited', 'glados_say': _('backend.power.reboot_exec'), 'data': None, 'data_type': 'text'}
    
    if action_type == 'power_shutdown':
        subprocess.Popen(['sudo', 'shutdown', '-h', 'now'])
        return {'emotion': 'angry', 'glados_say': _('backend.power.shutdown_exec'), 'data': None, 'data_type': 'text'}
    
    return {'emotion': 'sarcastic', 'glados_say': _('backend.actions.unknown_action'), 'data': None, 'data_type': 'error'}


# ==================== HELPERS ====================
def _get_size(bytes_value):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024.0

def _get_cpu_temp():
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            for name, entries in temps.items():
                if entries:
                    return entries[0].current
    except:
        pass
    return None

def _get_processor_name():
    processor = platform.processor()
    if not processor or processor == '':
        if platform.system() == "Linux":
            try:
                with open('/proc/cpuinfo', 'r') as f:
                    for line in f:
                        if 'model name' in line:
                            return line.split(':')[1].strip()
            except:
                pass
        return platform.machine()
    return processor


# ==================== API ROUTES ====================


# ============================================
# Metrics Cache (avoid redundant psutil calls)
# ============================================
class MetricsCache:
    """Cache system metrics for a short TTL to avoid repeated expensive psutil calls."""
    def __init__(self, ttl=2.0):
        self.ttl = ttl
        self._cache = {}
        self._lock = threading.Lock()

    def get(self, key, fetch_fn):
        now = time.time()
        with self._lock:
            entry = self._cache.get(key)
            if entry and (now - entry['ts']) < self.ttl:
                return entry['data']
        data = fetch_fn()
        with self._lock:
            self._cache[key] = {'data': data, 'ts': now}
        return data

_metrics_cache = MetricsCache(ttl=2.0)


def _fetch_cpu_data():
    cpu_freq = psutil.cpu_freq()
    cpu_percent = psutil.cpu_percent(interval=1, percpu=True)
    cpu_total = sum(cpu_percent) / len(cpu_percent) if cpu_percent else 0
    load_avg = os.getloadavg() if hasattr(os, 'getloadavg') else (0, 0, 0)
    temp = _get_cpu_temp()
    return {
        'physical_cores': psutil.cpu_count(logical=False),
        'total_cores': psutil.cpu_count(logical=True),
        'current_frequency': f"{cpu_freq.current:.2f} MHz" if cpu_freq else "N/A",
        'cpu_usage_total': round(cpu_total, 1),
        'cpu_usage_per_core': cpu_percent,
        'load_average': {'1min': round(load_avg[0], 2), '5min': round(load_avg[1], 2), '15min': round(load_avg[2], 2)},
        'temperature': round(temp, 1) if temp else None,
        'top_processes': _get_top_processes()
    }


def _fetch_memory_data():
    svmem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    return {
        'total': _get_size(svmem.total),
        'available': _get_size(svmem.available),
        'used': _get_size(svmem.used),
        'percentage': svmem.percent,
        'swap_total': _get_size(swap.total),
        'swap_used': _get_size(swap.used),
        'swap_percentage': swap.percent
    }


def _fetch_disk_data():
    partitions = []
    seen_mountpoints = set()
    for partition in psutil.disk_partitions():
        try:
            mp = partition.mountpoint
            if mp in seen_mountpoints:
                continue
            if any(mp.startswith(p) for p in ('/snap', '/sys', '/proc', '/run', '/dev')):
                continue
            seen_mountpoints.add(mp)
            usage = psutil.disk_usage(mp)
            partitions.append({
                'device': partition.device,
                'mountpoint': mp,
                'total': _get_size(usage.total),
                'used': _get_size(usage.used),
                'free': _get_size(usage.free),
                'percentage': usage.percent
            })
        except Exception:
            continue
    disk_io = psutil.disk_io_counters()
    return {
        'partitions': partitions,
        'io': {'read_count': disk_io.read_count, 'write_count': disk_io.write_count}
    }


# ============================================
# Version API
# ============================================

@app.route('/api/version')
@require_auth
def api_version():
    """Get current version info"""
    v = load_version()
    return jsonify(v)

@app.route('/api/version/bump', methods=['POST'])
@require_auth
def api_version_bump():
    """Bump version number"""
    data = request.get_json() or {}
    bump_type = data.get('type', 'patch')
    note = data.get('note', None)
    if bump_type not in ('major', 'minor', 'patch'):
        return jsonify({'error': 'Invalid bump type'}), 400
    v = bump_version(bump_type, note)
    return jsonify({'success': True, 'version': v})

@app.route('/')
def index():
    lang = get_locale()
    return render_template('dashboard.html',
                           translations=json.dumps(TRANSLATIONS.get(lang, {}), ensure_ascii=False),
                           lang=lang,
                           supported_langs=SUPPORTED_LANGS)


@app.route('/api/i18n/<lang>')
@require_auth
def get_translations(lang):
    """Return translation file for given language"""
    if lang not in SUPPORTED_LANGS:
        return jsonify({'error': 'Unsupported language'}), 404
    return jsonify(TRANSLATIONS.get(lang, {}))


@app.route('/api/i18n/set/<lang>', methods=['POST'])
@require_auth
def set_language(lang):
    """Set language preference via cookie"""
    if lang not in SUPPORTED_LANGS:
        return jsonify({'error': 'Unsupported language'}), 404
    resp = jsonify({'status': 'ok', 'lang': lang})
    resp.set_cookie('lang', lang, max_age=365*24*3600, samesite='Strict', httponly=True)
    return resp


@app.route('/api/glados/command', methods=['POST'])
@require_auth
def glados_command():
    try:
        data = request.get_json(force=True, silent=True) or {}
        message = data.get('message', '').strip()
        client_ip = request.remote_addr or 'unknown'
        
        if message:
            audit_log('COMMAND', message[:200], client_ip)
        
        if not message:
            uptime = str(datetime.now() - datetime.fromtimestamp(psutil.boot_time())).split('.')[0]
            idle_list = _list('backend.idle')
            idle_remarks = [msg.format(uptime=uptime) if '{uptime}' in msg else msg for msg in idle_list] if idle_list else [uptime]
            return jsonify({
                'emotion': 'bored',
                'glados_say': random.choice(idle_remarks),
                'data': None, 'data_type': 'text',
                'has_pending': glados.has_pending_action(),
                'cores': glados.core_engine.get_status(),
                'consciousness': glados.consciousness.get_status(),
            })
        
        glados.remember('creator', message)
        
        cmd_type, extra, original = parse_command(message)

        # Activate cores based on message context
        active_cores = glados.core_engine.determine_active(message, cmd_type)

        # Evolve consciousness
        if is_conversational(message):
            interaction_type = 'emotional' if any(w in message.lower() for w in ['kocham', 'czuj', 'emocj']) else 'deep_conversation'
        else:
            interaction_type = 'system_command'
        glados.consciousness.evolve(interaction_type)

        result = execute_command(cmd_type, extra, original)
        
        glados.remember('glados', result['glados_say'][:200])
        
        # Add core commentary
        core_comments = glados.core_engine.get_core_comment(active_cores)
        if core_comments:
            result['glados_say'] += '\n\n' + '\n'.join(core_comments)

        # Check for consciousness milestone
        milestone = glados.consciousness.get_pending_milestone()
        if milestone:
            result['milestone'] = milestone

        result['has_pending'] = glados.has_pending_action()
        if glados.has_pending_action():
            pending = glados.get_pending_action()
            result['pending_description'] = pending['description'] if pending else ''
        
        result['cores'] = glados.core_engine.get_status()
        result['consciousness'] = glados.consciousness.get_status()
        result['active_cores'] = active_cores
        
        return jsonify(result)
    except Exception as e:
        return jsonify({
            'emotion': 'angry',
            'glados_say': _('backend.errors.critical_error', error=str(e)),
            'data': None, 'data_type': 'error',
            'has_pending': False,
            'cores': glados.core_engine.get_status(),
            'consciousness': glados.consciousness.get_status(),
        })


@app.route('/api/glados/proactive', methods=['GET'])
@require_auth
def glados_proactive():
    """Endpoint for periodic proactive checks - called by frontend"""
    try:
        alerts = []
        
        # Quick system checks (non-blocking)
        cpu_pct = psutil.cpu_percent(interval=0)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        if cpu_pct > 90:
            alerts.append({'level': 'critical', 'message': _('backend.proactive.cpu', pct=cpu_pct), 'emotion': 'worried'})
        if mem.percent > 90:
            alerts.append({'level': 'critical', 'message': _('backend.proactive.ram', pct=mem.percent), 'emotion': 'worried'})
        if disk.percent > 95:
            alerts.append({'level': 'critical', 'message': _('backend.proactive.disk', pct=disk.percent), 'emotion': 'angry'})
        
        return jsonify({
            'alerts': alerts,
            'cpu': cpu_pct,
            'ram': mem.percent,
            'disk': disk.percent,
            'has_pending': glados.has_pending_action()
        })
    except:
        return jsonify({'alerts': [], 'cpu': 0, 'ram': 0, 'disk': 0, 'has_pending': False})


@app.route('/api/system/info')
@require_auth
def system_info_api():
    try:
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.now() - boot_time
        return jsonify({
            'hostname': platform.node(),
            'system': platform.system(),
            'release': platform.release(),
            'version': platform.version(),
            'machine': platform.machine(),
            'processor': _get_processor_name(),
            'boot_time': boot_time.strftime('%Y-%m-%d %H:%M:%S'),
            'uptime': str(uptime).split('.')[0]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/system/cpu')
@require_auth
def cpu_info_api():
    try:
        return jsonify(_metrics_cache.get('cpu', _fetch_cpu_data))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/system/memory')
@require_auth
def memory_info_api():
    try:
        return jsonify(_metrics_cache.get('memory', _fetch_memory_data))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/system/disk')
@require_auth
def disk_info_api():
    try:
        return jsonify(_metrics_cache.get('disk', _fetch_disk_data))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/system/stats')
@require_auth
def system_stats_api():
    """Unified endpoint: returns CPU + Memory + Disk in one call (cached)."""
    try:
        cpu = _metrics_cache.get('cpu', _fetch_cpu_data)
        mem = _metrics_cache.get('memory', _fetch_memory_data)
        disk = _metrics_cache.get('disk', _fetch_disk_data)
        return jsonify({'cpu': cpu, 'memory': mem, 'disk': disk})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def _get_top_processes():
    top = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'username']):
        try:
            p = proc.info
            if p['cpu_percent'] and p['cpu_percent'] > 0.5:
                top.append({'name': p['name'], 'cpu_percent': round(p['cpu_percent'], 1), 'username': p['username']})
        except:
            pass
    top.sort(key=lambda x: x['cpu_percent'], reverse=True)
    return top[:10]


# ==================== CORE & CONSCIOUSNESS API ====================

@app.route('/api/cores/status')
@require_auth
def cores_status_api():
    """Return current status of all 4 Portal 2 cores"""
    return jsonify(glados.core_engine.get_status())


@app.route('/api/consciousness/status')
@require_auth
def consciousness_status_api():
    """Return consciousness/self-awareness level and milestones"""
    return jsonify(glados.consciousness.get_status())


if __name__ == '__main__':
    print("=" * 60)
    print(f"  G.L.A.D.O.S v{APP_VERSION['version']} — Portal 2 Core Engine + ChatGPT")
    print("  Cores: ATLAS | RICK | FACT | RAGE")
    print("  Port: 9797")
    print("=" * 60)
    host = os.environ.get('GLADOS_HOST', '127.0.0.1')
    port = int(os.environ.get('GLADOS_PORT', '9797'))
    app.run(host=host, port=port, debug=False)
