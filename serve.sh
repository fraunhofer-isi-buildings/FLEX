#!/bin/bash
# FLEX - Local Development Server
#
# Usage:
#   ./serve.sh docs                # Build and serve Sphinx docs at http://127.0.0.1:8000
#   ./serve.sh docs install        # Install Sphinx dependencies first, then serve
#   ./serve.sh docs autobuild      # Auto-rebuild on file changes
#   ./serve.sh slides              # Start Slidev dev server (opens browser)
#   ./serve.sh slides install      # Install Slidev dependencies first, then serve
#   ./serve.sh slides build        # Build slides to static HTML
#   ./serve.sh slides export       # Export slides to PDF

set -e

DOCS_DIR="docs/documentation"
DOCS_BUILD_DIR="docs/documentation/_build/html"
SLIDES_DIR="docs/slides"

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
        sphinx-autobuild "$DOCS_DIR" "$DOCS_BUILD_DIR"
        exit 0
    fi

    echo "Building documentation..."
    sphinx-build -b html "$DOCS_DIR" "$DOCS_BUILD_DIR"
    echo ""
    echo "Serving documentation at http://127.0.0.1:8000"
    echo "Press Ctrl+C to stop."
    echo ""
    cd "$DOCS_BUILD_DIR"
    python -m http.server 8000
}

serve_slides() {
    local action="$1"

    if [ "$action" = "install" ]; then
        echo "Installing Slidev dependencies..."
        cd "$SLIDES_DIR"
        npm install
        echo ""
        echo "Dependencies installed. Run ./serve.sh slides to start."
        exit 0
    fi

    if [ ! -d "$SLIDES_DIR/node_modules" ]; then
        echo "Error: node_modules not found."
        echo "Run: ./serve.sh slides install"
        exit 1
    fi

    if [ "$action" = "build" ]; then
        echo "Building slides to static HTML..."
        cd "$SLIDES_DIR"
        npx slidev build slides.md
        echo ""
        echo "Static slides built to $SLIDES_DIR/dist/"
        exit 0
    fi

    if [ "$action" = "export" ]; then
        echo "Exporting slides to PDF..."
        cd "$SLIDES_DIR"
        npx slidev export slides.md
        echo ""
        echo "PDF exported."
        exit 0
    fi

    echo "Starting Slidev dev server..."
    echo "Press Ctrl+C to stop."
    echo ""
    cd "$SLIDES_DIR"
    npx slidev slides.md --open
}

case "$1" in
    docs)
        serve_docs "$2"
        ;;
    slides)
        serve_slides "$2"
        ;;
    *)
        echo "FLEX - Local Development Server"
        echo ""
        echo "Usage: ./serve.sh <target> [action]"
        echo ""
        echo "  docs                Build and serve Sphinx documentation"
        echo "  docs install        Install Sphinx dependencies first"
        echo "  docs autobuild      Auto-rebuild on file changes"
        echo ""
        echo "  slides              Start Slidev presentation (opens browser)"
        echo "  slides install      Install Slidev dependencies"
        echo "  slides build        Build slides to static HTML"
        echo "  slides export       Export slides to PDF"
        exit 1
        ;;
esac
