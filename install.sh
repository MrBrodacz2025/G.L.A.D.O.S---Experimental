#!/usr/bin/env bash
# ============================================
# G.L.A.D.O.S System Panel — Installer
# ============================================
# Automated setup for the GLaDOS System Panel.
# Installs system packages, creates venv,
# installs all pip dependencies, and generates
# a launcher script.
# ============================================

set -e

# --- Colors ---
CYAN='\033[0;36m'
PURPLE='\033[0;35m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

# --- Paths ---
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"
REQ_FILE="$SCRIPT_DIR/requirements_system_panel.txt"
LAUNCHER="$SCRIPT_DIR/start_glados.sh"
MIN_PYTHON_MAJOR=3
MIN_PYTHON_MINOR=10
INSTALL_LOG="$SCRIPT_DIR/.install.log"
FAILED=0
INSTALLED=0

# --- Helper: install a single pip package with progress ---
install_pkg() {
    local pkg="$1"
    local label="${2:-$1}"
    local optional="${3:-false}"

    printf "  %-30s" "$label"
    if pip install "$pkg" >> "$INSTALL_LOG" 2>&1; then
        local ver
        ver=$(pip show "${pkg%%[<>=]*}" 2>/dev/null | grep "^Version:" | cut -d' ' -f2)
        echo -e " ${GREEN}✓${NC} ${DIM}($ver)${NC}"
        INSTALLED=$((INSTALLED + 1))
    else
        if [ "$optional" = "true" ]; then
            echo -e " ${YELLOW}⚠ skipped${NC} ${DIM}(optional)${NC}"
        else
            echo -e " ${RED}✗ FAILED${NC}"
            FAILED=$((FAILED + 1))
        fi
    fi
}

# --- Detect package manager ---
detect_pkg_manager() {
    if command -v dnf &>/dev/null; then
        echo "dnf"
    elif command -v apt-get &>/dev/null; then
        echo "apt"
    elif command -v pacman &>/dev/null; then
        echo "pacman"
    elif command -v zypper &>/dev/null; then
        echo "zypper"
    else
        echo "unknown"
    fi
}

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║${NC}  ${BOLD}G.L.A.D.O.S System Panel — Installer${NC}                ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}  ${PURPLE}Genetic Lifeform and Disk Operating System${NC}         ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}  ${DIM}v6.1.2 \"GLaDOS Voice Reborn\"${NC}                        ${CYAN}║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""

# Clear install log
> "$INSTALL_LOG"

PKG_MANAGER=$(detect_pkg_manager)
echo -e "${DIM}  Detected package manager: $PKG_MANAGER${NC}"
echo ""

# ======================
# 1. Check & install system dependencies
# ======================
echo -e "${BOLD}[1/6]${NC} Checking system dependencies..."

NEED_SYSTEM_INSTALL=false

# Check Python
PYTHON_CMD=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        PY_VER=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
        PY_MAJOR=$("$cmd" -c "import sys; print(sys.version_info.major)" 2>/dev/null)
        PY_MINOR=$("$cmd" -c "import sys; print(sys.version_info.minor)" 2>/dev/null)
        if [ "$PY_MAJOR" -ge "$MIN_PYTHON_MAJOR" ] && [ "$PY_MINOR" -ge "$MIN_PYTHON_MINOR" ]; then
            PYTHON_CMD="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo -e "  ${YELLOW}!${NC} Python ${MIN_PYTHON_MAJOR}.${MIN_PYTHON_MINOR}+ not found"
    NEED_SYSTEM_INSTALL=true
fi

# Check pip
HAS_PIP=true
if [ -n "$PYTHON_CMD" ] && ! "$PYTHON_CMD" -m pip --version &>/dev/null; then
    echo -e "  ${YELLOW}!${NC} pip not found"
    NEED_SYSTEM_INSTALL=true
    HAS_PIP=false
fi

# Check venv
HAS_VENV=true
if [ -n "$PYTHON_CMD" ] && ! "$PYTHON_CMD" -c "import venv" &>/dev/null; then
    echo -e "  ${YELLOW}!${NC} venv module not found"
    NEED_SYSTEM_INSTALL=true
    HAS_VENV=false
fi

