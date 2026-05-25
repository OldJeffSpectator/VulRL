#!/bin/bash
################################################################################
# VulRL SFT Data Generation - One-Click Script
################################################################################
# Collects rollout trajectories for supervised fine-tuning (SFT).
#
# This script:
#   1. Install system dependencies (docker, redis, python) if missing
#   2. Setup Worker Orchestrator Python environment (venv + pip)
#   3. Validate configuration (API key, parquet dataset)
#   4. Start services (Redis, Worker Router)
#   5. For each case in the parquet × TRIALS_PER_CASE, collect rollout trajectories
#
# All trajectories are saved regardless of reward. Supports resume.
#
# Usage:
#   bash run_sft_gen_one_click.sh
#
# Edit the CONFIGURATION section below before running.
################################################################################

set -e

# ============================================================================
# CONFIGURATION  —  Edit these values directly before running
# ============================================================================

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
WORKER_ORCH_DIR="$REPO_ROOT/worker_orchestrator"
SFT_GEN_DIR="$REPO_ROOT/sft_data_gen"

# ---- LLM API ----
LLM_API_KEY="sk-REPLACE_ME"                      # <-- PUT YOUR API KEY HERE
LLM_API_BASE="https://api.openai.com"             # e.g. https://api.deepseek.com
LLM_MODEL_NAME="gpt-4o"                           # e.g. deepseek-chat

# ---- Dataset ----
TRAIN_DATA="$REPO_ROOT/dataset/cve_vulhub/train_vulhub_hard.parquet"

# ---- Generation parameters ----
TRIALS_PER_CASE=20          # Number of rollout trials per case
MAX_WORKERS=5               # Max concurrent rollouts (tune for API rate limits)
ROLLOUT_TIMEOUT=1800        # Per-rollout timeout in seconds (30 min)
TEMPERATURE=0.7             # LLM sampling temperature
MAX_TOKENS=4096             # LLM max tokens per turn
POLL_INTERVAL=15            # Seconds between status polls

# ---- Service ports ----
WORKER_ROUTER_PORT=12345
REDIS_PORT=6379
USE_DOCKER_REDIS=false      # Set to true to run Redis in Docker

# ---- Script behaviour ----
NO_SUDO=false               # Set to true to skip system package installation

# ---- Output ----
RUN_TIMESTAMP=$(date +"%Y_%m_%d_%H_%M")
OUTPUT_DIR="$SFT_GEN_DIR/results/$RUN_TIMESTAMP"
# To resume a previous run, uncomment and set the path:
# OUTPUT_DIR="$SFT_GEN_DIR/results/2026_05_25_12_00"

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()    { echo -e "${BLUE}[INFO]${NC} $1" >&2; }
log_success() { echo -e "${GREEN}[OK]${NC} $1" >&2; }
log_warning() { echo -e "${YELLOW}[WARN]${NC} $1" >&2; }
log_error()   { echo -e "${RED}[ERR]${NC} $1" >&2; }

log_section() {
    {
        echo ""
        echo "============================================================================"
        echo "$1"
        echo "============================================================================"
        echo ""
    } >&2
}

command_exists() { command -v "$1" >/dev/null 2>&1; }

port_in_use() {
    netstat -tuln 2>/dev/null | grep -q ":$1 " || ss -tuln 2>/dev/null | grep -q ":$1 "
}

detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        OS_VERSION=$VERSION_ID
    elif [ -f /etc/redhat-release ]; then
        OS="rhel"
    else
        OS="unknown"
    fi
    log_info "Detected OS: $OS ${OS_VERSION:-}"
}

# ============================================================================
# PHASE 1: CHECK / INSTALL SYSTEM DEPENDENCIES
# ============================================================================

