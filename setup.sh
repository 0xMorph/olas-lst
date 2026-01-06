#!/bin/bash
set -e

echo "=== OLAS Liquid Staking Setup ==="

# Configure git for non-interactive operations
git config --global advice.detachedHead false 2>/dev/null || true

# Fix SSH submodule URLs to HTTPS
if [ -f .gitmodules ]; then
    sed -i 's|git@github.com:|https://github.com/|g' .gitmodules 2>/dev/null || \
    sed -i '' 's|git@github.com:|https://github.com/|g' .gitmodules 2>/dev/null || true
fi

# Install Foundry if needed
export PATH="$HOME/.foundry/bin:$PATH"

if ! command -v forge &> /dev/null; then
    echo "Installing Foundry..."
    curl -L https://foundry.paradigm.xyz | bash
    source "$HOME/.bashrc" 2>/dev/null || true
    export PATH="$HOME/.foundry/bin:$PATH"
    foundryup
fi

echo "✓ Using $(forge --version | head -n1)"

# Install dependencies
echo "Installing dependencies..."
forge install
yarn install

# Build
echo "Building contracts..."
forge build

echo ""
echo "✓ Setup complete"
echo ""
