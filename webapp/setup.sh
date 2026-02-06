#!/bin/bash

# BioAgent Web Application Setup Script
# This script helps you get BioAgent running quickly

set -e  # Exit on any error

echo "BioAgent Web Application Setup"
echo "=============================="
echo

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker is installed
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first:"
        echo "  - macOS: https://docs.docker.com/docker-for-mac/install/"
        echo "  - Windows: https://docs.docker.com/docker-for-windows/install/"
        echo "  - Linux: https://docs.docker.com/engine/install/"
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose first:"
        echo "  https://docs.docker.com/compose/install/"
        exit 1
    fi

    print_success "Docker and Docker Compose are installed"
}

# Determine docker compose command
get_compose_cmd() {
    if docker compose version &> /dev/null; then
        echo "docker compose"
    else
        echo "docker-compose"
    fi
}

COMPOSE_CMD=$(get_compose_cmd)

# Check if .env file exists
check_env() {
    if [ ! -f .env ]; then
        print_status "Creating .env file from template..."
        cp .env.example .env
        print_warning "Please edit .env file and add your Anthropic API key:"
        echo "  ANTHROPIC_API_KEY=your_key_here"
        echo
        echo "Get your API key from: https://console.anthropic.com/"
        echo
        read -p "Press Enter after you've added your API key to .env file..."
    else
        print_success ".env file already exists"
    fi

    # Check if API key is set
    if grep -q "ANTHROPIC_API_KEY=your_anthropic_api_key_here" .env 2>/dev/null; then
        print_warning "Please set your ANTHROPIC_API_KEY in .env file before starting"
        echo "Get your API key from: https://console.anthropic.com/"
        exit 1
    fi
}

# Start services
start_services() {
    print_status "Starting BioAgent services with Docker Compose..."

    # Pull latest images
    print_status "Pulling Docker images..."
    $COMPOSE_CMD pull

    # Build and start services
    print_status "Building and starting services..."
    $COMPOSE_CMD up -d --build

    # Wait for services to be ready
    print_status "Waiting for services to start..."
    sleep 10

    # Check service health
    print_status "Checking service health..."

    # Check backend health
    max_attempts=30
    attempt=1

    while [ $attempt -le $max_attempts ]; do
        if curl -s http://localhost:8000/health >/dev/null 2>&1; then
            print_success "Backend is ready!"
            break
        fi

        if [ $attempt -eq $max_attempts ]; then
            print_error "Backend failed to start after ${max_attempts} attempts"
            print_status "Checking backend logs..."
            $COMPOSE_CMD logs backend
            exit 1
        fi

        print_status "Waiting for backend... (attempt $attempt/$max_attempts)"
        sleep 2
        ((attempt++))
    done

    # Check frontend
    attempt=1
    while [ $attempt -le $max_attempts ]; do
        if curl -s http://localhost:3000 >/dev/null 2>&1; then
            print_success "Frontend is ready!"
            break
        fi

        if [ $attempt -eq $max_attempts ]; then
            print_warning "Frontend may still be building. Check logs with: $COMPOSE_CMD logs frontend"
            break
        fi

        print_status "Waiting for frontend... (attempt $attempt/$max_attempts)"
        sleep 2
        ((attempt++))
    done
}

# Display success message
show_success() {
    echo
    echo "BioAgent is now running!"
    echo "========================"
    echo
    echo "Frontend:     http://localhost:3000"
    echo "Backend API:  http://localhost:8000"
    echo "API Docs:     http://localhost:8000/docs"
    echo "MinIO Console: http://localhost:9001"
    echo "   (User: bioagent, Password: bioagent_secret_key)"
    echo
    echo "Next Steps:"
    echo "1. Open http://localhost:3000 in your browser"
    echo "2. Click 'New Chat' to start your first analysis"
    echo "3. Try: 'Help me analyze my RNA-seq data'"
    echo
    echo "Useful Commands:"
    echo "  View logs:      $COMPOSE_CMD logs -f"
    echo "  Stop services:  $COMPOSE_CMD down"
    echo "  Restart:        $COMPOSE_CMD restart"
    echo "  Full reset:     $COMPOSE_CMD down -v && $COMPOSE_CMD up -d --build"
    echo
}

# Show help
show_help() {
    echo "BioAgent Setup Script"
    echo
    echo "Usage: $0 [OPTION]"
    echo
    echo "Options:"
    echo "  start     Start BioAgent services (default)"
    echo "  stop      Stop all services"
    echo "  restart   Restart all services"
    echo "  logs      Show service logs"
    echo "  status    Show service status"
    echo "  clean     Stop services and remove volumes (data loss!)"
    echo "  help      Show this help message"
    echo
}

# Handle command line arguments
case "${1:-start}" in
    start)
        check_docker
        check_env
        start_services
        show_success
        ;;
    stop)
        print_status "Stopping BioAgent services..."
        $COMPOSE_CMD down
        print_success "Services stopped"
        ;;
    restart)
        print_status "Restarting BioAgent services..."
        $COMPOSE_CMD restart
        print_success "Services restarted"
        ;;
    logs)
        $COMPOSE_CMD logs -f
        ;;
    status)
        $COMPOSE_CMD ps
        ;;
    clean)
        print_warning "This will remove all data including the database!"
        read -p "Are you sure? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_status "Stopping services and removing volumes..."
            $COMPOSE_CMD down -v
            print_success "Cleanup complete"
        else
            print_status "Cleanup cancelled"
        fi
        ;;
    help)
        show_help
        ;;
    *)
        print_error "Unknown option: $1"
        show_help
        exit 1
        ;;
esac