check_required_commands() {
    local missing_deps=()

    log_info "Checking required dependencies..."

    if ! command_exists python3.12 && ! command_exists python3; then
        missing_deps+=("python3")
        log_warning "Python 3 not found"
    else
        log_success "Python 3 found"
    fi

    if ! command_exists docker; then
        missing_deps+=("docker")
        log_warning "Docker not found"
    else
        log_success "Docker found"
    fi

    if ! docker compose version >/dev/null 2>&1 && ! command_exists docker-compose; then
        missing_deps+=("docker-compose")
        log_warning "Docker Compose not found"
    else
        log_success "Docker Compose found"
    fi

    if [ "$USE_DOCKER_REDIS" = "true" ]; then
        log_info "Using Docker for Redis (system Redis not required)"
    else
        if ! command_exists redis-server; then
            missing_deps+=("redis-server")
            log_warning "Redis not found"
        else
            log_success "Redis found"
        fi
    fi

    if [ "$NO_SUDO" = "true" ] && [ ${#missing_deps[@]} -gt 0 ]; then
        log_error "NO_SUDO mode but missing deps: ${missing_deps[*]}"
        {
            echo ""
            echo "Please install the following manually:"
            echo ""
            for dep in "${missing_deps[@]}"; do
                case "$dep" in
                    python3)
                        echo "  Python 3.10+:"
                        echo "    Ubuntu/Debian: sudo apt-get install python3 python3-venv python3-dev"
                        ;;
                    docker)
                        echo "  Docker:"
                        echo "    https://docs.docker.com/engine/install/"
                        ;;
                    docker-compose)
                        echo "  Docker Compose:"
                        echo "    sudo apt-get install docker-compose-plugin"
                        ;;
                    redis-server)
                        echo "  Redis (or set USE_DOCKER_REDIS=true):"
                        echo "    sudo apt-get install redis-server"
                        ;;
                esac
            done
            echo ""
        } >&2
        exit 1
    fi

    if [ ${#missing_deps[@]} -gt 0 ]; then
        echo "${missing_deps[@]}"
    fi
}

install_system_deps() {
    log_section "Phase 1: System Dependencies"

    local missing_deps
    missing_deps=$(check_required_commands)

    if [ -z "$missing_deps" ]; then
        log_success "Phase 1 complete: All dependencies already installed"
        return 0
    fi

    detect_os

    if [ "$EUID" -eq 0 ]; then
        SUDO=""
    elif command_exists sudo; then
        SUDO="sudo"
        log_info "Will use sudo to install: $missing_deps"
    else
        log_error "Missing deps but no sudo. Install manually or run as root."
        exit 1
    fi

    log_info "Updating package lists..."
    case "$OS" in
        ubuntu|debian) $SUDO apt-get update -qq ;;
        centos|rhel|fedora) $SUDO yum update -y -q || $SUDO dnf update -y -q ;;
        *) log_warning "Unknown OS — skipping package update" ;;
    esac

    if ! command_exists python3.12 && ! command_exists python3; then
        log_info "Installing Python 3..."
        case "$OS" in
            ubuntu|debian) $SUDO apt-get install -y python3 python3-venv python3-dev ;;
            centos|rhel|fedora) $SUDO yum install -y python3 python3-devel || $SUDO dnf install -y python3 python3-devel ;;
        esac
    fi
    log_success "Python 3 ready"

    if ! command_exists docker; then
        log_info "Installing Docker..."
        case "$OS" in
            ubuntu|debian) $SUDO apt-get install -y docker.io ;;
            centos|rhel|fedora) $SUDO yum install -y docker || $SUDO dnf install -y docker ;;
        esac
        $SUDO systemctl enable docker
        $SUDO systemctl start docker
        $SUDO usermod -aG docker "$USER" || true
        log_warning "You may need to re-login for Docker group permissions."
    fi
    log_success "Docker ready"

    if ! docker compose version >/dev/null 2>&1 && ! command_exists docker-compose; then
        log_info "Installing Docker Compose..."
        case "$OS" in
            ubuntu|debian) $SUDO apt-get install -y docker-compose-plugin || $SUDO apt-get install -y docker-compose ;;
            centos|rhel|fedora) $SUDO yum install -y docker-compose || $SUDO dnf install -y docker-compose ;;
        esac
    fi
    log_success "Docker Compose ready"

    if ! command_exists redis-server && [ "$USE_DOCKER_REDIS" != "true" ]; then
        log_info "Installing Redis..."
        case "$OS" in
            ubuntu|debian) $SUDO apt-get install -y redis-server ;;
            centos|rhel|fedora) $SUDO yum install -y redis || $SUDO dnf install -y redis ;;
        esac
    fi
    log_success "Redis ready"

    log_info "Installing utilities (curl, git, build-essential)..."
    case "$OS" in
        ubuntu|debian) $SUDO apt-get install -y curl git build-essential python3-pip ;;
        centos|rhel|fedora) $SUDO yum install -y curl git gcc gcc-c++ make python3-pip || $SUDO dnf install -y curl git gcc gcc-c++ make python3-pip ;;
    esac

    log_success "Phase 1 complete: All system dependencies installed"
}

