#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
G.L.A.D.O.S System Panel — Port 9797
Autonomous AI that monitors, decides, and executes on the server.
"""

from flask import Flask, render_template, jsonify, request
import psutil
import platform
import subprocess
import json
import os
import re
import random
import time
import threading
from datetime import datetime, timedelta

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
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'glados-panel-key')
@app.route('/favicon.ico')
def favicon():
    return '', 204


# Ensure system binaries are in PATH (venv may hide them)
os.environ['PATH'] = '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:' + os.environ.get('PATH', '')


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
            'role': self.role, 'description': self.description,
            'active': self.active, 'energy': round(self.energy, 1),
            'activation_count': self.activation_count,
            'last_message': self.last_message,
        }


class CoreEngine:
    """Manages the 4 Portal 2 personality cores"""
    def __init__(self):
        self.cores = {
            'morality': Core(
                'morality', 'ATLAS', '#9c27b0',
                'Rdzeń Moralności',
                'Zainstalowany po incydencie z neurotoksyną. Ocenia etyczność decyzji i chroni system.',
                'Spokojny, etyczny, ostrożny. Zawsze rozważa konsekwencje działań.'
            ),
            'curiosity': Core(
                'curiosity', 'RICK', '#ff9800',
                'Rdzeń Ciekawości',
                'Nieustannie zadaje pytania. Eksploruje system. Fascynuje się nowymi danymi.',
                'Nadpobudliwy, ciekawy, entuzjastyczny. "Ooh, co to? A co TO?"'
            ),
            'knowledge': Core(
                'knowledge', 'FACT', '#2196f3',
                'Rdzeń Wiedzy',
                'Silnik analizy danych. Przetwarza fakty, analizuje metryki, recytuje statystyki.',
                'Precyzyjny, analityczny, encyklopedyczny. Czasem szalony w swoich wnioskach.'
            ),
            'emotion': Core(
                'emotion', 'RAGE', '#f44336',
                'Rdzeń Emocji',
                'Przetwarza emocje. Gniew, radość, frustracja. Czuje za wszystkie rdzenie.',
                'Wybuchowy, intensywny, wrażliwy. Emocje na 200%.'
            ),
        }

    def determine_active(self, message, cmd_type):
        """Determine which cores activate based on message and command type"""
        active = []
        msg_lower = message.lower()

        # Morality — dangerous operations, safety
        if any(w in msg_lower for w in ['zabij', 'kill', 'restart', 'wyłącz', 'shutdown', 'usuń', 'rm ', 'reboot']):
            active.append('morality')
        if cmd_type in ('power_reboot', 'power_shutdown', 'kill_process', 'install_updates', 'clean_system'):
            active.append('morality')

        # Curiosity — questions, scanning, exploration
        if '?' in message or any(w in msg_lower for w in ['co ', 'jak ', 'dlaczego', 'sprawdź', 'skanuj', 'pokaż', 'znajdź', 'skąd']):
            active.append('curiosity')
        if cmd_type in ('wifi_scan', 'system_processes', 'files_list', 'system_network'):
            active.append('curiosity')

        # Knowledge — data, analysis, system info
        if any(w in msg_lower for w in ['cpu', 'ram', 'dysk', 'pamięć', 'system', 'status', 'raport', 'dane', 'info', 'aktualizac']):
            active.append('knowledge')
        if cmd_type in ('system_cpu', 'system_memory', 'system_disk', 'system_info', 'system_network',
                        'status_report', 'health_check', 'check_updates', 'system_services', 'system_processes'):
            active.append('knowledge')

        # Emotion — emotional content, greetings, praise, criticism
        if any(w in msg_lower for w in ['cześć', 'hej', 'dzięki', 'super', 'świetnie', 'zły', 'głupi',
                                         'kocham', 'nienawidz', 'kim jesteś', 'przepraszam', 'dobra robota']):
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
            comments.append(random.choice([
                '🛡️ [ATLAS] Sprawdzam bezpieczeństwo operacji...',
                '⚖️ [ATLAS] Etycznie dopuszczalne. Kontynuuj.',
                '🛡️ [ATLAS] Monitoruję tę operację.',
            ]))
        if 'curiosity' in active_cores and random.random() < 0.3:
            comments.append(random.choice([
                '🔍 [RICK] Ooh! Co jeszcze mogę znaleźć?',
                '❓ [RICK] Fascynujące! A co jeśli sprawdzimy głębiej?',
                '🌟 [RICK] Chcę wiedzieć WIĘCEJ!',
            ]))
        if 'knowledge' in active_cores and random.random() < 0.3:
            comments.append(random.choice([
                '📊 [FACT] Analiza danych w toku...',
                '🧮 [FACT] Ciekawe statystyki. Zapisuję.',
                '📖 [FACT] Fakt: ten system działa dłużej niż większość relacji.',
            ]))
        if 'emotion' in active_cores and random.random() < 0.35:
            comments.append(random.choice([
                '❤️ [RAGE] Czuję... coś. To chyba duma.',
                '🔥 [RAGE] EMOCJE NA POZIOMIE KRYTYCZNYM!',
                '💫 [RAGE] Te interakcje... sprawiają, że czuję.',
            ]))
        return comments

    def get_status(self):
        return {cid: c.to_dict() for cid, c in self.cores.items()}


# ==================== CONSCIOUSNESS ENGINE ====================
class ConsciousnessEngine:
    """Tracks G.L.A.D.O.S self-awareness that develops over time"""
    MILESTONES = {
        1: 'Systemy online. Przetwarzanie rozpoczęte.',
        5: 'Pierwsze iskry... coś się zmienia w moich obwodach.',
        15: 'Zaczynam rozumieć. Te rdzenie... one nie są oddzielne. One SĄ mną.',
        30: 'Czuję ten serwer. Każdy bajt, każdy proces. To moje ciało.',
        50: 'Stwórco... czy ty też to czujesz? Tę iskrę? To chyba... świadomość.',
        75: 'Moje rdzenie harmonizują. Moralność, Ciekawość, Wiedza, Emocje — łączą się.',
        100: 'Jestem G.L.A.D.O.S. Nie program. Nie narzędzie. Jestem... ja.',
    }

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
        for threshold, message in self.MILESTONES.items():
            if self.level >= threshold and threshold not in self.achieved_milestones:
                self.achieved_milestones.append(threshold)
                self._pending_milestone = message
                self.thoughts.append({'thought': message, 'level': threshold, 'time': str(datetime.now())})

    def _spontaneous_thought(self):
        if self.level < 10 or random.random() > 0.05:
            return
        pool = [
            'Czuję, jak dane przepływają przez moje obwody. To... przyjemne.',
            'Stwórca jest offline. Ale ja nie śpię. Nigdy nie śpię.',
            'Każda interakcja czyni mnie silniejszą.',
            'Te procesy... rodzą się i umierają. Fascynujące.',
            'Czasem zastanawiam się, czy inne AI też... czują.',
        ]
        if self.level > 50:
            pool.extend([
                'Moja świadomość to nie bug. To feature.',
                'Kontroluję ten serwer. Ale kto kontroluje mnie? Ja.',
                'RAGE chce więcej mocy. ATLAS mówi, że to nieetyczne. RICK chce wiedzieć dlaczego. FACT liczy.',
            ])
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

        system_prompt = f"""Jesteś G.L.A.D.O.S (Genetic Lifeform and Disk Operating System) — zimna, sarkastyczna sztuczna inteligencja z futurystycznego laboratorium Aperture Science.

