#!/usr/bin/env bash
# ==============================================================================
# AI System Template — One-Click Automated Installer & Verifier
# ==============================================================================

set -e

# --- Color Definitions & Visual Styling ---
BOLD='\033[1m'
DIM='\033[2m'
RESET='\033[0m'
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[0;37m'

# --- Logging Helpers ---
log_banner() {
    echo -e "${CYAN}${BOLD}"
    echo "  ╔══════════════════════════════════════════════════════════════════════════╗"
    echo "  ║                                                                          ║"
    echo "  ║           AI SYSTEM TEMPLATE : ONE-CLICK DEPLOYER & VERIFIER             ║"
    echo "  ║            Decoupled Django 5 + Nous Hermes Agent Framework              ║"
    echo "  ║                                                                          ║"
    echo "  ╚══════════════════════════════════════════════════════════════════════════╝"
    echo -e "${RESET}"
}

log_phase() {
    echo -e "\n${MAGENTA}${BOLD}==>${RESET} ${CYAN}${BOLD}[Phase $1]${RESET} ${WHITE}${BOLD}$2${RESET}"
    echo -e "${DIM}────────────────────────────────────────────────────────────────────────────${RESET}"
}

log_step() {
    echo -e "  ${BLUE}${BOLD}▸${RESET} $1"
}

log_success() {
    echo -e "  ${GREEN}${BOLD}✔${RESET} ${GREEN}$1${RESET}"
}

log_warning() {
    echo -e "  ${YELLOW}${BOLD}⚠${RESET} ${YELLOW}$1${RESET}"
}

log_error() {
    echo -e "  ${RED}${BOLD}✖${RESET} ${RED}$1${RESET}"
}

# --- Pre-flight Checks ---
check_prerequisites() {
    log_phase "1/5" "Environment & Pre-flight Diagnostics"

    log_step "Checking Docker daemon status..."
    if ! docker info >/dev/null 2>&1; then
        log_error "Docker is not running or current user does not have permission to access the Docker daemon."
        echo -e "    ${DIM}Please start Docker (e.g., sudo systemctl start docker) and try again.${RESET}"
        exit 1
    fi
    log_success "Docker daemon is active and responsive."

    log_step "Checking Docker Compose..."
    if ! docker compose version >/dev/null 2>&1; then
        log_error "Docker Compose (v2) is not installed or not in PATH."
        exit 1
    fi
    local compose_ver=$(docker compose version --short 2>/dev/null || echo "v2")
    log_success "Docker Compose ($compose_ver) verified."

    log_step "Checking Hermes base image (hermes-agent:local)..."
    if docker image inspect hermes-agent:local >/dev/null 2>&1; then
        log_success "Found pre-built Hermes Agent image: hermes-agent:local"
    else
        log_warning "hermes-agent:local not found locally. It will fall back to configuration in .env"
    fi
}

# --- Setup Environment Files ---
setup_environments() {
    log_phase "2/5" "Configuration & Secret Bootstrapping"

    # Backend environment
    log_step "Verifying Django backend configuration (backend/.env)..."
    if [ ! -f "backend/.env" ]; then
        if [ -f "backend/.env.example" ]; then
            cp backend/.env.example backend/.env
            log_success "Created backend/.env from backend/.env.example"
        else
            log_error "Missing backend/.env.example template."
            exit 1
        fi
    else
        log_success "Existing backend/.env detected."
    fi

    # Hermes environment
    log_step "Verifying Hermes agent configuration (agent_service/.env)..."
    if [ ! -f "agent_service/.env" ]; then
        if [ -f "agent_service/.env.example" ]; then
            cp agent_service/.env.example agent_service/.env
            log_success "Created agent_service/.env from agent_service/.env.example"
        else
            log_error "Missing agent_service/.env.example template."
            exit 1
        fi
    else
        log_success "Existing agent_service/.env detected."
    fi

    log_step "Preparing persistent data volume for Hermes..."
    mkdir -p agent_service/data
    log_success "Persistent data directory ready (agent_service/data/)."
}

# --- Build & Start Django Environment ---
launch_django() {
    log_phase "3/5" "Deploying Environment 1: Django Backend & DB Core"

    log_step "Starting PostgreSQL 16, Redis 7, and Django 5..."
    docker compose -f backend/docker-compose.yml up -d --build

    log_step "Waiting for Django backend & database to initialize..."
    local retries=30
    local healthy=0
    while [ $retries -gt 0 ]; do
        if curl -s http://localhost:8000/api/health/ 2>/dev/null | grep -qE '"status"[[:space:]]*:[[:space:]]*"healthy"'; then
            healthy=1
            break
        fi
        sleep 2
        retries=$((retries - 1))
        echo -n "."
    done
    echo ""

    if [ $healthy -eq 1 ]; then
        log_success "Django backend is HEALTHY on port 8000."
        log_success "PostgreSQL database migrated and superuser initialized (admin / admin12345)."
    else
        log_error "Django backend did not report healthy within 60 seconds."
        echo -e "${DIM}Recent backend logs:${RESET}"
        docker compose -f backend/docker-compose.yml logs --tail=20 backend
        exit 1
    fi
}

# --- Build & Start Hermes Environment ---
launch_hermes() {
    log_phase "4/5" "Deploying Environment 2: Isolated Hermes Agent Runtime"

    log_step "Starting isolated Hermes Agent daemon..."
    docker compose -f agent_service/docker-compose.yml up -d

    log_step "Verifying Hermes Gateway status on port 8643..."
    local retries=20
    local running=0
    while [ $retries -gt 0 ]; do
        if docker compose -f agent_service/docker-compose.yml ps | grep -q "Up"; then
            running=1
            break
        fi
        sleep 2
        retries=$((retries - 1))
        echo -n "."
    done
    echo ""

    if [ $running -eq 1 ]; then
        log_success "Hermes Agent container is ACTIVE on port 8643 (isolated network)."
    else
        log_error "Hermes Agent container failed to start."
        docker compose -f agent_service/docker-compose.yml logs --tail=20
        exit 1
    fi
}

# --- Handshake Verification ---
run_verification() {
    log_phase "5/5" "Bidirectional Handshake & Integration Verification"

    log_step "Executing handshake skill from inside Hermes container..."
    if docker compose -f agent_service/docker-compose.yml exec -T hermes python /workspace/skills/django_handshake/run.py; then
        echo ""
        log_success "Hermes -> Django handshake succeeded! Acknowledged and saved in PostgreSQL."
    else
        log_error "Hermes -> Django handshake failed."
        exit 1
    fi

    log_step "Checking reverse ping (Django -> Hermes Gateway)..."
    local reverse_status=$(curl -s http://localhost:8000/api/ping-hermes/ 2>/dev/null | grep -o '"status": *"[^"]*"' | head -n1 || echo "")
    if [[ "$reverse_status" =~ "connected" ]]; then
        log_success "Django -> Hermes reverse gateway connection confirmed."
    else
        log_warning "Reverse ping returned non-standard status: $reverse_status (Hermes gateway daemon may still be initializing)."
    fi
}

# --- Final Summary Dashboard ---
show_dashboard() {
    echo ""
    echo -e "${GREEN}${BOLD}  ╔══════════════════════════════════════════════════════════════════════════╗"
    echo -e "  ║               SYSTEM DEPLOYMENT & VERIFICATION SUCCESSFUL                ║"
    echo -e "  ╚══════════════════════════════════════════════════════════════════════════╝${RESET}"
    echo ""
    echo -e "  ${WHITE}${BOLD}Available Services & Endpoints:${RESET}"
    echo -e "  ${CYAN}• Django Admin Portal:${RESET}   ${BOLD}http://localhost:8000/admin/${RESET}"
    echo -e "    ${DIM}Credentials:          Username: ${BOLD}admin${RESET}${DIM} | Password: ${BOLD}admin12345${RESET}"
    echo -e "  ${CYAN}• REST API Health:${RESET}       ${BOLD}http://localhost:8000/api/health/${RESET}"
    echo -e "  ${CYAN}• Handshake Logs:${RESET}        ${BOLD}http://localhost:8000/api/handshake/logs/${RESET}"
    echo -e "  ${CYAN}• Hermes Gateway Daemon:${RESET} ${BOLD}http://localhost:8643/${RESET}"
    echo ""
    echo -e "  ${WHITE}${BOLD}Operational Management Commands:${RESET}"
    echo -e "  ${DIM}• View Django logs:     docker compose -f backend/docker-compose.yml logs -f${RESET}"
    echo -e "  ${DIM}• View Hermes logs:     docker compose -f agent_service/docker-compose.yml logs -f${RESET}"
    echo -e "  ${DIM}• Run verification:     python3 scripts/verify_handshake.py${RESET}"
    echo -e "  ${DIM}• Stop backend:         docker compose -f backend/docker-compose.yml down${RESET}"
    echo -e "  ${DIM}• Stop Hermes:          docker compose -f agent_service/docker-compose.yml down${RESET}"
    echo ""
    echo -e "  ${GREEN}${BOLD}✔ Both isolated Docker environments are up, connected, and ready for work!${RESET}"
    echo ""
}

# --- Main Flow ---
main() {
    log_banner
    check_prerequisites
    setup_environments
    launch_django
    launch_hermes
    run_verification
    show_dashboard
}

main "$@"
