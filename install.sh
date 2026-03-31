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

        if [ -d "$target_dir" ]; then
            echo "  Updating: $skill_name"
            cp -r "$skill_dir"* "$target_dir/"
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
for skill_name in survey-pipeline research-lit paper-analysis taxonomy-build gap-identify survey-write; do
    if [ -f "$SKILLS_DIR/$skill_name/SKILL.md" ]; then
        INSTALLED_COUNT=$((INSTALLED_COUNT + 1))
    fi
done
echo "  Installed $INSTALLED_COUNT skills"

# Create default workspace surveys directory
mkdir -p "$SCRIPT_DIR/surveys"
echo "  Created output base: $SCRIPT_DIR/surveys"

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
echo "Output will be saved under: $SCRIPT_DIR/surveys/survey_<topic_slug>/"
echo ""
