#!/bin/bash

# Cynapse Launcher & Setup Script
# Automatically handles virtual environment creation, activation, and dependency installation.

set -e  # Exit on error

# Directory of this script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VENV_DIR="$DIR/.venv"
REQUIREMENTS_CORE="$DIR/requirements.txt"
REQUIREMENTS_FULL="$DIR/requirements-full.txt"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Initializing Cynapse Environment...${NC}"

# 1. Check/Create Virtual Environment
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}Virtual environment not found. Creating one...${NC}"
    python3 -m venv "$VENV_DIR"
    echo -e "${GREEN}Virtual environment created at $VENV_DIR${NC}"
else
    echo -e "${GREEN}Virtual environment found.${NC}"
fi

# 2. Activate Virtual Environment
source "$VENV_DIR/bin/activate"

# 3. Check/Install Dependencies
# We use a marker file to observe if requirements have been installed to avoid re-running pip every time
# But if requirements.txt changes, we should probably re-run. For now, simple check.
if ! python3 -c "import numpy" &> /dev/null; then
    echo -e "${YELLOW}Core dependencies missing. Installing...${NC}"
    pip install -r "$REQUIREMENTS_CORE"
    echo -e "${GREEN}Core dependencies installed.${NC}"
fi

# Optional: Check if full requirements are requested or if we should just warn
# For now, we'll stick to core to ensure it runs.
# Users can manually install full requirements if they want AI features instantly,
# or we can prompt them. For this script, let's keep it non-interactive and safe.

# 4. Run Cynapse
echo -e "${GREEN}Launching Cynapse...${NC}"
# Pass all arguments to the python script
exec python "$DIR/cynapse_entry.py" "$@"
