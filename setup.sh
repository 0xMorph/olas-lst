#!/bin/bash
set -e  # Exit on any error

echo "=== OLAS Liquid Staking (stOLAS) Setup ==="

# 1. CONFIGURE GIT (prevents interactive prompts)
echo "Configuring git..."
git config --global advice.detachedHead false 2>/dev/null || true
git config --global init.defaultBranch main 2>/dev/null || true

# Fix SSH submodule URLs to use HTTPS (solmate uses git@github.com)
if [ -f .gitmodules ]; then
    echo "Converting SSH git URLs to HTTPS..."
    sed -i 's|git@github.com:|https://github.com/|g' .gitmodules 2>/dev/null || \
    sed -i '' 's|git@github.com:|https://github.com/|g' .gitmodules 2>/dev/null || true
fi

echo "✓ Git configured"

# 2. INSTALL FOUNDRY
export PATH="$HOME/.foundry/bin:$PATH"

if command -v forge &> /dev/null; then
    echo "✓ Foundry already installed"
else
    echo "Installing Foundry..."
    curl -L https://foundry.paradigm.xyz | bash

    # Source shell configs to get foundryup in PATH
    [ -f "$HOME/.bashrc" ] && source "$HOME/.bashrc" 2>/dev/null || true
    [ -f "$HOME/.profile" ] && source "$HOME/.profile" 2>/dev/null || true
    export PATH="$HOME/.foundry/bin:$PATH"

    if command -v foundryup &> /dev/null; then
        foundryup
    else
        echo "ERROR: foundryup not found after installation"
        exit 1
    fi
fi

# Verify forge is accessible
if ! command -v forge &> /dev/null; then
    echo "ERROR: forge command not found"
    echo "DEBUG: PATH=$PATH"
    echo "DEBUG: Checking $HOME/.foundry/bin:"
    ls -la "$HOME/.foundry/bin" 2>&1 || echo "Directory does not exist"
    exit 1
fi

echo "✓ Using: $(forge --version | head -n1)"

# 3. INSTALL NODE.JS AND YARN
if ! command -v node &> /dev/null; then
    echo "ERROR: Node.js not found. Installing Node.js..."
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
    apt-get install -y nodejs

    if ! command -v node &> /dev/null; then
        echo "ERROR: Node.js installation failed"
        exit 1
    fi
fi

echo "✓ Using Node.js: $(node --version)"

# Install/verify Yarn
if ! command -v yarn &> /dev/null; then
    echo "Installing Yarn..."
    npm install -g yarn

    if ! command -v yarn &> /dev/null; then
        echo "ERROR: Yarn installation failed"
        exit 1
    fi
fi

echo "✓ Using Yarn: $(yarn --version)"

# 4. CLEAN BUILD STATE
echo "Cleaning build artifacts..."
forge clean 2>/dev/null || true
rm -rf node_modules 2>/dev/null || true
rm -rf cache 2>/dev/null || true
rm -rf artifacts 2>/dev/null || true

echo "✓ Build artifacts cleaned"

# 5. INSTALL DEPENDENCIES

# 5a. Install Forge dependencies (git submodules)
echo "Installing Forge dependencies and git submodules..."
forge install

# Verify critical submodules are present
CRITICAL_LIBS=("lib/forge-std" "lib/openzeppelin-contracts" "lib/layerzero-v2")
for lib in "${CRITICAL_LIBS[@]}"; do
    if [ ! -d "$lib" ] || [ ! "$(ls -A $lib)" ]; then
        echo "ERROR: Critical dependency $lib not properly installed"
        echo "Attempting manual submodule initialization..."
        git submodule update --init --recursive

        if [ ! -d "$lib" ] || [ ! "$(ls -A $lib)" ]; then
            echo "ERROR: Failed to install $lib even after manual init"
            exit 1
        fi
    fi
done

echo "✓ Forge dependencies installed"

# 5b. Install Node.js dependencies
echo "Installing Node.js dependencies..."
yarn install --frozen-lockfile 2>/dev/null || yarn install

if [ ! -d "node_modules" ]; then
    echo "ERROR: Node modules not installed"
    exit 1
fi

echo "✓ Node.js dependencies installed"

# 6. BUILD PROJECT
echo "Building Solidity contracts..."
forge build

if [ $? -ne 0 ]; then
    echo "ERROR: Build failed"
    exit 1
fi

# Verify build output exists
if [ ! -d "out" ] || [ ! "$(ls -A out)" ]; then
    echo "ERROR: Build output directory is empty"
    exit 1
fi

echo "✓ Build successful"

# 7. COMPLETION MESSAGE
echo ""
echo "=== Setup complete ==="
echo ""
echo "Environment is ready for validation tasks."
echo ""
echo "Available commands:"
echo "  - forge test              # Run Foundry tests"
echo "  - yarn hardhat test       # Run Hardhat tests"
echo "  - make tests              # Run all tests"
echo "  - forge build             # Rebuild contracts"
echo ""
