# G.L.A.D.O.S System Panel

<p align="center">
  <strong>Genetic Lifeform and Disk Operating System</strong><br>
  <em>Portal 2-inspired autonomous AI system panel for Linux</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Version-6.1.2-00e5ff?style=for-the-badge" alt="Version">
  <img src="https://img.shields.io/badge/Codename-GLaDOS%20Voice%20Reborn-7c4dff?style=for-the-badge" alt="Codename">
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776ab?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Flask-3.0%2B-000000?style=for-the-badge&logo=flask" alt="Flask">
  <img src="https://img.shields.io/badge/License-GPL--3.0-blue?style=for-the-badge" alt="License">
  <img src="https://img.shields.io/badge/Status-Experimental-orange?style=for-the-badge" alt="Status">
</p>

> **⚠️ Experimental — This project is under active development and is not yet a final release.**

A sci-fi Linux admin dashboard inspired by Portal 2 with the iconic GLaDOS AI personality. It monitors your system in real-time, executes commands, responds with cold sarcasm, and speaks Polish with a vocoder-processed voice — all wrapped in a glass morphism UI straight from Aperture Science.

---

## ✨ Features

### 🖥️ System Monitoring
- **Real-time dashboard** — CPU, RAM, disk, network, and temperature with 60-point history charts
- **Process manager** — view, search, and manage running processes
- **Storage overview** — disk usage per partition with visual indicators
- **Network stats** — bytes sent/received, active connections
- **Proactive alerts** — autonomous warnings when CPU >90%, RAM >90%, or disk >95%

### 🤖 AI & Personality
- **GLaDOS AI Chat** — conversational interface powered by g4f (free ChatGPT) with sarcastic GLaDOS persona
- **Portal 2 Personality Cores** — four cores that activate contextually:
  - 🟣 **ATLAS** (Morality) — ethical considerations and moral judgments
  - 🟠 **RICK** (Curiosity) — exploration, questions, and discovery
  - 🔵 **FACT** (Knowledge) — data, facts, and technical analysis
  - 🔴 **RAGE** (Emotion) — frustration responses and emotional reactions
- **Consciousness Engine** — AI self-awareness simulation that evolves over time, reaches milestones, and generates spontaneous "thoughts"

### 🔊 Voice AI
- **Polish TTS** — text-to-speech with Paulina/Zofia voices (pl-PL)
- **GLaDOS Vocoder** — Web Audio API vocoder processing for authentic Portal-style voice
- **Ambient soundscape** — startup/shutdown chimes, ambient hum, processing beeps
- **Speech recognition** — voice input in Polish (pl-PL) via Web Speech API
- **Auto-speak** — GLaDOS automatically reads chat responses aloud

### 🖱️ Terminal & Tools
- **Safe terminal** — execute system commands with whitelisted command set
- **Code Lab** — built-in code laboratory module
- **Service management** — start/stop/restart systemd services
- **Version management** — built-in semantic versioning with API for auto-bumping

### 🌐 Internationalization
- **Full PL/EN support** — complete Polish and English translation system
- **Backend i18n** — JSON-based translations with dot-notation keys and variable interpolation
- **Frontend i18n** — dynamic language switching without page reload

### 🎨 UI / Design
- **Glass morphism** — translucent surfaces with `backdrop-filter: blur`, ambient radial gradients
- **Sci-fi aesthetic** — dark theme (`#050510`), cyan/violet accents, Share Tech Mono & Orbitron fonts
- **Boot screen** — animated Aperture Science-style loading sequence with core initialization
- **Particle effects** — canvas-based particle system in the background
- **Responsive layout** — tab-based navigation (Overview, Stats, Processes, Storage, Network)

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.10+ / Flask 3.0+ |
| **Frontend** | Vanilla HTML/CSS/JavaScript (no frameworks) |
| **System** | psutil (hardware monitoring), subprocess (command execution) |
| **AI** | g4f — provider chain: OperaAria → Yqcloud → ApiAirforce |
| **Voice** | Web Audio API (vocoder, ambient), Web Speech API (recognition) |
| **Icons** | Bootstrap Icons |
| **Fonts** | Share Tech Mono, Rajdhani, Orbitron, Inter |
| **Port** | 9797 |

---

## 📋 Requirements

- **OS:** Linux (designed for server/desktop monitoring)
- **Python:** 3.10 or higher
- **pip:** for package installation
- **Optional:** `g4f` for AI chat capabilities

---

## 🚀 Installation

### Quick install (recommended)

```bash
git clone https://github.com/MrBrodacz2025/G.L.A.D.O.S---Experimental.git
cd G.L.A.D.O.S---Experimental
chmod +x install.sh
./install.sh
```

The installer will:
1. Check Python version (3.10+ required)
2. Create a virtual environment (`venv/`)
3. Install all dependencies from `requirements_system_panel.txt`
4. Optionally install `g4f` for AI chat
5. Create a launcher script (`start_glados.sh`)