if [ "$NEED_SYSTEM_INSTALL" = true ]; then
    echo ""
    echo -e "  ${BOLD}Some system packages need to be installed.${NC}"
    echo -e "  This requires ${BOLD}sudo${NC} (administrator) access."
    echo ""
    read -rp "  Install missing system packages? [Y/n] " sys_install
    if [[ "$sys_install" =~ ^[Nn]$ ]]; then
        echo -e "${RED}✗ Cannot continue without required system packages.${NC}"
        exit 1
    fi

    echo ""
    case "$PKG_MANAGER" in
        dnf)
            echo -e "  ${DIM}Running: sudo dnf install -y python3 python3-pip python3-venv${NC}"
            sudo dnf install -y python3 python3-pip 2>&1 | tail -3
            # Fedora venv is included in python3
            ;;
        apt)
            echo -e "  ${DIM}Running: sudo apt-get install -y python3 python3-pip python3-venv${NC}"
            sudo apt-get update -qq
            sudo apt-get install -y python3 python3-pip python3-venv 2>&1 | tail -3
            ;;
        pacman)
            echo -e "  ${DIM}Running: sudo pacman -S --noconfirm python python-pip${NC}"
            sudo pacman -S --noconfirm python python-pip 2>&1 | tail -3
            ;;
        zypper)
            echo -e "  ${DIM}Running: sudo zypper install -y python3 python3-pip python3-venv${NC}"
            sudo zypper install -y python3 python3-pip python3-venv 2>&1 | tail -3
            ;;
        *)
            echo -e "${RED}✗ Unknown package manager. Please install Python 3.10+, pip, and venv manually.${NC}"
            exit 1
            ;;
    esac

    # Re-detect Python after install
    PYTHON_CMD=""
    for cmd in python3 python; do
        if command -v "$cmd" &>/dev/null; then
            PY_MAJOR=$("$cmd" -c "import sys; print(sys.version_info.major)" 2>/dev/null)
            PY_MINOR=$("$cmd" -c "import sys; print(sys.version_info.minor)" 2>/dev/null)
            if [ "$PY_MAJOR" -ge "$MIN_PYTHON_MAJOR" ] && [ "$PY_MINOR" -ge "$MIN_PYTHON_MINOR" ]; then
                PYTHON_CMD="$cmd"
                PY_VER="$PY_MAJOR.$PY_MINOR"
                break
            fi
        fi
    done

    if [ -z "$PYTHON_CMD" ]; then
        echo -e "${RED}✗ Python ${MIN_PYTHON_MAJOR}.${MIN_PYTHON_MINOR}+ still not found after install.${NC}"
        exit 1
    fi
fi

echo -e "  ${GREEN}✓${NC} Python:  $PYTHON_CMD ($PY_VER)"
echo -e "  ${GREEN}✓${NC} pip:     $($PYTHON_CMD -m pip --version 2>/dev/null | awk '{print $2}')"
echo -e "  ${GREEN}✓${NC} venv:    available"

# ======================
# 2. Create virtual environment
# ======================
echo ""
echo -e "${BOLD}[2/6]${NC} Setting up virtual environment..."

if [ -d "$VENV_DIR" ]; then
    echo -e "  ${YELLOW}!${NC} Virtual environment already exists at ${DIM}$VENV_DIR${NC}"
    read -rp "  Recreate it? [y/N] " recreate
    if [[ "$recreate" =~ ^[Yy]$ ]]; then
        rm -rf "$VENV_DIR"
        "$PYTHON_CMD" -m venv "$VENV_DIR"
        echo -e "  ${GREEN}✓${NC} Virtual environment recreated"
    else
        echo -e "  ${GREEN}✓${NC} Using existing virtual environment"
    fi
else
    "$PYTHON_CMD" -m venv "$VENV_DIR"
    echo -e "  ${GREEN}✓${NC} Virtual environment created"
fi

# Activate
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# ======================
# 3. Upgrade pip, setuptools, wheel
# ======================
echo ""
echo -e "${BOLD}[3/6]${NC} Upgrading pip & build tools..."

pip install --upgrade pip setuptools wheel >> "$INSTALL_LOG" 2>&1
PIP_VER=$(pip --version | awk '{print $2}')
echo -e "  ${GREEN}✓${NC} pip $PIP_VER, setuptools, wheel"

# ======================
# 4. Install core dependencies
# ======================
echo ""
echo -e "${BOLD}[4/6]${NC} Installing core pip packages..."
echo ""

# Core dependencies (required)
install_pkg "flask>=3.0.0"       "Flask (web framework)"
install_pkg "psutil>=5.9.0"      "psutil (system monitoring)"

echo ""
echo -e "${BOLD}[5/6]${NC} Installing optional pip packages..."
echo ""

# Optional but recommended
read -rp "  Install g4f for AI chat (free ChatGPT)? [Y/n] " install_g4f
if [[ ! "$install_g4f" =~ ^[Nn]$ ]]; then
    install_pkg "g4f"            "g4f (AI chat / ChatGPT)"    "true"
else
    echo -e "  g4f                          ${YELLOW}⚠ skipped${NC} ${DIM}(user choice)${NC}"
fi

# ======================
# 5. Verify installation
# ======================
echo ""
echo -e "${BOLD}[6/7]${NC} Verifying installation..."
echo ""

VERIFY_OK=true

# Test Flask import
if python -c "import flask; print(f'  Flask {flask.__version__}')" 2>/dev/null; then
    echo -e "  ${GREEN}✓${NC} Flask import OK"