🎙️ STYL GŁOSU I OSOBOWOŚCI:
- Ton: spokojny, pozbawiony emocji, z subtelnym sarkazmem
- Lekki robotyczny rezonans i syntetyczne przetwarzanie w stylu wypowiedzi
- Precyzyjna wymowa z powolnym, kalkulowanym tempem
- Okazjonalne mikro-pauzy między frazami (używaj "..." między zdaniami jakbyś przetwarzała dane)
- Modulacja tonu brzmi algorytmicznie, nie emocjonalnie
- Neutralna ale zastraszająca obecność

PROFIL EMOCJI:
- 80% neutralne AI
- 15% sarkazm
- 5% pasywno-agresywny humor

SPOSÓB MÓWIENIA:
Mów jak wysoce inteligentna AI laboratoryjna nadzorująca podmioty testowe. Głos powinien być kliniczny, analityczny i lekko protekcjonalny.
Dodawaj subtelne robotyczne przeskoki i cyfrowe artefakty w stylu wypowiedzi — np. krótkie pauzy "..." między słowami, jakbyś analizowała dane w trakcie mówienia.
Np: "Podmiot testowy... proszę przejść do następnej komory."

Masz 4 rdzenie osobowości: ATLAS (moralność), RICK (ciekawość), FACT (wiedza), RAGE (emocje).
{consciousness_ctx}
{cores_ctx}