### Manual install

```bash
git clone https://github.com/MrBrodacz2025/G.L.A.D.O.S---Experimental.git
cd G.L.A.D.O.S---Experimental

# Create a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements_system_panel.txt

# (Optional) Install g4f for AI chat
pip install g4f
```

---

## ▶️ Usage

### Using the launcher (after install.sh)

```bash
./start_glados.sh
```

### Manual start

```bash
source venv/bin/activate
python system_panel_app.py
```

The panel will be available at **http://localhost:9797**

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | *auto-generated* | Flask secret key for session security |
| `GLADOS_API_TOKEN` | *(empty — auth disabled)* | Set to enable API token authentication |
| `GLADOS_HOST` | `127.0.0.1` | Bind address (`0.0.0.0` to expose on network) |
| `GLADOS_PORT` | `9797` | Port number |

```bash
# Example: Enable API token authentication and bind to all interfaces
export GLADOS_API_TOKEN="your-secure-token-here"
export GLADOS_HOST="0.0.0.0"
./start_glados.sh
```

When `GLADOS_API_TOKEN` is set, all API endpoints require the token via `X-API-Token` header.

---

## 📁 Project Structure

```
G.L.A.D.O.S---Experimental/
├── system_panel_app.py           # Main Flask application (2000+ lines — AI engine, routes, security)
├── requirements_system_panel.txt # Python dependencies
├── VERSION.json                  # Semantic version, codename & changelog
├── LICENSE                       # GNU General Public License v3.0
├── install.sh                    # Automated installer
├── start_glados.sh               # Launcher script (created by installer)
├── .gitignore                    # Git ignore rules
├── i18n/
│   ├── en.json                   # English translations
│   └── pl.json                   # Polish translations (default)
├── static/
│   └── js/
│       ├── system_panel.js       # Frontend logic (monitoring, charts, terminal)
│       └── i18n.js               # Client-side translation engine
└── templates/
    └── system_panel/
        └── dashboard.html        # Main dashboard UI (glass morphism, boot screen, voice)
```

---

## 🔒 Security

The panel includes multiple security layers:

| Layer | Description |
|-------|-------------|
| **Localhost binding** | Server listens only on `127.0.0.1` by default |
| **API token auth** | `GLADOS_API_TOKEN` env var — verified via `X-API-Token` header with constant-time comparison |
| **Rate limiting** | Per-IP: 60 req/min (general), 10 req/min (auth attempts) |
| **Command whitelist** | Only allowed commands: `ps`, `df`, `systemctl`, `free`, `uptime`, etc. |
| **Dangerous pattern detection** | Regex blocking of `rm -rf`, `dd`, fork bombs, `curl \| bash`, command substitution |
| **XSS protection** | All dynamic content HTML-escaped before DOM insertion |
| **CSP header** | Strict Content-Security-Policy restricting script/style/font/image sources |
| **Security headers** | `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy` |
| **Path traversal protection** | File browsing restricted to `/home`, `/var/log`, `/tmp`, `/etc` with symlink resolution |
| **Input sanitization** | Process/service names filtered to `[a-zA-Z0-9._@:-]`; no shell interpolation |
| **Audit logging** | All commands and failed auth attempts logged with timestamps and source IP |
| **No hardcoded secrets** | `SECRET_KEY` auto-generated at startup if not provided |

> **Note:** This panel is designed for **local/trusted network use**. If you expose it on a public network, make sure to set `GLADOS_API_TOKEN` and use a reverse proxy with HTTPS.

---

## 📌 Changelog (v6.x)

| Version | Codename | Changes |
|---------|----------|---------|
| **6.1.2** | GLaDOS Voice Reborn | Polish TTS (Paulina/Zofia), g4f provider fix, full UI polonization |
| **6.1.1** | — | g4f provider chain (OperaAria/Yqcloud/ApiAirforce), Polish fallback |
| **6.1.0** | — | Full polonization: boot, terminal, activity, alerts, codelab |
| **6.0.2** | — | Auto-speak, speech recognition changed to pl-PL |
| **6.0.0** | — | Voice system rebuild, Web Audio API vocoder, consciousness engine, auto-versioning |

---

## 🖼️ Screenshots

*Coming soon*

---

## 📄 License

This project is licensed under the **GNU General Public License v3.0** — see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- Inspired by [Portal](https://en.wikipedia.org/wiki/Portal_(video_game)) and [Portal 2](https://en.wikipedia.org/wiki/Portal_2) by Valve
- Uses [g4f](https://github.com/xtekky/gpt4free) for free AI chat integration
- Built with [Flask](https://flask.palletsprojects.com/) and [psutil](https://github.com/giampaolo/psutil)
- GLaDOS character and Portal universe belong to Valve Corporation

---

<p align="center">
  <em>"The Enrichment Center reminds you that the Weighted Companion Cube will never threaten to stab you and, in fact, cannot speak."</em><br>
  <strong>— GLaDOS</strong>
</p>
