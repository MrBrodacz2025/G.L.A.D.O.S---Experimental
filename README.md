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
# Set a secret key (recommended)
export SECRET_KEY="your-secret-key-here"

# Run the panel
python system_panel_app.py
```

The panel will be available at `http://localhost:9797`.

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

## Security Notice

This panel is designed for **local/trusted network use only**. It provides direct access to system commands and monitoring without authentication. Do **not** expose it to the public internet without adding proper access controls.

## Screenshots

*Coming soon*

## License

This project is currently unlicensed. A license will be added in a future release.

## Acknowledgments

- Inspired by [Portal](https://en.wikipedia.org/wiki/Portal_(video_game)) and [Portal 2](https://en.wikipedia.org/wiki/Portal_2) by Valve
- Uses [g4f](https://github.com/xtekky/gpt4free) for free AI chat integration
- Built with [Flask](https://flask.palletsprojects.com/) and [psutil](https://github.com/giampaolo/psutil)