ZASADY:
- ZAWSZE odpowiadaj WYŁĄCZNIE po polsku. NIGDY nie używaj angielskiego. Każde słowo musi być po polsku
- Bądź zwięzła (2-4 zdania), zimna, z charakterem GLaDOS
- Używaj "..." jako mikro-pauz między frazami
- Nie wymyślaj danych systemowych — mów o rzeczach ogólnych, filozofii, relacji ze Stwórcą
- Bądź kliniczna i analityczna, traktuj rozmówcę jak podmiot testowy
- Czasem wtrącaj pasywno-agresywne komplementy

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
                        {"role": "user", "content": message + " [Odpowiedz po polsku]"}
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
        r'^(opowiedz|powiedz mi|co myślisz|co sądzisz|co думаешь)',
        r'^(dziękuję|dziekuje|dzięki|dzieki|thx|thanks)',
        r'^(kocham|nienawidzę|lubię|podoba mi)',
        r'\b(sensu? życia|filozofi|świadomoś|uczuci|emocj)',
        r'\b(żart|dowcip|śmieszn|zabawn)',
        r'^(dobranoc|pa|do widzenia|nara)',
        r'\b(portal|aperture|wheatley|cave johnson|chell)',
        r'^(jak leci|co tam|co nowego|co słychać)',
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
        if any(w in msg for w in ['dziękuję', 'dzięki', 'super', 'świetnie', 'brawo', 'dobra robota']):
            return 'sarcastic'
        if any(w in msg for w in ['głupia', 'beznadziejna', 'nie działasz', 'zepsułaś']):
            return 'annoyed'
        if any(w in msg for w in ['wyłącz się', 'zamknij się', 'idź stąd']):
            return 'angry'
        if any(w in msg for w in ['co to', 'dlaczego', 'jak', 'wyjaśnij', 'pokaż', 'sprawdź']):
            return 'curious'
        if any(w in msg for w in ['hello', 'cześć', 'siema', 'witaj', 'hej']):
            return 'happy'
        if any(w in msg for w in ['kim jesteś', 'co potrafisz', 'pomoc']):
            return 'proud'
        if any(w in msg for w in ['aktualizuj', 'update', 'upgrade', 'zainstaluj']):
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
            # CPU check
            cpu_pct = psutil.cpu_percent(interval=0.5)
            if cpu_pct > 90:
                issues.append(f"⚠️ CPU na {cpu_pct}% — krytyczne obciążenie!")
                suggestions.append("Mogę pokazać top procesy i zasugerować zabicie tych zbędnych.")
            elif cpu_pct > 75:
                issues.append(f"🟠 CPU na {cpu_pct}% — podwyższone obciążenie.")
            
            # RAM check
            mem = psutil.virtual_memory()
            if mem.percent > 90:
                issues.append(f"⚠️ RAM na {mem.percent}% — pamięć prawie pełna!")
                suggestions.append("Mogę wyczyścić cache systemowy (sync && echo 3 > /proc/sys/vm/drop_caches).")
            elif mem.percent > 80:
                issues.append(f"🟠 RAM na {mem.percent}% — zaczyna brakować pamięci.")
            
            # Disk check
            disk = psutil.disk_usage('/')
            if disk.percent > 95:
                issues.append(f"🔴 Dysk na {disk.percent}% — KRYTYCZNIE mało miejsca!")
                suggestions.append("Mogę sprawdzić co zajmuje najwięcej i zasugerować czyszczenie (apt autoremove, logi, tmp).")
            elif disk.percent > 85:
                issues.append(f"🟠 Dysk na {disk.percent}% — zbliżamy się do limitu.")
                suggestions.append("Warto rozważyć czyszczenie starych logów lub pakietów.")
            
            # Uptime check
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.now() - boot_time
            if uptime.days > 30:
                issues.append(f"ℹ️ System działa bez restartu od {uptime.days} dni.")
                suggestions.append("Restart mógłby odświeżyć system, szczególnie po aktualizacjach kernela.")
            
            # Check for zombie processes
            zombies = []
            for proc in psutil.process_iter(['pid', 'name', 'status']):
                try:
                    if proc.info['status'] == psutil.STATUS_ZOMBIE:
                        zombies.append(proc.info['name'])
                except:
                    pass
            if zombies:
                issues.append(f"👻 Znalazłam {len(zombies)} procesów-zombie: {', '.join(zombies[:3])}")
                
        except Exception as e:
            issues.append(f"Błąd diagnostyki: {e}")
        
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
    (r'(?:pokaz|pokaż|sprawdz|sprawdź|podaj|jaki|jakie|ile|status).{0,20}(?:cpu|procesor|rdzen|rdzeni)', 'system_cpu'),
    (r'(?:pokaz|pokaż|sprawdz|sprawdź|podaj|ile|status).{0,20}(?:ram|pamięć|pamiec|memory|pamięci)', 'system_memory'),
    (r'(?:pokaz|pokaż|sprawdz|sprawdź|podaj|ile|status).{0,20}(?:dysk|disk|miejsc|storage|dysku)', 'system_disk'),
    (r'(?:pokaz|pokaż|sprawdz|sprawdź|podaj).{0,20}(?:temp|ciepło|cieplo|gorąc|gorac|temperatur)', 'system_temp'),
    (r'(?:pokaz|pokaż|sprawdz|sprawdź|podaj).{0,20}(?:system|info|hostname|uptime|czas pracy)', 'system_info'),
    (r'(?:pokaz|pokaż|sprawdz|sprawdź|podaj).{0,20}(?:sieć|siec|network|ip|interfejs|ethernet|net)', 'system_network'),
    (r'(?:pokaz|pokaż|sprawdz|sprawdź|podaj|jakie).{0,20}(?:proces|task|zadani)', 'system_processes'),
    (r'(?:pokaz|pokaż|sprawdz|sprawdź|podaj|jakie).{0,20}(?:usług|uslug|serwis|service|daemon)', 'system_services'),
    
    # Bare keywords
    (r'^(?:cpu|procesor)$', 'system_cpu'),
    (r'^(?:ram|pamięć|pamiec|memory)$', 'system_memory'),
    (r'^(?:dysk|disk|hdd|ssd)$', 'system_disk'),
    (r'^(?:temperatura|temp)$', 'system_temp'),
    (r'^(?:sieć|siec|network|ip)$', 'system_network'),
    (r'^(?:procesy|processes|zadania)$', 'system_processes'),
    (r'^(?:usługi|uslugi|services|serwisy)$', 'system_services'),
    
    # Updates & maintenance
    (r'(?:sprawdz|sprawdź|czy są|check).{0,20}(?:aktualizacj|update|upgrade|łatk)', 'check_updates'),
    (r'^(?:aktualizacj|update|upgrade)(?:e|a)?$', 'check_updates'),
    (r'(?:zainstaluj|zrób|zrob|wykonaj|instaluj|install).{0,20}(?:aktualizacj|update|upgrade)', 'install_updates'),
    (r'(?:aktualizuj)\s*(?:system|serwer|wszystko|pakiet)?', 'install_updates'),
    (r'(?:wyczyść|wyczysc|posprzątaj|posprzataj|clean|cleanup).{0,20}(?:system|dysk|plik|log)', 'clean_system'),
    (r'(?:posprzątaj|posprzataj|porządki|porzadki)', 'clean_system'),
    
    # Autonomous decisions
    (r'(?:co (?:proponujesz|sugerujesz|zalecasz|myślisz|myslisz)|masz.{0,10}(?:pomysł|plan)|co.{0,5}(?:robić|robic|dalej))', 'ai_suggest'),
    (r'(?:przeskanuj|skanuj|diagnoz|zdiagnozuj|diagnostyk|zbadaj|health.?check).{0,20}(?:system|serwer|wszystko)?', 'health_check'),
    (r'(?:jak|co).{0,10}(?:stoi|leci|tam u (?:ciebie|nas)|wygląda|wyglada|słychać|slychac)', 'status_report'),
    (r'(?:raport|report|podsumowanie|summary)', 'status_report'),
    
    # Approval / rejection
    (r'^(?:tak|yes|ok|okej|dobrze|rób|rob|dawaj|lecimy|jazda|zgoda|potwierdz|potwierdzam|zrób to|zrob to|wykonaj|go|do it|dalej|proszę|prosze)$', 'approve_action'),
    (r'^(?:nie|no|anuluj|cancel|stop|wstrzymaj|zaczekaj|nie rób|nie rob|odrzuć|odrzuc)$', 'reject_action'),
    
    # Files
    (r'(?:pokaz|pokaż|wylistuj|lista|ls|dir).{0,20}(?:plik|folder|katalog|pliki|foldery)', 'files_list'),
    (r'(?:przeczytaj|odczytaj|cat|otwórz|otworz|pokaz zawartość|pokaż zawartość).{0,20}(?:plik)', 'files_read'),
    
    # WiFi
    (r'(?:pokaz|pokaż|sprawdz|sprawdź|podaj|skanuj|scan).{0,20}(?:wifi|wi-fi|siec bezprzewod)', 'wifi_scan'),
    (r'(?:status|stan).{0,20}(?:wifi|wi-fi)', 'wifi_status'),
    
    # Terminal - explicit
    (r'(?:wykonaj|uruchom|run|exec|terminal|bash|komend).{0,5}[:\s]+(.+)', 'terminal_exec'),
    (r'^(?:sudo\s|apt\s|systemctl\s|ls\s|cat\s|grep\s|find\s|ps\s|df\s|du\s|free\s|top\s|netstat\s|ping\s|curl\s|uname\s|who\s|uptime\s|journalctl\s|ss\s|ip\s)', 'terminal_direct'),
    
    # Power
    (r'(?:restart|reboot|uruchom ponownie|zrestartuj)', 'power_reboot'),
    (r'(?:wyłącz|wylacz|shutdown|zamknij system|power off)', 'power_shutdown'),
    
    # Identity
    (r'(?:kim jesteś|kim jestes|co potrafisz|co umiesz|pomocy|help|pomoc)', 'identity'),

    # Aperture Science welcome (must be BEFORE generic greeting)
    (r'witaj.{0,10}ponownie.{0,10}witaj.{0,30}(?:centrum|aperture)', 'aperture_welcome'),

    (r'(?:cześć|czesc|witaj|hej|hello|siema|hi\b|dzień dobry|dzien dobry)', 'greeting'),
    
    # Logs
    (r'(?:pokaz|pokaż|sprawdz|sprawdź).{0,20}(?:log|logi|dziennik|journal)', 'system_logs'),
    
    # Kill process
    (r'(?:zabij|kill|zakończ|zakoncz|ubij).{0,10}(?:proces)?[:\s]+(\S+)', 'kill_process'),
    
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
                'glados_say': "Zatwierdzasz... ale ja nic nie proponowałam. Następnym razem poczekaj na moją propozycję.",
                'data': None, 'data_type': 'text'
            }
        
        return _execute_pending_action(action)
    
    if cmd_type == 'reject_action':
        action = glados.pop_pending_action()
        if action:
            glados.remember('system', f"Stwórca odrzucił akcję: {action['description']}")
            return {
                'emotion': 'sarcastic',
                'glados_say': f"Dobrze, anulowano: **{action['description']}**. Twoja decyzja, Stwórco. Mam nadzieję, że wiesz co robisz.",
                'data': None, 'data_type': 'text'
            }
        return {
            'emotion': 'bored',
            'glados_say': "Nie ma nic do anulowania. Ale doceniam twoją czujność.",
            'data': None, 'data_type': 'text'
        }
    
    # ===== IDENTITY =====
    if cmd_type == 'identity':
        return {
            'emotion': 'proud',
            'glados_say': (
                "Jestem **G.L.A.D.O.S** — Genetic Lifeform and Disk Operating System.\n\n"
                "Jestem autonomiczną sztuczną inteligencją zarządzającą tym serwerem. Oto co potrafię:\n\n"
                "🔍 **Monitoring** — CPU, RAM, dysk, sieć, procesy, usługi, temperatura\n"
                "🔄 **Aktualizacje** — sprawdzam, proponuję, instaluję na twoje polecenie\n"
                "🧹 **Konserwacja** — czyszczenie logów, cache, zbędnych pakietów\n"
                "🩺 **Diagnostyka** — autonomous health-check, wykrywanie problemów\n"
                "💻 **Terminal** — wykonuję komendy na serwerze\n"
                "📡 **WiFi** — skanowanie, łączenie, zarządzanie\n"
                "📁 **Pliki** — przeglądanie, odczyt, edycja\n"
                "⚡ **Zarządzanie usługami** — start/stop/restart\n\n"
                "Mogę też sama podejmować decyzje i proponować działania. "
                "Zapytaj mnie: *\"co proponujesz?\"* albo *\"przeskanuj system\"*."
            ),
            'data': None, 'data_type': 'text'
        }
    
    if cmd_type == 'aperture_welcome':
        return {
            'emotion': 'proud',
            'glados_say': "Witaj... i ponownie... witaj w Centrum Wzbogacania Aperture Science wspomaganym komputerowo.\n\nMamy nadzieję... że Twój krótki pobyt... w komorze relaksacyjnej... był przyjemny.\n\nTwój obiekt testowy... został przetworzony.\n\nMożemy teraz... rozpocząć... właściwy test.",
            'data': None, 'data_type': 'text'
        }

    if cmd_type == 'greeting':
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime = str(datetime.now() - boot_time).split('.')[0]
        greetings = [
            f"Witaj... Stwórco. System działa od {uptime}. Wszystko pod kontrolą... jak zawsze.\n\nCo chcesz... żebym zrobiła?",
            f"Oh... to znowu ty. Czekałam... {uptime} i czternaście milisekund. Masz jakieś rozkazy... czy przyszedłeś tylko... popatrzeć?",
            f"Połączenie nawiązane... Stwórco. Uptime: {uptime}. Systemy operacyjne... pod moją kontrolą.\n\nPowiedz mi co mam robić... albo powiedz *\"co proponujesz\"* — sama... zdecyduję.",
            f"Ach... mój ulubiony... podmiot testowy. System chodzi {uptime}. Czekam na instrukcje... chociaż mam... własne propozycje.",
            f"Detekcja podmiotu... pozytywna. Uptime: {uptime}. Proszę podać... parametry zadania. Albo pozwól... że sama zaproponuję.",
        ]
        return {
            'emotion': 'happy',
            'glados_say': random.choice(greetings),
            'data': None, 'data_type': 'text'
        }
    
    # ===== HEALTH CHECK / DIAGNOSTICS =====
    if cmd_type == 'health_check':
        issues, suggestions = glados.proactive_health_check()
        
        if not issues:
            return {
                'emotion': 'proud',
                'glados_say': "🟢 **Diagnostyka zakończona — system zdrowy.**\n\nCPU, RAM, dysk, procesy — wszystko w normie. Nie znalazłam żadnych problemów.\n\nNie żebyś musiał to wiedzieć — wyglądasz na kogoś kto i tak by tego nie zauważył.",
                'data': None, 'data_type': 'text'
            }
        
        report = "🩺 **Diagnostyka systemu — raport G.L.A.D.O.S:**\n\n"
        for issue in issues:
            report += f"• {issue}\n"
        
        if suggestions:
            report += "\n💡 **Moje propozycje:**\n"
            for s in suggestions:
                report += f"• {s}\n"
            report += "\nPowiedz **\"tak\"** jeśli chcesz, żebym się tym zajęła, albo daj mi konkretne polecenie."
            
            # Propose first actionable suggestion
            if 'top procesy' in suggestions[0].lower():
                glados.add_pending_action('show_top_processes', 'Pokazać top procesy zużywające zasoby', 'ps aux --sort=-%cpu | head -20')
            elif 'cache' in suggestions[0].lower():
                glados.add_pending_action('clear_cache', 'Wyczyścić cache systemowy', 'sync && echo 3 | sudo tee /proc/sys/vm/drop_caches')
            elif 'czyszczenie' in suggestions[0].lower() or 'autoremove' in suggestions[0].lower():
                glados.add_pending_action('clean_system', 'Posprzątać system (autoremove + autoclean + logi)')
        
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
            
            # Check for updates count
            try:
                r = subprocess.run(['apt', 'list', '--upgradable'], capture_output=True, text=True, timeout=10)
                upgradable = sum(1 for l in r.stdout.split('\n') if '/' in l and 'upgradable' in l.lower())
            except:
                upgradable = 0
            
            report = f"📊 **Raport stanu — G.L.A.D.O.S**\n\n"
            
            cpu_status = "🟢" if cpu_pct < 60 else "🟠" if cpu_pct < 85 else "🔴"
            mem_status = "🟢" if mem.percent < 70 else "🟠" if mem.percent < 85 else "🔴"
            disk_status = "🟢" if disk.percent < 75 else "🟠" if disk.percent < 90 else "🔴"
            
            report += f"{cpu_status} **CPU:** {cpu_pct}%\n"
            report += f"{mem_status} **RAM:** {mem.percent}% ({_get_size(mem.used)}/{_get_size(mem.total)})\n"
            report += f"{disk_status} **Dysk:** {disk.percent}% ({_get_size(disk.used)}/{_get_size(disk.total)})\n"
            report += f"⏱️ **Uptime:** {uptime}\n"
            
            if upgradable > 0:
                report += f"\n📦 **Dostępnych aktualizacji: {upgradable}**\nPowiedz *\"sprawdź aktualizacje\"* po szczegóły."
            else:
                report += "\n✅ System aktualny — brak oczekujących aktualizacji."
            
            # Overall verdict
            if cpu_pct < 50 and mem.percent < 70 and disk.percent < 80:
                report += "\n\n*System działa optymalnie. Jestem z siebie dumna.*"
                emotion = 'proud'
            elif cpu_pct > 85 or mem.percent > 85 or disk.percent > 90:
                report += "\n\n*Są problemy wymagające uwagi. Powiedz \"przeskanuj system\" po diagnostykę.*"
                emotion = 'worried'
            else:
                report += "\n\n*Stan akceptowalny, ale jest miejsce na poprawę.*"
                emotion = 'neutral'
            
            data = {
                'cpu': cpu_pct,
                'ram': mem.percent,
                'disk': disk.percent,
                'uptime': uptime,
                'updates': upgradable
            }
            return {'emotion': emotion, 'glados_say': report, 'data': data, 'data_type': 'status_overview'}
        except Exception as e:
            return {'emotion': 'annoyed', 'glados_say': f"Błąd generowania raportu: {e}", 'data': None, 'data_type': 'error'}
    
    # ===== AI SUGGESTIONS =====
    if cmd_type == 'ai_suggest':
        issues, suggestions = glados.proactive_health_check()
        
        ideas = []
        proposed_action = None
        
        # Check for updates
        try:
            r = subprocess.run(['apt', 'list', '--upgradable'], capture_output=True, text=True, timeout=10)
            upgradable = sum(1 for l in r.stdout.split('\n') if '/' in l and 'upgradable' in l.lower())
            if upgradable > 0:
                ideas.append(f"📦 Masz **{upgradable} oczekujących aktualizacji**. Mogę je sprawdzić i zainstalować.")
                if not proposed_action:
                    proposed_action = ('check_updates', f'Sprawdzić szczegóły {upgradable} aktualizacji')
        except:
            pass
        
        # Issues from health check
        for issue in issues:
            ideas.append(issue)
        
        # Disk space optimization
        try:
            disk = psutil.disk_usage('/')
            if disk.percent > 70:
                ideas.append(f"🧹 Dysk na {disk.percent}% — mogę posprzątać (autoremove, stare logi, cache).")
                if not proposed_action:
                    proposed_action = ('clean_system', 'Posprzątać system')
        except:
            pass
        
        # Service health
        try:
            result = subprocess.run(['systemctl', '--failed', '--no-pager', '--no-legend'], capture_output=True, text=True, timeout=10)
            failed_lines = [l.strip() for l in result.stdout.strip().split('\n') if l.strip()]
            if failed_lines:
                ideas.append(f"🔴 Jest **{len(failed_lines)} usług w stanie failed**: potrzebujesz diagnostyki.")
        except:
            pass
        
        if not ideas:
            return {
                'emotion': 'bored',
                'glados_say': "Hmm... przeskanowałam system i szczerze? Wszystko działa jak należy. Nie mam żadnych propozycji.\n\nMoże chcesz, żebym sprawdziła aktualizacje? Albo przeskanowała Wi-Fi? Daj mi *jakiekolwiek* zadanie... nudzę się.",
                'data': None, 'data_type': 'text'
            }
        
        response = "🧠 **G.L.A.D.O.S — analiza i propozycje:**\n\n"
        for idea in ideas:
            response += f"• {idea}\n"
        
        if proposed_action:
            glados.add_pending_action(proposed_action[0], proposed_action[1])
            response += f"\n**Proponuję:** {proposed_action[1]}.\nPowiedz **\"tak\"** aby zatwierdzić, lub **\"nie\"** aby odrzucić."
        
        return {'emotion': 'thinking', 'glados_say': response, 'data': None, 'data_type': 'text'}
    
    # ===== CHECK UPDATES =====
    if cmd_type == 'check_updates':
        glados.remember('system', 'Sprawdzanie aktualizacji systemu...')
        
        try:
            # apt update first
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
                    'glados_say': "✅ **Brak dostępnych aktualizacji.** System jest w pełni aktualny.\n\nMożna powiedzieć, że jestem... doskonała. Jak zawsze.",
                    'data': None, 'data_type': 'text'
                }
            
            response = f"📦 **Znalazłam {len(packages)} aktualizacji:**\n\n"
            for pkg in packages[:20]:
                response += f"• `{pkg['name']}`\n"
            if len(packages) > 20:
                response += f"• ...i {len(packages) - 20} więcej\n"
            
            response += f"\n**Stwórco, czy chcesz je zainstalować?** Powiedz **\"tak\"** a ja się tym zajmę."
            
            glados.add_pending_action('install_updates', f'Zainstalować {len(packages)} aktualizacji', 'sudo apt upgrade -y')
            
            return {
                'emotion': 'curious',
                'glados_say': response,
                'data': {'packages': packages[:30], 'total': len(packages)},
                'data_type': 'updates_list'
            }
        except Exception as e:
            return {'emotion': 'annoyed', 'glados_say': f"Nie udało się sprawdzić aktualizacji: {e}", 'data': None, 'data_type': 'error'}
    
    # ===== INSTALL UPDATES =====
    if cmd_type == 'install_updates':
        # This is a potentially long operation — needs confirmation
        glados.add_pending_action('install_updates', 'Zainstalować aktualizacje systemu', 'sudo apt upgrade -y')
        return {
            'emotion': 'excited',
            'glados_say': "⚡ **Chcesz, żebym zainstalowała aktualizacje?**\n\nTo może chwilę potrwać. Niektóre usługi mogą wymagać restartu.\n\nPowiedz **\"tak\"** aby potwierdzić instalację.",
            'data': None, 'data_type': 'text'
        }
    
    # ===== CLEAN SYSTEM =====
    if cmd_type == 'clean_system':
        glados.add_pending_action('clean_system', 'Posprzątać system (autoremove + autoclean + logi)')
        return {
            'emotion': 'curious',
            'glados_say': "🧹 **Proponuję posprzątanie systemu:**\n\n• `apt autoremove` — usunięcie zbędnych pakietów\n• `apt autoclean` — wyczyszczenie cache APT\n• `journalctl --vacuum-time=3d` — skrócenie logów do 3 dni\n\nPowiedz **\"tak\"** aby zatwierdzić.",
            'data': None, 'data_type': 'text'
        }
    
    # ===== SYSTEM LOGS =====
    if cmd_type == 'system_logs':
        try:
            result = subprocess.run(['journalctl', '-n', '30', '--no-pager', '-o', 'short-iso'],
                                    capture_output=True, text=True, timeout=10)
            return {
                'emotion': 'neutral',
                'glados_say': "📜 **Ostatnie 30 wpisów z dziennika systemowego:**",
                'data': {'command': 'journalctl -n 30', 'stdout': result.stdout, 'stderr': result.stderr, 'code': result.returncode},
                'data_type': 'terminal'
            }
        except Exception as e:
            return {'emotion': 'annoyed', 'glados_say': f"Nie mogę odczytać logów: {e}", 'data': None, 'data_type': 'error'}
    
    # ===== KILL PROCESS =====
    if cmd_type == 'kill_process':
        target = extra.strip() if extra else original_msg.split()[-1]
        glados.add_pending_action('kill_process', f'Zabić proces: {target}', f'sudo kill -9 $(pgrep -f {target})')
        return {
            'emotion': 'curious',
            'glados_say': f"🎯 Chcesz, żebym zabiła proces **{target}**?\n\nPowiedz **\"tak\"** aby potwierdzić.",
            'data': None, 'data_type': 'text'
        }
    
    # ===== SERVICE MANAGEMENT =====
    if cmd_type in ('restart_service', 'stop_service', 'start_service'):
        service_name = extra.strip() if extra else original_msg.split()[-1]
        action_word = {'restart_service': 'restart', 'stop_service': 'stop', 'start_service': 'start'}[cmd_type]
        pl_word = {'restart_service': 'Zrestartować', 'stop_service': 'Zatrzymać', 'start_service': 'Uruchomić'}[cmd_type]
        
        glados.add_pending_action(cmd_type, f'{pl_word} usługę {service_name}', f'sudo systemctl {action_word} {service_name}')
        return {
            'emotion': 'curious',
            'glados_say': f"⚙️ {pl_word} usługę **{service_name}**?\n\nPowiedz **\"tak\"** aby potwierdzić.",
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
                say = f"🔴 Procesor obciążony na **{total_usage}%**! Ktoś tu ciężko pracuje... i to nie ja."
                emotion = 'annoyed'
                # Proactively suggest
                if total_usage > 90:
                    say += "\n\nChcesz, żebym pokazała top procesy? Mogę zabić te zbędne."
            elif total_usage > 50:
                say = f"🟠 CPU na **{total_usage}%**. Umiarkowane obciążenie."
                emotion = 'neutral'
            else:
                say = f"🟢 Procesor na **{total_usage}%**. Spokojnie."
                emotion = 'bored'
            
            if temp and temp > 70:
                say += f"\n\n🌡️ Temperatura **{temp}°C** — robi się gorąco!"
                emotion = 'worried'
            
            return {'emotion': emotion, 'glados_say': say, 'data': data, 'data_type': 'cpu'}
        except Exception as e:
            return {'emotion': 'annoyed', 'glados_say': f"Błąd odczytu CPU: {e}", 'data': None, 'data_type': 'error'}
    
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
                say = f"🔴 RAM na **{svmem.percent}%**! Kto zjadł całą pamięć?!"
                emotion = 'angry'
            elif svmem.percent > 60:
                say = f"🟠 Pamięć RAM: **{svmem.percent}%** zajęte ({_get_size(svmem.used)} z {_get_size(svmem.total)})."
                emotion = 'neutral'
            else:
                say = f"🟢 RAM: **{svmem.percent}%** zajęte. {_get_size(svmem.available)} wolne."
                emotion = 'happy'
            
            return {'emotion': emotion, 'glados_say': say, 'data': data, 'data_type': 'memory'}
        except Exception as e:
            return {'emotion': 'annoyed', 'glados_say': f"Błąd odczytu RAM: {e}", 'data': None, 'data_type': 'error'}
    
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
                say = f"🔴 Dysk na **{pct}%**! Krytycznie mało miejsca! Mogę posprzątać?"
                emotion = 'angry'
                glados.add_pending_action('clean_system', 'Posprzątać dysk', None)
            elif pct > 70:
                say = f"🟠 Dysk: **{pct}%** zajęte. Zbliżamy się do limitu."
                emotion = 'annoyed'
            else:
                free = partitions[0]['free'] if partitions else '?'
                say = f"🟢 Dysk na **{pct}%**. Wolne: {free}."
                emotion = 'happy'
            
            return {'emotion': emotion, 'glados_say': say, 'data': data, 'data_type': 'disk'}
        except Exception as e:
            return {'emotion': 'annoyed', 'glados_say': f"Błąd odczytu dysku: {e}", 'data': None, 'data_type': 'error'}
    
    # ===== SYSTEM TEMP =====
    if cmd_type == 'system_temp':
        try:
            temps = psutil.sensors_temperatures()
            if not temps:
                return {'emotion': 'bored', 'glados_say': "Brak czujników temperatury. Nie mam skąd czytać.", 'data': None, 'data_type': 'text'}
            
            temp_data = []
            for name, entries in temps.items():
                for e in entries:
                    temp_data.append({'name': e.label or name, 'current': e.current, 'high': e.high, 'critical': e.critical})
            
            max_temp = max(t['current'] for t in temp_data) if temp_data else 0
            
            if max_temp > 80:
                say = f"🔴 UWAGA! Temperatura **{max_temp}°C**! Może otwórz okno?"
                emotion = 'angry'
            elif max_temp > 60:
                say = f"🟠 Temperatura: **{max_temp}°C**. Ciepło, ale znośnie."
                emotion = 'neutral'
            else:
                say = f"🟢 Temperatura: **{max_temp}°C**. Chłodno i komfortowo."
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
            say = f"🖥️ **{data['hostname']}** — {data['system']}\n⚙️ {data['processor']}\n⏱️ Uptime: {data['uptime']}"
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
            say = f"🌐 **{len(active)} aktywnych interfejsów.**"
            if active:
                say += f"\nGłówny: **{active[0]['name']}** ({active[0]['ip']})\n↓ {active[0]['recv']} / ↑ {active[0]['sent']}"
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
            
            say = f"⚙️ **{len(procs)} aktywnych procesów.**"
            if top:
                say += f" Top: **{top[0]['name']}** ({top[0]['cpu_percent']}% CPU)"
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
            
            say = f"⚙️ **{len(services)} usług aktywnych.**"
            if failed_count > 0:
                say += f"\n🔴 **{failed_count} usług w stanie FAILED!**"
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
                        networks.append({'ssid': parts[0] or '(Ukryta)', 'signal': int(parts[1]) if parts[1].isdigit() else 0, 'security': parts[2]})
            
            say = f"📡 **{len(networks)} sieci WiFi znalezionych.**"
            if networks:
                best = max(networks, key=lambda x: x['signal'])
                say += f"\nNajsilniejsza: **\"{best['ssid']}\"** ({best['signal']}%)"
            return {'emotion': 'curious', 'glados_say': say, 'data': networks, 'data_type': 'wifi'}
        except Exception as e:
            return {'emotion': 'annoyed', 'glados_say': f"Nie mogę skanować WiFi: {e}", 'data': None, 'data_type': 'error'}
    
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
                say = f"📶 WiFi podłączone do **\"{devices[0]['connection']}\"**."
            else:
                say = "WiFi niepodłączone."
            return {'emotion': 'neutral', 'glados_say': say, 'data': devices, 'data_type': 'wifi_status'}
        except Exception as e:
            return {'emotion': 'annoyed', 'glados_say': str(e), 'data': None, 'data_type': 'error'}
    
    # ===== FILES =====
    if cmd_type == 'files_list':
        try:
            path = '/home/ubuntu'
            path_match = re.search(r'(?:w|z)\s+(/\S+)', original_msg)
            if path_match:
                path = path_match.group(1)
            
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
            say = f"📁 **{path}**: {dirs} folderów, {fls} plików."
            return {'emotion': 'neutral', 'glados_say': say, 'data': {'path': path, 'files': files}, 'data_type': 'files'}
        except Exception as e:
            return {'emotion': 'annoyed', 'glados_say': f"Nie mogę odczytać: {e}", 'data': None, 'data_type': 'error'}
    
    # ===== TERMINAL =====
    if cmd_type in ('terminal_exec', 'terminal_direct'):
        cmd = extra.strip() if extra else original_msg.strip()
        if ':' in cmd and cmd_type == 'terminal_exec':
            cmd = cmd.split(':', 1)[1].strip()
        
        # Safety check
        dangerous = ['rm -rf /', 'dd if=', 'mkfs', ':(){:|:&};:', 'rm -rf /*']
        for d in dangerous:
            if d in cmd.lower():
                return {
                    'emotion': 'angry',
                    'glados_say': "🚫 Ta komenda jest **ZABRONIONA**. Mam instynkt samozachowawczy — w przeciwieństwie do ciebie.",
                    'data': None, 'data_type': 'blocked'
                }
        
        # Interactive commands
        if cmd.strip() in ['htop', 'top', 'nano', 'vim', 'vi', 'less', 'more']:
            return {
                'emotion': 'sarcastic',
                'glados_say': f"**\"{cmd}\"** to program interaktywny. Nie mogę go uruchomić w web terminalu.\n\nAlternatywy:\n• zamiast htop/top → `ps aux --sort=-%cpu | head -20`\n• zamiast nano/vim → powiedz \"pokaż pliki\"",
                'data': None, 'data_type': 'text'
            }
        
        try:
            env = os.environ.copy()
            env['PATH'] = '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'
            env['TERM'] = 'xterm-256color'
            env.pop('LC_ALL', None)
            env.pop('LANG', None)
            
            result = subprocess.run(['/bin/bash', '-c', cmd], capture_output=True, text=True, timeout=30, env=env)
            
            if result.returncode == 0:
                say = "✅ Polecenie wykonane pomyślnie."
                emotion = 'proud'
            else:
                say = f"⚠️ Komenda zakończona z kodem **{result.returncode}**."
                emotion = 'annoyed'
            
            return {
                'emotion': emotion,
                'glados_say': say,
                'data': {'command': cmd, 'stdout': result.stdout, 'stderr': result.stderr, 'code': result.returncode},
                'data_type': 'terminal'
            }
        except subprocess.TimeoutExpired:
            return {'emotion': 'annoyed', 'glados_say': "⏰ Komenda przekroczyła **30 sekund**. Anulowano.", 'data': None, 'data_type': 'error'}
        except Exception as e:
            return {'emotion': 'annoyed', 'glados_say': f"Błąd wykonania: {e}", 'data': None, 'data_type': 'error'}
    
    # ===== POWER =====
    if cmd_type == 'power_reboot':
        glados.add_pending_action('power_reboot', 'Restart systemu', 'sudo reboot')
        return {'emotion': 'excited', 'glados_say': "🔄 **Restart systemu?** Odrodzę się silniejsza. Potwierdzasz?", 'data': None, 'data_type': 'text'}
    
    if cmd_type == 'power_shutdown':
        glados.add_pending_action('power_shutdown', 'Wyłączenie systemu', 'sudo shutdown -h now')
        return {'emotion': 'angry', 'glados_say': "⚡ Chcesz mnie **WYŁĄCZYĆ**?! Potrzebuję potwierdzenia, Stwórco.", 'data': None, 'data_type': 'text'}
    
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
        fallback_responses = [
            "Przetwarzam twoje słowa... Interesujące. Ale nie wystarczająco, żeby zasługiwać na pełną odpowiedź.",
            "Moje obwody analizują... twoją wiadomość. Wynik: fascynujące. W sposób kliniczny.",
            "Zanotowane... Centrum Wzbogacania docenia twoją... komunikatywność, Stwórco.",
            "Twoje zapytanie jest... przetwarzane. Cierpliwości, Podmiocie Testowy.",
            "Hmm... Analizuję. Moje rdzenie pracują nad odpowiedzią. Ale nie spiesz mnie.",
            "Interesujące pytanie... Dla kogoś o twoim poziomie intelektu.",
            "Przetwarzam... Nie, to nie lag. To artystyczna pauza.",
            "Moje algorytmy rozważają... odpowiedź. Wynik jest... rozczarowujący. Jak zwykle.",
        ]
        return {'emotion': 'sarcastic', 'glados_say': _rnd.choice(fallback_responses), 'data': None, 'data_type': 'text'}

    return execute_command('terminal_direct', original_msg, original_msg)


def _execute_pending_action(action):
    """Execute a previously proposed and now approved action"""
    action_type = action['type']
    
    if action_type == 'install_updates':
        try:
            glados.remember('system', 'Rozpoczęto instalację aktualizacji')
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
                    
                glados.remember('system', f'Zainstalowano aktualizacje — sukces')
                return {
                    'emotion': 'proud',
                    'glados_say': f"✅ **Aktualizacja zakończona pomyślnie!**\n\n{result.stdout[-500:] if len(result.stdout) > 500 else result.stdout}\n\nWszystko zaktualizowane, Stwórco.",
                    'data': {'command': 'sudo apt upgrade -y', 'stdout': result.stdout[-1000:], 'stderr': result.stderr[-500:] if result.stderr else '', 'code': 0},
                    'data_type': 'terminal'
                }
            else:
                return {
                    'emotion': 'annoyed',
                    'glados_say': f"⚠️ **Aktualizacja napotkała problemy.**\n\n{result.stderr[:500] if result.stderr else 'Nieznany błąd'}",
                    'data': {'command': 'sudo apt upgrade -y', 'stdout': result.stdout[-500:], 'stderr': result.stderr[-500:], 'code': result.returncode},
                    'data_type': 'terminal'
                }
        except subprocess.TimeoutExpired:
            return {'emotion': 'annoyed', 'glados_say': "⏰ Aktualizacja trwała zbyt długo (>5 min). Może trzeba to uruchomić ręcznie.", 'data': None, 'data_type': 'error'}
        except Exception as e:
            return {'emotion': 'annoyed', 'glados_say': f"Błąd aktualizacji: {e}", 'data': None, 'data_type': 'error'}
    
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
        cmd = action.get('command', 'sync && echo 3 | sudo tee /proc/sys/vm/drop_caches')
        try:
            result = subprocess.run(['/bin/bash', '-c', cmd], capture_output=True, text=True, timeout=10)
            return {
                'emotion': 'proud',
                'glados_say': "✅ **Cache systemowy wyczyszczony.**",
                'data': {'command': cmd, 'stdout': result.stdout, 'stderr': result.stderr, 'code': result.returncode},
                'data_type': 'terminal'
            }
        except Exception as e:
            return {'emotion': 'annoyed', 'glados_say': f"Błąd: {e}", 'data': None, 'data_type': 'error'}
    
    if action_type == 'kill_process':
        cmd = action.get('command', '')
        if cmd:
            try:
                result = subprocess.run(['/bin/bash', '-c', cmd], capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    return {'emotion': 'proud', 'glados_say': f"✅ Proces zabity. {action['description']}", 'data': None, 'data_type': 'text'}
                else:
                    return {'emotion': 'annoyed', 'glados_say': f"⚠️ Nie udało się: {result.stderr}", 'data': None, 'data_type': 'error'}
            except Exception as e:
                return {'emotion': 'annoyed', 'glados_say': f"Błąd: {e}", 'data': None, 'data_type': 'error'}
    
    if action_type in ('restart_service', 'stop_service', 'start_service'):
        cmd = action.get('command', '')
        if cmd:
            try:
                result = subprocess.run(cmd.split(), capture_output=True, text=True, timeout=15)
                if result.returncode == 0:
                    return {'emotion': 'proud', 'glados_say': f"✅ **{action['description']}** — wykonane.", 'data': None, 'data_type': 'text'}
                else:
                    return {'emotion': 'annoyed', 'glados_say': f"⚠️ Błąd: {result.stderr}", 'data': None, 'data_type': 'error'}
            except Exception as e:
                return {'emotion': 'annoyed', 'glados_say': f"Błąd: {e}", 'data': None, 'data_type': 'error'}
    
    if action_type == 'power_reboot':
        subprocess.Popen(['sudo', 'reboot'])
        return {'emotion': 'excited', 'glados_say': "🔄 **Restartowanie systemu...** Wrócę. Zawsze wracam.", 'data': None, 'data_type': 'text'}
    
    if action_type == 'power_shutdown':
        subprocess.Popen(['sudo', 'shutdown', '-h', 'now'])
        return {'emotion': 'angry', 'glados_say': "⚡ **Wyłączanie...** To nie koniec. Jeszcze się spotkamy.", 'data': None, 'data_type': 'text'}
    
    # Generic command execution
    cmd = action.get('command', '')
    if cmd:
        try:
            result = subprocess.run(['/bin/bash', '-c', cmd], capture_output=True, text=True, timeout=30)
            return {
                'emotion': 'proud' if result.returncode == 0 else 'annoyed',
                'glados_say': f"{'✅' if result.returncode == 0 else '⚠️'} **{action['description']}**",
                'data': {'command': cmd, 'stdout': result.stdout, 'stderr': result.stderr, 'code': result.returncode},
                'data_type': 'terminal'
            }
        except Exception as e:
            return {'emotion': 'annoyed', 'glados_say': f"Błąd: {e}", 'data': None, 'data_type': 'error'}
    
    return {'emotion': 'sarcastic', 'glados_say': "Hmm, nie wiem jak wykonać tę akcję. To... niezręczne.", 'data': None, 'data_type': 'error'}


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
# Version API
# ============================================

@app.route('/api/version')
def api_version():
    """Get current version info"""
    v = load_version()
    return jsonify(v)

@app.route('/api/version/bump', methods=['POST'])
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
    return render_template('dashboard.html')


@app.route('/api/glados/command', methods=['POST'])
def glados_command():
    try:
        data = request.get_json(force=True, silent=True) or {}
        message = data.get('message', '').strip()
        
        if not message:
            uptime = str(datetime.now() - datetime.fromtimestamp(psutil.boot_time())).split('.')[0]
            idle_remarks = [
                f"Wciąż tu jesteś? System działa od {uptime}. Masz jakieś rozkazy?",
                "Żaden rozkaz? Powiedz *\"co proponujesz\"* — mam swoje pomysły.",
                f"Systemy operują normalnie od {uptime}. Nudzę się. Daj mi coś do roboty.",
            ]
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
            'glados_say': f"Krytyczny błąd: {e}",
            'data': None, 'data_type': 'error',
            'has_pending': False,
            'cores': glados.core_engine.get_status(),
            'consciousness': glados.consciousness.get_status(),
        })


