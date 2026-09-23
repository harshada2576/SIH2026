#!/usr/bin/env bash
# ==============================================================================
# CyberShield — Predictive Cash Egress Interception Platform (SIH26184)
# Unified Launcher Script for Android App & Backend Services
# ==============================================================================

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
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

# Detect Android SDK
export ANDROID_HOME="${ANDROID_HOME:-/home/seucra/Android/Sdk}"
export ANDROID_SDK_ROOT="${ANDROID_SDK_ROOT:-$ANDROID_HOME}"
if [ -d "$ANDROID_HOME/platform-tools" ]; then
    export PATH="$PATH:$ANDROID_HOME/platform-tools"
fi

print_header() {
    echo -e "${BOLD}${CYAN}"
    echo "=================================================================="
    echo "  🛡️  CyberShield: Predictive Cash Egress Interception (SIH26184)"
    echo "  Sole Frontend: Native Android Kotlin (Jetpack Compose)"
    echo "=================================================================="
    echo -e "${NC}"
}

print_help() {
    print_header
    echo "Usage: ./run.sh [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  app             Build, install, and launch the CyberShield Android App on connected USB phone (Default)"
    echo "  backend         Start mock Bank & NCRP/I4C APIs and run Phase 2 E2E Demo"
    echo "  demo            Run full Phase 2 E2E demo scenario in terminal"
    echo "  pipeline        Start local Kafka (Docker), pipeline consumer, and detection scorer"
    echo "  test            Run all pytest verification and integration tests"
    echo "  all             Build & launch Android app + run background mock services and demo"
    echo "  help            Show this help menu"
    echo ""
}

check_device() {
    log_info "Checking for connected Android device via ADB..."
    if ! command -v adb &>/dev/null; then
        log_error "adb command not found. Please ensure Android platform-tools is installed."
        return 1
    fi

    DEVICE_STATE=$(adb get-state 2>/dev/null || echo "offline")
    if [ "$DEVICE_STATE" != "device" ]; then
        log_warn "Device status: $DEVICE_STATE"
        log_info "Listing attached devices:"
        adb devices
        echo ""
        log_warn "If 'unauthorized', please unlock your phone and tap 'Allow USB debugging'."
        log_warn "Waiting up to 10s for device authorization..."
        for i in {1..10}; do
            if [ "$(adb get-state 2>/dev/null)" = "device" ]; then
                DEVICE_STATE="device"
                break
            fi
            sleep 1
        done
    fi

    if [ "$DEVICE_STATE" = "device" ]; then
        DEVICE_MODEL=$(adb shell getprop ro.product.model 2>/dev/null || echo "Android Device")
        log_success "Connected device detected: ${BOLD}$DEVICE_MODEL${NC}"
        return 0
    else
        log_error "No authorized Android device connected. Connect your phone via USB with USB Debugging enabled."
        return 1
    fi
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
    if check_device; then
        log_info "Installing APK to connected device..."
        adb install -r "$APK_PATH"
        log_success "APK successfully installed."

        log_info "Launching CyberShield (MainActivity)..."
        adb shell am start -n "com.i4c.cybershield/.MainActivity"
        log_success "🚀 CyberShield is now running on your mobile device!"
    else
        log_warn "APK build succeeded, but could not install to device because no authorized device was found."
    fi
}

run_mock_services() {
    log_info "Starting Mock Bank API (port 8001) and Mock NCRP/I4C API (port 8002)..."
    $PYTHON -m mock_services.bank_api.server &
    PID_BANK=$!
    $PYTHON -m mock_services.ncrp_i4c_api.server &
    PID_NCRP=$!

    # Trap to kill background services on exit
    trap "kill $PID_BANK $PID_NCRP 2>/dev/null || true" EXIT

    sleep 1
    log_success "Mock services active (Bank API: 8001, NCRP/I4C: 8002)"
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

    trap "kill $PID_CONSUMER $PID_SCORER 2>/dev/null || true" EXIT

    log_info "Producing live synthetic transactions..."
    $PYTHON data-generator/producer.py
}

# Main routing
CMD="${1:-app}"

case "$CMD" in
    app)
        print_header
        build_and_launch_android
        ;;
    backend)
        print_header
        run_mock_services
        run_demo
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
    all)
        print_header
        build_and_launch_android
        echo ""
        log_info "Starting backend mock services & running Phase 2 demo..."
        run_mock_services
        run_demo
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