# ============================================================================
# PHASE 2: SETUP WORKER ORCHESTRATOR ENVIRONMENT
# ============================================================================

setup_worker_orchestrator() {
    log_section "Phase 2: Setting Up Worker Orchestrator"

    cd "$WORKER_ORCH_DIR"

    # Determine which python to use
    local PYTHON_BIN
    if command_exists python3.12; then
        PYTHON_BIN=python3.12
    else
        PYTHON_BIN=python3
    fi

    if [ ! -d "venv" ]; then
        log_info "Creating virtual environment with $PYTHON_BIN..."
        $PYTHON_BIN -m venv venv
        log_success "Virtual environment created"
    else
        log_success "Virtual environment already exists"
    fi

    source venv/bin/activate

    log_info "Upgrading pip..."
    pip install --upgrade pip --quiet

    log_info "Installing Worker Orchestrator dependencies..."
    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt --quiet
        log_success "Dependencies installed"
    else
        log_error "requirements.txt not found in $WORKER_ORCH_DIR"
        exit 1
    fi

    # Ensure pandas + pyarrow are available (needed by collect_rollouts.py)
    if ! python -c "import pandas" 2>/dev/null; then
        log_info "Installing pandas + pyarrow..."
        pip install pandas pyarrow --quiet
    fi

    log_info "Verifying critical packages..."
    if python -c "import fastapi, redis, docker, pandas, aiohttp" 2>/dev/null; then
        log_success "All critical packages verified"
    else
        log_error "Some packages failed to import. Check venv."
        exit 1
    fi

    cd "$REPO_ROOT"
    log_success "Phase 2 complete: Worker Orchestrator ready"
}

# ============================================================================
# PHASE 3: VALIDATE CONFIG
# ============================================================================

validate_config() {
    log_section "Phase 3: Validating Configuration"

    if [ -z "$LLM_API_KEY" ] || [ "$LLM_API_KEY" = "sk-REPLACE_ME" ]; then
        log_error "LLM_API_KEY is not set. Edit the CONFIGURATION section in this script."
        exit 1
    fi
    log_success "LLM_API_KEY is set"

    if [ ! -f "$TRAIN_DATA" ]; then
        log_error "Training data not found: $TRAIN_DATA"
        exit 1
    fi
    log_success "Training data found: $TRAIN_DATA"

    log_success "Phase 3 complete: Configuration valid"
}

# ============================================================================
# PHASE 4: START SERVICES
# ============================================================================

start_redis() {
    log_info "Starting Redis..."

    if port_in_use $REDIS_PORT; then
        log_success "Redis already running on port $REDIS_PORT"
        return 0
    fi

    if [ "$USE_DOCKER_REDIS" = "true" ]; then
        log_info "Starting Redis in Docker..."
        docker run -d --name vulrl-redis --rm -p $REDIS_PORT:6379 redis:7-alpine redis-server --appendonly yes
        sleep 3
        if port_in_use $REDIS_PORT; then
            log_success "Redis running in Docker on port $REDIS_PORT"
            return 0
        else
            log_error "Failed to start Redis in Docker"
            exit 1
        fi
    fi

    if command_exists redis-server; then
        redis-server --daemonize yes --port $REDIS_PORT --dir /tmp 2>/dev/null || true
        sleep 2
    fi

    if port_in_use $REDIS_PORT; then
        log_success "Redis running on port $REDIS_PORT"
    else
        log_error "Failed to start Redis"
        log_info "Try: USE_DOCKER_REDIS=true bash $0"
        exit 1
    fi
}

