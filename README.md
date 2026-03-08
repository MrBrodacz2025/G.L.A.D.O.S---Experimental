# G.L.A.D.O.S System Panel

> **⚠️ Experimental — This project is under active development and is not yet a final release.**

A Portal-inspired autonomous AI system panel built with Flask. G.L.A.D.O.S (Genetic Lifeform and Disk Operating System) monitors your Linux server, executes commands, and responds with the cold, sarcastic personality known from Aperture Science.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Flask](https://img.shields.io/badge/Flask-3.0%2B-green)
![Status](https://img.shields.io/badge/Status-Experimental-orange)

## Features

- **Real-time System Monitoring** — CPU, RAM, disk, network, temperatures, and running processes
- **AI Chat Interface** — Conversational interface with GLaDOS personality powered by g4f (free ChatGPT integration)
- **Portal 2 Personality Cores** — Four cores (ATLAS, RICK, FACT, RAGE) that activate contextually based on your interactions
- **Consciousness Engine** — A self-awareness simulation that evolves over time through interactions
- **System Management** — Execute system commands, manage services, install updates, scan Wi-Fi — all through natural language
- **Proactive Health Checks** — Autonomous monitoring with alerts when CPU, RAM, or disk usage crosses thresholds
- **Version Management** — Built-in semantic versioning with changelog tracking

## Tech Stack

- **Backend:** Python 3 / Flask
- **Frontend:** HTML, CSS, JavaScript (vanilla)
- **System:** psutil for hardware monitoring, subprocess for command execution
- **AI:** g4f (optional, for ChatGPT-style responses)

## Requirements

- Linux (designed for server/desktop monitoring)
- Python 3.10+
- Dependencies listed in `requirements_system_panel.txt`

## Installation

```bash
# Clone the repository
git clone https://github.com/<your-username>/glados-panel.git
cd glados-panel

# Create a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements_system_panel.txt

# (Optional) Install g4f for AI chat capabilities
pip install g4f
```

## Usage

```bash
# Run the panel (binds to localhost by default)
python system_panel_app.py
```

The panel will be available at `http://localhost:9797`.

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
python system_panel_app.py
```

When `GLADOS_API_TOKEN` is set, all API endpoints require the token via `X-API-Token` header.

## Project Structure

```
├── system_panel_app.py          # Main Flask application (GLaDOS AI engine, routes, system commands)
├── requirements_system_panel.txt # Python dependencies
├── VERSION.json                  # Semantic version and changelog
├── static/
│   └── js/
│       └── system_panel.js       # Frontend logic
└── templates/
    └── system_panel/
        └── dashboard.html        # Main dashboard UI
```

## Security

The panel includes the following security layers:

- **Localhost binding by default** — the server only listens on `127.0.0.1` unless explicitly overridden
- **API token authentication** — set `GLADOS_API_TOKEN` to protect all API endpoints; token verified via `X-API-Token` header using constant-time comparison
- **Rate limiting** — per-IP rate limiting (60 req/min general, 10 req/min for auth attempts) to prevent brute force and DoS
- **Command whitelist** — only explicitly allowed system commands (`ps`, `df`, `systemctl`, etc.) can be executed via the terminal interface
- **Dangerous pattern detection** — regex-based blocking of destructive commands (`rm -rf`, `dd`, fork bombs, `curl | bash`, command substitution, etc.)
- **XSS protection** — all dynamic content is HTML-escaped before DOM insertion; `simpleMarkdown()` escapes HTML before applying formatting
- **Content Security Policy (CSP)** — strict CSP header restricting script/style/font/image sources
- **Security headers** — `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`
- **Path traversal protection** — file browsing restricted to safe directories (`/home`, `/var/log`, `/tmp`, `/etc`) with symlink resolution via `os.path.realpath()`
- **Input sanitization** — process and service names filtered to `[a-zA-Z0-9._@:-]`; no shell interpolation in subprocess calls
- **Audit logging** — all commands and failed auth attempts are logged with timestamps and source IP
- **No hardcoded secrets** — `SECRET_KEY` is auto-generated at startup if not provided via environment

> **Note:** This panel is designed for **local/trusted network use**. If you expose it on a public network, make sure to set `GLADOS_API_TOKEN` and use a reverse proxy with HTTPS.

## Screenshots

*Coming soon*

## License

This project is currently unlicensed. A license will be added in a future release.

## Acknowledgments

- Inspired by [Portal](https://en.wikipedia.org/wiki/Portal_(video_game)) and [Portal 2](https://en.wikipedia.org/wiki/Portal_2) by Valve
- Uses [g4f](https://github.com/xtekky/gpt4free) for free AI chat integration
- Built with [Flask](https://flask.palletsprojects.com/) and [psutil](https://github.com/giampaolo/psutil)