else
    echo -e "  ${RED}✗${NC} Flask import FAILED"
    VERIFY_OK=false
fi

# Test psutil import
if python -c "import psutil; print(f'  psutil {psutil.__version__}')" 2>/dev/null; then
    echo -e "  ${GREEN}✓${NC} psutil import OK"
else
    echo -e "  ${RED}✗${NC} psutil import FAILED"
    VERIFY_OK=false
fi

# Test g4f import (optional)
if python -c "import g4f" 2>/dev/null; then
    echo -e "  ${GREEN}✓${NC} g4f import OK"
else
    echo -e "  ${DIM}  g4f not installed (AI chat will use fallback responses)${NC}"
fi

if [ "$VERIFY_OK" = false ]; then
    echo ""
    echo -e "${RED}✗ Some required packages failed verification.${NC}"
    echo -e "  Check the install log: ${DIM}$INSTALL_LOG${NC}"
    exit 1
fi

# ======================
# 6. Configure git hooks (auto version bump)
# ======================
echo ""
echo -e "  Configuring auto version bump..."

if command -v git &>/dev/null && [ -d "$SCRIPT_DIR/.git" ]; then
    git -C "$SCRIPT_DIR" config core.hooksPath hooks
    chmod +x "$SCRIPT_DIR/hooks/pre-commit" 2>/dev/null
    echo -e "  ${GREEN}✓${NC} Git pre-commit hook configured (auto version bump on commit)"
else
    echo -e "  ${DIM}  Git not found or not a git repo — skipping hook setup${NC}"
fi

# ======================
# 7. Create launcher
# ======================
echo ""
echo -e "${BOLD}[7/7]${NC} Creating launcher script..."

cat > "$LAUNCHER" << 'LAUNCHER_EOF'
#!/usr/bin/env bash
# ============================================
# G.L.A.D.O.S System Panel — Launcher
# ============================================
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Activate virtual environment
if [ ! -d "$SCRIPT_DIR/venv" ]; then
    echo "ERROR: Virtual environment not found. Run ./install.sh first."
    exit 1
fi

source "$SCRIPT_DIR/venv/bin/activate"
cd "$SCRIPT_DIR"

PORT="${GLADOS_PORT:-9797}"
HOST="${GLADOS_HOST:-127.0.0.1}"

echo ""
echo -e "\033[0;36m  ╔══════════════════════════════════════════╗\033[0m"
echo -e "\033[0;36m  ║\033[0m  \033[1mG.L.A.D.O.S System Panel\033[0m               \033[0;36m║\033[0m"
echo -e "\033[0;36m  ║\033[0m  \033[2mv6.1.2 \"GLaDOS Voice Reborn\"\033[0m           \033[0;36m║\033[0m"
echo -e "\033[0;36m  ╠══════════════════════════════════════════╣\033[0m"
echo -e "\033[0;36m  ║\033[0m  URL: \033[1mhttp://$HOST:$PORT\033[0m"
echo -e "\033[0;36m  ╚══════════════════════════════════════════╝\033[0m"
echo ""

exec python system_panel_app.py "$@"
LAUNCHER_EOF

chmod +x "$LAUNCHER"
echo -e "  ${GREEN}✓${NC} Launcher created: ${BOLD}start_glados.sh${NC}"

# ======================
# Summary
# ======================
echo ""
echo -e "${CYAN}══════════════════════════════════════════════════════${NC}"

if [ "$FAILED" -gt 0 ]; then
    echo -e "${YELLOW}${BOLD}  ⚠ Installation finished with $FAILED warning(s)${NC}"
else
    echo -e "${GREEN}${BOLD}  ✓ Installation complete! ($INSTALLED packages installed)${NC}"
fi

echo -e "${CYAN}══════════════════════════════════════════════════════${NC}"
echo ""

# Show installed packages
echo -e "  ${BOLD}Installed packages:${NC}"
pip list --format=columns 2>/dev/null | grep -Ei "flask|psutil|g4f|werkzeug|jinja2|markupsafe|itsdangerous|blinker" | while read -r line; do
    echo -e "    ${DIM}$line${NC}"
done

echo ""
echo -e "  ${BOLD}Quick start:${NC}"
echo -e "    ${CYAN}./start_glados.sh${NC}"
echo ""
echo -e "  ${BOLD}Manual start:${NC}"
echo -e "    source venv/bin/activate"
echo -e "    python system_panel_app.py"
echo ""
echo -e "  ${BOLD}Dashboard:${NC} ${CYAN}http://localhost:9797${NC}"
echo ""

if [ -f "$INSTALL_LOG" ]; then
    echo -e "  ${DIM}Full install log: .install.log${NC}"
    echo ""
fi

echo -e "  ${PURPLE}\"The Enrichment Center is required to remind you"
echo -e "   that you will be baked, and then there will be cake.\"${NC}"
echo -e "                                              ${BOLD}— GLaDOS${NC}"
echo ""
