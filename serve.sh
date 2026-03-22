#!/bin/bash
# FLEX - Local Development Server
#
# Usage:
#   ./serve.sh docs                # Build and serve Sphinx docs at http://127.0.0.1:8000
#   ./serve.sh docs install        # Install Sphinx dependencies first, then serve
#   ./serve.sh docs autobuild      # Auto-rebuild on file changes

set -e

DOCS_DIR="docs"
BUILD_DIR="docs/_build/html"

serve_docs() {
    local action="$1"

    if [ "$action" = "install" ]; then
        echo "Installing documentation dependencies..."
        pip install sphinx myst-parser sphinx-rtd-theme sphinx-autobuild
        echo ""
    fi

    if ! command -v sphinx-build &> /dev/null; then
        echo "Error: sphinx-build is not installed."
        echo "Run: ./serve.sh docs install"
        exit 1
    fi

    if [ "$action" = "autobuild" ]; then
        if ! command -v sphinx-autobuild &> /dev/null; then
            echo "Error: sphinx-autobuild is not installed."
            echo "Run: pip install sphinx-autobuild"
            exit 1
        fi
        echo "Starting auto-rebuild server..."
        echo "Open http://127.0.0.1:8000 in your browser"
        echo ""
        sphinx-autobuild "$DOCS_DIR" "$BUILD_DIR"
        exit 0
    fi

    echo "Building documentation..."
    sphinx-build -b html "$DOCS_DIR" "$BUILD_DIR"
    echo ""
    echo "Serving documentation at http://127.0.0.1:8000"
    echo "Press Ctrl+C to stop."
    echo ""
    cd "$BUILD_DIR"
    python -m http.server 8000
}

case "$1" in
    docs)
        serve_docs "$2"
        ;;
    *)
        echo "Usage: ./serve.sh docs [action]"
        echo ""
        echo "  docs                Build and serve Sphinx documentation"
        echo "  docs install        Install dependencies first"
        echo "  docs autobuild      Auto-rebuild on file changes"
        exit 1
        ;;
esac