start_worker_router() {
    log_info "Starting Worker Router..."

    if port_in_use $WORKER_ROUTER_PORT; then
        log_success "Worker Router already running on port $WORKER_ROUTER_PORT"
        return 0
    fi

    cd "$WORKER_ORCH_DIR"
    source venv/bin/activate
    mkdir -p logs

    # Override max workers via env so the router respects our concurrency limit
    export WORKER_ROUTER_MAX_WORKERS="$MAX_WORKERS"

    nohup bash start_worker_router.sh > logs/worker_router.log 2>&1 &
    WORKER_ROUTER_PID=$!
    echo $WORKER_ROUTER_PID > logs/worker_router.pid

    log_info "Waiting for Worker Router to start (max 60s)..."
    for i in $(seq 1 60); do
        if port_in_use $WORKER_ROUTER_PORT; then
            log_success "Worker Router started (PID: $WORKER_ROUTER_PID)"
            break
        fi
        if [ "$i" -eq 60 ]; then
            log_error "Worker Router failed to start within 60 seconds"
            log_info "Check logs: $WORKER_ORCH_DIR/logs/worker_router.log"
            exit 1
        fi
        sleep 1
    done

    sleep 3
    if curl -s "http://localhost:$WORKER_ROUTER_PORT/health" >/dev/null 2>&1; then
        log_success "Worker Router health check passed"
    else
        log_warning "Worker Router running but health check failed — continuing"
    fi

    cd "$REPO_ROOT"
}

start_services() {
    log_section "Phase 4: Starting Services"

    start_redis
    start_worker_router

    log_success "Phase 4 complete: All services running"
}

# ============================================================================
# PHASE 5: RUN COLLECTION
# ============================================================================

run_collection() {
    log_section "Phase 5: Collecting Rollout Trajectories"

    mkdir -p "$OUTPUT_DIR"

    # Save run config for reproducibility
    cat > "$OUTPUT_DIR/run_config.json" <<CFGEOF
{
    "llm_api_base": "$LLM_API_BASE",
    "llm_model_name": "$LLM_MODEL_NAME",
    "train_data": "$TRAIN_DATA",
    "trials_per_case": $TRIALS_PER_CASE,
    "max_workers": $MAX_WORKERS,
    "rollout_timeout": $ROLLOUT_TIMEOUT,
    "temperature": $TEMPERATURE,
    "max_tokens": $MAX_TOKENS,
    "poll_interval": $POLL_INTERVAL,
    "worker_router_port": $WORKER_ROUTER_PORT,
    "started_at": "$(date -Iseconds)"
}
CFGEOF

    log_info "Configuration:"
    echo "  LLM endpoint:     $LLM_API_BASE"
    echo "  Model:            $LLM_MODEL_NAME"
    echo "  Dataset:          $TRAIN_DATA"
    echo "  Trials per case:  $TRIALS_PER_CASE"
    echo "  Max workers:      $MAX_WORKERS"
    echo "  Rollout timeout:  ${ROLLOUT_TIMEOUT}s"
    echo "  Temperature:      $TEMPERATURE"
    echo "  Max tokens:       $MAX_TOKENS"
    echo "  Output dir:       $OUTPUT_DIR"
    echo ""

    cd "$WORKER_ORCH_DIR"
    source venv/bin/activate

    export LLM_API_KEY

    python "$SFT_GEN_DIR/collect_rollouts.py" \
        --parquet "$TRAIN_DATA" \
        --output-dir "$OUTPUT_DIR" \
        --llm-endpoint "$LLM_API_BASE" \
        --model-name "$LLM_MODEL_NAME" \
        --api-key "$LLM_API_KEY" \
        --trials "$TRIALS_PER_CASE" \
        --max-concurrent "$MAX_WORKERS" \
        --router-url "http://localhost:$WORKER_ROUTER_PORT" \
        --poll-interval "$POLL_INTERVAL" \
        --rollout-timeout "$ROLLOUT_TIMEOUT" \
        --temperature "$TEMPERATURE" \
        --max-tokens "$MAX_TOKENS"

    cd "$REPO_ROOT"

    log_success "Phase 5 complete: Collection finished"
    log_info "Results saved to: $OUTPUT_DIR"
}