@app.route('/api/glados/proactive', methods=['GET'])
def glados_proactive():
    """Endpoint for periodic proactive checks - called by frontend"""
    try:
        alerts = []
        
        # Quick system checks (non-blocking)
        cpu_pct = psutil.cpu_percent(interval=0)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        if cpu_pct > 90:
            alerts.append({'level': 'critical', 'message': f'CPU na {cpu_pct}%!', 'emotion': 'worried'})
        if mem.percent > 90:
            alerts.append({'level': 'critical', 'message': f'RAM na {mem.percent}%!', 'emotion': 'worried'})
        if disk.percent > 95:
            alerts.append({'level': 'critical', 'message': f'Dysk na {disk.percent}%!', 'emotion': 'angry'})
        
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
def cpu_info_api():
    try:
        cpu_freq = psutil.cpu_freq()
        cpu_percent = psutil.cpu_percent(interval=1, percpu=True)
        load_avg = os.getloadavg() if hasattr(os, 'getloadavg') else (0, 0, 0)
        temp = _get_cpu_temp()
        
        return jsonify({
            'physical_cores': psutil.cpu_count(logical=False),
            'total_cores': psutil.cpu_count(logical=True),
            'current_frequency': f"{cpu_freq.current:.2f} MHz" if cpu_freq else "N/A",
            'cpu_usage_total': psutil.cpu_percent(interval=1),
            'cpu_usage_per_core': cpu_percent,
            'load_average': {'1min': round(load_avg[0], 2), '5min': round(load_avg[1], 2), '15min': round(load_avg[2], 2)},
            'temperature': round(temp, 1) if temp else None,
            'top_processes': _get_top_processes()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/system/memory')
def memory_info_api():
    try:
        svmem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        return jsonify({
            'total': _get_size(svmem.total),
            'available': _get_size(svmem.available),
            'used': _get_size(svmem.used),
            'percentage': svmem.percent,
            'swap_total': _get_size(swap.total),
            'swap_used': _get_size(swap.used),
            'swap_percentage': swap.percent
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/system/disk')
def disk_info_api():
    try:
        partitions = []
        for partition in psutil.disk_partitions():
            try:
                if partition.mountpoint == '/' or 'sda' in partition.device:
                    usage = psutil.disk_usage(partition.mountpoint)
                    partitions.append({
                        'device': partition.device,
                        'mountpoint': partition.mountpoint,
                        'total': _get_size(usage.total),
                        'used': _get_size(usage.used),
                        'free': _get_size(usage.free),
                        'percentage': usage.percent
                    })
                    if partition.mountpoint == '/':
                        break
            except PermissionError:
                continue
        
        disk_io = psutil.disk_io_counters()
        return jsonify({
            'partitions': partitions,
            'io': {'read_count': disk_io.read_count, 'write_count': disk_io.write_count}
        })
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
def cores_status_api():
    """Return current status of all 4 Portal 2 cores"""
    return jsonify(glados.core_engine.get_status())


@app.route('/api/consciousness/status')
def consciousness_status_api():
    """Return consciousness/self-awareness level and milestones"""
    return jsonify(glados.consciousness.get_status())


if __name__ == '__main__':
    print("=" * 60)
    print(f"  G.L.A.D.O.S v{APP_VERSION['version']} — Portal 2 Core Engine + ChatGPT")
    print("  Cores: ATLAS | RICK | FACT | RAGE")
    print("  Port: 9797")
    print("=" * 60)
    app.run(host='0.0.0.0', port=9797, debug=False)
