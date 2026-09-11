#!/usr/bin/env bash
# ==============================================================================
# CyberShield — Predictive Cash Egress Interception Platform (SIH26184)
# Unified Backend Services & Live Gateway Launcher
# ==============================================================================

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

# ANSI Colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m' # No Color

log_info() { echo -e "${CYAN}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Detect Python interpreter
if [ -f "$REPO_ROOT/.venv/bin/python" ]; then
    PYTHON="$REPO_ROOT/.venv/bin/python"
elif command -v python3 &>/dev/null; then
    PYTHON="python3"
else
    PYTHON="python"
fi

print_header() {
    echo -e "${BOLD}${CYAN}"
    echo "=================================================================="
    echo "  🛡️  CyberShield: Predictive Cash Egress Interception (SIH26184)"
    echo "  Backend Stack: FastAPI (5003) | Mock Bank (8001) | NCRP (8002)"
    echo "  Live Gateway: https://sih.seucra.tech | wss://sih.seucra.tech/ws"
    echo "=================================================================="
    echo -e "${NC}"
}

print_help() {
    print_header
    echo "Usage: ./run.sh [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  server          Start complete backend stack & Cloudflare tunnel (Default)"
    echo "  backend         Alias for 'server'"
    echo "  demo            Run Phase 2 E2E demo scenario in terminal"
    echo "  test            Run full pytest test suite (145 tests)"
    echo "  pipeline        Start local Kafka pipeline and stream synthetic transactions"
    echo "  app             Build and deploy Android APK to connected device via ADB"
    echo "  help            Show this help menu"
    echo ""
}

run_server() {
    # 1. Cloudflare Tunnel (sih.seucra.tech -> localhost:5003)
    PID_CF=""
    if command -v cloudflared &>/dev/null; then
        if pgrep -f "cloudflared tunnel" &>/dev/null; then
            log_success "Cloudflare tunnel is already active."
        else
            log_info "Starting Cloudflare tunnel in background (sih.seucra.tech -> localhost:5003)..."
            cloudflared tunnel run >/dev/null 2>&1 &
            PID_CF=$!
            sleep 1
            log_success "Cloudflare tunnel started (PID: $PID_CF)."
        fi
    else
        log_warn "cloudflared binary not found; running on local LAN only."
    fi

    # 2. Mock Services (Bank on 8001, NCRP/I4C on 8002)
    log_info "Starting Mock Bank API (port 8001) & Mock NCRP/I4C API (port 8002)..."
    $PYTHON -m mock_services.bank_api.server &
    PID_BANK=$!
    $PYTHON -m mock_services.ncrp_i4c_api.server &
    PID_NCRP=$!

    cleanup() {
        echo ""
        log_info "Shutting down backend services..."
        kill $PID_BANK $PID_NCRP 2>/dev/null || true
        if [ -n "$PID_CF" ]; then
            kill $PID_CF 2>/dev/null || true
        fi
        log_success "All backend services stopped cleanly."
    }
    trap cleanup EXIT INT TERM

    sleep 1
    log_success "Mock services active:"
    echo "  - Mock Bank API:   http://127.0.0.1:8001"
    echo "  - Mock NCRP / I4C: http://127.0.0.1:8002"
    echo ""
    log_success "Live Cloudflare Gateway:"
    echo "  - HTTPS API:       https://sih.seucra.tech"
    echo "  - WebSocket:       wss://sih.seucra.tech/ws"
    echo ""
    log_info "Starting CyberShield FastAPI, WebSocket & Discovery server on 0.0.0.0:5003..."
    $PYTHON -m api.server 5003
}

run_demo() {
    log_info "Running Phase 2 E2E Demo..."
    $PYTHON -m scripts.demo_phase2
}

run_tests() {
    log_info "Running backend test suite..."
    $PYTHON -m pytest tests/ -v
}

run_pipeline() {
    log_info "Starting Kafka with Docker Compose..."
    docker compose up -d
    log_info "Starting pipeline consumer in background..."
    $PYTHON pipeline/consumer.py &
    PID_CONSUMER=$!
    log_info "Starting detection scorer in background..."
    $PYTHON detection/scorer.py &
    PID_SCORER=$!

    trap "kill $PID_CONSUMER $PID_SCORER 2>/dev/null || true" EXIT INT TERM

    log_info "Producing live synthetic transactions..."
    $PYTHON data-generator/producer.py
}

build_and_launch_android() {
    log_info "Building CyberShield Android App..."
    cd "$REPO_ROOT/CyberShield"
    chmod +x gradlew
    ./gradlew assembleDebug

    APK_PATH="$REPO_ROOT/CyberShield/app/build/outputs/apk/debug/app-debug.apk"
    if [ ! -f "$APK_PATH" ]; then
        log_error "APK not found at $APK_PATH"
        exit 1
    fi
    log_success "Debug APK built successfully at $APK_PATH"

    cd "$REPO_ROOT"
    if command -v adb &>/dev/null && [ "$(adb get-state 2>/dev/null)" = "device" ]; then
        log_info "Installing APK to connected device..."
        adb install -r "$APK_PATH"
        log_success "APK successfully installed."
        log_info "Launching CyberShield (MainActivity)..."
        adb shell am start -n "com.i4c.cybershield/.MainActivity"
    else
        log_info "Debug APK ready at $APK_PATH"
    fi
}

# Main routing (default to 'server')
CMD="${1:-server}"

case "$CMD" in
    server|backend)
        print_header
        run_server
        ;;
    demo)
        print_header
        run_demo
        ;;
    test)
        print_header
        run_tests
        ;;
    pipeline)
        print_header
        run_pipeline
        ;;
    app)
        print_header
        build_and_launch_android
        ;;
    all)
        print_header
        build_and_launch_android
        echo ""
        log_info "Starting complete backend stack..."
        run_server
        ;;
    help|--help|-h)
        print_help
        ;;
    *)
        log_error "Unknown command: $CMD"
        print_help
        exit 1
        ;;
esac