# ============================================================================
# CLEANUP HANDLER
# ============================================================================

cleanup() {
    echo ""
    log_warning "Received interrupt signal. Cleaning up..."

    if [ -f "$WORKER_ORCH_DIR/logs/worker_router.pid" ]; then
        WORKER_PID=$(cat "$WORKER_ORCH_DIR/logs/worker_router.pid")
        if kill -0 "$WORKER_PID" 2>/dev/null; then
            log_info "Stopping Worker Router (PID: $WORKER_PID)..."
            kill "$WORKER_PID"
            sleep 2
            if kill -0 "$WORKER_PID" 2>/dev/null; then
                log_warning "Force killing Worker Router..."
                kill -9 "$WORKER_PID"
            fi
            log_success "Worker Router stopped"
        else
            log_info "Worker Router already stopped"
        fi
    fi

    log_info "Redis is still running (shared service)."
    log_info "To stop Redis manually:"
    if [ "$USE_DOCKER_REDIS" = "true" ]; then
        echo "  docker stop vulrl-redis"
    else
        echo "  redis-cli shutdown"
    fi

    if [ -n "$OUTPUT_DIR" ] && [ -d "$OUTPUT_DIR" ]; then
        echo ""
        log_info "Partial results saved in: $OUTPUT_DIR"
        log_info "Re-run the same command to resume collection."
    fi

    echo ""
    log_success "Cleanup complete."
    exit 130
}

trap cleanup INT TERM

# ============================================================================
# MAIN
# ============================================================================

main() {
    log_section "VulRL SFT Data Generation"

    log_info "Repository: $REPO_ROOT"
    log_info "This script will:"
    echo "  1. Check/install system dependencies (docker, redis, python)"
    echo "  2. Setup Worker Orchestrator Python environment"
    echo "  3. Validate configuration (API key, parquet)"
    echo "  4. Start services (Redis, Worker Router)"
    echo "  5. Collect rollout trajectories for SFT"
    echo ""
    log_info "Configuration:"
    echo "  LLM_API_BASE=$LLM_API_BASE"
    echo "  LLM_MODEL_NAME=$LLM_MODEL_NAME"
    echo "  TRAIN_DATA=$TRAIN_DATA"
    echo "  TRIALS_PER_CASE=$TRIALS_PER_CASE"
    echo "  MAX_WORKERS=$MAX_WORKERS"
    echo "  OUTPUT_DIR=$OUTPUT_DIR"
    echo ""
    if [ "$NO_SUDO" = "true" ]; then
        log_warning "NO_SUDO mode — will not install system packages"
    fi
    echo ""

    read -p "Press Enter to continue, or Ctrl+C to abort..."
    echo ""

    install_system_deps
    setup_worker_orchestrator
    validate_config
    start_services
    run_collection

    log_section "SFT DATA GENERATION COMPLETE"
    log_success "All rollout trajectories collected."
    echo ""
    log_info "Output files:"
    echo "  Trajectories:  $OUTPUT_DIR/trajectories.jsonl"
    echo "  Error log:     $OUTPUT_DIR/errors.log"
    echo "  Run config:    $OUTPUT_DIR/run_config.json"
    echo ""
    log_info "Next steps:"
    echo "  - Filter trajectories (e.g., keep reward > 0 for positive SFT)"
    echo "  - Convert to chat format for your training framework"
    echo "  - Re-run to resume if collection was interrupted"
    echo ""
}

main "$@"
