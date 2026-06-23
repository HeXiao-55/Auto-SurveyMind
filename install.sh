#!/bin/bash
# SurveyMind Installation Script
# Usage: ./install.sh

set -e

echo "=================================="
echo "  SurveyMind Installation"
echo "=================================="

# Detect OS
OS="$(uname -s)"
echo "[1/5] Detecting OS: $OS"

# Step 1: Create Claude skills directory
echo "[2/5] Setting up Claude skills directory..."
SKILLS_DIR="$HOME/.claude/skills"
if [ ! -d "$SKILLS_DIR" ]; then
    mkdir -p "$SKILLS_DIR"
    echo "  Created: $SKILLS_DIR"
else
    echo "  Already exists: $SKILLS_DIR"
fi

# Step 2: Copy skills to Claude directory
echo "[3/5] Installing SurveyMind skills..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -d "$SCRIPT_DIR/skills" ]; then
    # Copy each skill directory
    for skill_dir in "$SCRIPT_DIR/skills"/*/; do
        skill_name=$(basename "$skill_dir")
        target_dir="$SKILLS_DIR/$skill_name"

        # Skip empty skill directories (no SKILL.md)
        if [ ! -f "$skill_dir/SKILL.md" ]; then
            echo "  Skipping: $skill_name (empty, no SKILL.md)"
            continue
        fi

        if [ -d "$target_dir" ]; then
            echo "  Updating: $skill_name"
            cp -r "$skill_dir/." "$target_dir/"
        else
            echo "  Installing: $skill_name"
            cp -r "$skill_dir" "$target_dir"
        fi
    done
    echo "  Skills installed successfully!"
else
    echo "  Warning: skills/ directory not found in $SCRIPT_DIR"
fi

# Step 3: Install SSL certificates (macOS only)
if [ "$OS" = "Darwin" ]; then
    echo "[4/5] Installing SSL certificates for macOS..."

    # Check if certificates are already installed
    if [ -f "/etc/ssl/cert.pem" ]; then
        echo "  SSL certificates already installed"
    else
        # Install homebrew certificates if available
        if command -v brew &> /dev/null; then
            echo "  Running: brew install curl-ca-bundle"
            brew install curl-ca-bundle 2>/dev/null || true

            # Create symlink if needed
            if [ -f "$(brew --prefix)/opt/curl-ca-bundle/share/ca-bundle.crt" ]; then
                sudo ln -sf "$(brew --prefix)/opt/curl-ca-bundle/share/ca-bundle.crt" /etc/ssl/cert.pem 2>/dev/null || true
                echo "  SSL certificates installed via Homebrew"
            fi
        else
            echo "  Warning: Homebrew not found. You may need to install SSL certificates manually."
            echo "  Run: /Applications/Python\ 3.x/Install\ Certificates.command"
        fi
    fi
else
    echo "[4/5] Skipping SSL setup (not macOS)"
fi

# Step 4: Verify installation
echo "[5/5] Verifying installation..."
INSTALLED_COUNT=0
for skill_name in survey-pipeline research-lit paper-analysis taxonomy-build gap-identify survey-write code-discover repo-setup repo-reproduce repo-adapt reproduce-pipeline task-parser algo-plan algo-implement reflect-improve model-deliver algo-pipeline; do
    if [ -f "$SKILLS_DIR/$skill_name/SKILL.md" ]; then
        INSTALLED_COUNT=$((INSTALLED_COUNT + 1))
    fi
done
echo "  Installed $INSTALLED_COUNT skills"

# Create default workspace directories
mkdir -p "$SCRIPT_DIR/surveys"
mkdir -p "$SCRIPT_DIR/experiments"
mkdir -p "$SCRIPT_DIR/data"
echo "  Created output base: $SCRIPT_DIR/surveys"
echo "  Created experiments dir: $SCRIPT_DIR/experiments"
echo "  Created data dir: $SCRIPT_DIR/data"

echo ""
echo "=================================="
echo "  Installation Complete!"
echo "=================================="
echo ""
echo "Next steps:"
echo "  1. Configure API keys (optional):"
echo "     export ARXIV_API_KEY=your_key"
echo "     export GEMINI_API_KEY=your_key"
echo ""
echo "  2. Start SurveyMind:"
echo "     claude"
echo ""
echo "  3. Run a survey:"
echo "     > /survey-pipeline \"your research topic\""
echo ""
echo "  4. Run algorithm R&D pipeline (WiFi CSI HAR):"
echo "     > /algo-pipeline \"WiFi CSI人体行为识别，CPU，85%准确率\""
echo ""
echo "  5. Start the Dashboard:"
echo "     pip install gradio matplotlib"
echo "     python3 mcp-servers/dashboard/server.py"
echo ""
echo "Survey outputs:   $SCRIPT_DIR/surveys/survey_<topic_slug>/"
echo "Algo experiments: $SCRIPT_DIR/experiments/task_<id>/"
echo ""
