#!/usr/bin/env bash
# ============================================
# G.L.A.D.O.S System Panel — Installer
# ============================================
# Automated setup for the GLaDOS System Panel.
# Creates venv, installs dependencies, and
# generates a launcher script.
# ============================================

set -e

# --- Colors ---
CYAN='\033[0;36m'
PURPLE='\033[0;35m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

# --- Paths ---
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"
REQ_FILE="$SCRIPT_DIR/requirements_system_panel.txt"
LAUNCHER="$SCRIPT_DIR/start_glados.sh"
MIN_PYTHON_MAJOR=3
MIN_PYTHON_MINOR=10

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║${NC}  ${BOLD}G.L.A.D.O.S System Panel — Installer${NC}            ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}  ${PURPLE}Genetic Lifeform and Disk Operating System${NC}     ${CYAN}║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
echo ""

# ======================
# 1. Check Python
# ======================
echo -e "${BOLD}[1/5]${NC} Checking Python version..."

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
    echo -e "${RED}✗ Python ${MIN_PYTHON_MAJOR}.${MIN_PYTHON_MINOR}+ is required but not found.${NC}"
    echo "  Install it with your package manager, e.g.:"
    echo "    sudo dnf install python3    (Fedora)"
    echo "    sudo apt install python3    (Debian/Ubuntu)"
    exit 1
fi

echo -e "${GREEN}✓${NC} Found $PYTHON_CMD ($PY_VER)"

# ======================
# 2. Check pip & venv
# ======================
echo -e "${BOLD}[2/5]${NC} Checking pip and venv module..."

if ! "$PYTHON_CMD" -m pip --version &>/dev/null; then
    echo -e "${RED}✗ pip not found.${NC}"
    echo "  Install it with: $PYTHON_CMD -m ensurepip --upgrade"
    echo "  Or: sudo dnf install python3-pip / sudo apt install python3-pip"
    exit 1
fi

if ! "$PYTHON_CMD" -c "import venv" &>/dev/null; then
    echo -e "${RED}✗ venv module not found.${NC}"
    echo "  Install it with: sudo dnf install python3-venv / sudo apt install python3-venv"
    exit 1
fi

echo -e "${GREEN}✓${NC} pip and venv available"

# ======================
# 3. Create virtual environment
# ======================
echo -e "${BOLD}[3/5]${NC} Setting up virtual environment..."

if [ -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}!${NC} Virtual environment already exists at $VENV_DIR"
    read -rp "  Recreate it? [y/N] " recreate
    if [[ "$recreate" =~ ^[Yy]$ ]]; then
        rm -rf "$VENV_DIR"
        "$PYTHON_CMD" -m venv "$VENV_DIR"
        echo -e "${GREEN}✓${NC} Virtual environment recreated"
    else
        echo -e "${GREEN}✓${NC} Using existing virtual environment"
    fi
else
    "$PYTHON_CMD" -m venv "$VENV_DIR"
    echo -e "${GREEN}✓${NC} Virtual environment created at $VENV_DIR"
fi

# Activate
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# ======================
# 4. Install dependencies
# ======================
echo -e "${BOLD}[4/5]${NC} Installing dependencies..."

pip install --upgrade pip --quiet

if [ -f "$REQ_FILE" ]; then
    pip install -r "$REQ_FILE" --quiet
    echo -e "${GREEN}✓${NC} Core dependencies installed (flask, psutil)"
else
    echo -e "${YELLOW}!${NC} requirements file not found, installing manually..."
    pip install flask psutil --quiet
    echo -e "${GREEN}✓${NC} flask and psutil installed"
fi

# Optional: g4f
echo ""
read -rp "  Install g4f for AI chat capabilities? [Y/n] " install_g4f
if [[ ! "$install_g4f" =~ ^[Nn]$ ]]; then
    echo "  Installing g4f (this may take a moment)..."
    pip install g4f --quiet 2>/dev/null && \
        echo -e "  ${GREEN}✓${NC} g4f installed" || \
        echo -e "  ${YELLOW}!${NC} g4f installation failed (non-critical — panel works without it)"
fi

# ======================
# 5. Create launcher
# ======================
echo -e "${BOLD}[5/5]${NC} Creating launcher script..."

cat > "$LAUNCHER" << 'LAUNCHER_EOF'
#!/usr/bin/env bash
# G.L.A.D.O.S System Panel — Launcher
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/venv/bin/activate"
cd "$SCRIPT_DIR"
echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║   G.L.A.D.O.S System Panel          ║"
echo "  ║   http://localhost:${GLADOS_PORT:-9797}              ║"
echo "  ╚══════════════════════════════════════╝"
echo ""
exec python system_panel_app.py "$@"
LAUNCHER_EOF

chmod +x "$LAUNCHER"
echo -e "${GREEN}✓${NC} Launcher created: start_glados.sh"

# ======================
# Done
# ======================
echo ""
echo -e "${CYAN}══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}${BOLD}  ✓ Installation complete!${NC}"
echo -e "${CYAN}══════════════════════════════════════════════════${NC}"
echo ""
echo -e "  To start the panel:"
echo -e "    ${BOLD}./start_glados.sh${NC}"
echo ""
echo -e "  Or manually:"
echo -e "    source venv/bin/activate"
echo -e "    python system_panel_app.py"
echo ""
echo -e "  Dashboard: ${CYAN}http://localhost:9797${NC}"
echo ""
echo -e "  ${PURPLE}\"The Enrichment Center is required to remind you"
echo -e "   that you will be baked, and then there will be cake.\"${NC}"
echo -e "                                           ${BOLD}— GLaDOS${NC}"
echo ""
