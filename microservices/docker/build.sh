#!/bin/bash
# ============================================================================
# Enterprise Microservices Docker Build Script
# ============================================================================
# Optimized build script for production-ready microservices containers

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REGISTRY="${DOCKER_REGISTRY:-}"
TAG="${DOCKER_TAG:-latest}"
PUSH="${DOCKER_PUSH:-false}"
PARALLEL="${DOCKER_PARALLEL:-true}"
CACHE_FROM="${DOCKER_CACHE_FROM:-}"

# Services to build
SERVICES=(
    "api-gateway"
    "orchestration"
    "rag-agent"
    "search-agent"
    "jira-agent"
    "llm-agent"
)

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Build a single service
build_service() {
    local service=$1
    local context="../$service"
    local dockerfile="$context/Dockerfile"
    local image_name="${REGISTRY:+$REGISTRY/}enterprise-agentic-ai-$service:$TAG"
    
    log_info "Building $service..."
    
    # Check if Dockerfile exists
    if [[ ! -f "$dockerfile" ]]; then
        log_error "Dockerfile not found for $service: $dockerfile"
        return 1
    fi
    
    # Build arguments
    local build_args=(
        "build"
        "--target" "runtime"
        "--tag" "$image_name"
        "--file" "$dockerfile"
    )
    
    # Add cache from if specified
    if [[ -n "$CACHE_FROM" ]]; then
        build_args+=("--cache-from" "$CACHE_FROM")
    fi
    
    # Add build context
    build_args+=("$context")
    
    # Build the image
    if docker "${build_args[@]}"; then
        log_success "Built $service successfully: $image_name"
        
        # Push if requested
        if [[ "$PUSH" == "true" ]]; then
            log_info "Pushing $service..."
            if docker push "$image_name"; then
                log_success "Pushed $service successfully"
            else
                log_error "Failed to push $service"
                return 1
            fi
        fi
        
        return 0
    else
        log_error "Failed to build $service"
        return 1
    fi
}

# Build all services
build_all() {
    local failed_services=()
    
    log_info "Starting build process..."
    log_info "Registry: ${REGISTRY:-'local'}"
    log_info "Tag: $TAG"
    log_info "Push: $PUSH"
    log_info "Parallel: $PARALLEL"
    
    if [[ "$PARALLEL" == "true" ]]; then
        log_info "Building services in parallel..."
        
        # Build services in parallel
        local pids=()
        for service in "${SERVICES[@]}"; do
            build_service "$service" &
            pids+=($!)
        done
        
        # Wait for all builds to complete
        for i in "${!pids[@]}"; do
            if ! wait "${pids[$i]}"; then
                failed_services+=("${SERVICES[$i]}")
            fi
        done
    else
        log_info "Building services sequentially..."
        
        # Build services sequentially
        for service in "${SERVICES[@]}"; do
            if ! build_service "$service"; then
                failed_services+=("$service")
            fi
        done
    fi
    
    # Report results
    if [[ ${#failed_services[@]} -eq 0 ]]; then
        log_success "All services built successfully!"
        return 0
    else
        log_error "Failed to build services: ${failed_services[*]}"
        return 1
    fi
}

# Clean up old images
cleanup() {
    log_info "Cleaning up old images..."
    
    # Remove dangling images
    docker image prune -f
    
    # Remove old versions of our images
    for service in "${SERVICES[@]}"; do
        local image_pattern="${REGISTRY:+$REGISTRY/}enterprise-agentic-ai-$service"
        docker images "$image_pattern" --format "table {{.Repository}}:{{.Tag}}\t{{.CreatedAt}}" | \
        tail -n +2 | \
        sort -k2 -r | \
        tail -n +4 | \
        awk '{print $1}' | \
        xargs -r docker rmi -f
    done
    
    log_success "Cleanup completed"
}

# Show usage
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Build enterprise microservices Docker images with production optimizations.

OPTIONS:
    -r, --registry REGISTRY    Docker registry URL (default: local)
    -t, --tag TAG             Image tag (default: latest)
    -p, --push                Push images to registry after building
    -s, --sequential          Build services sequentially (default: parallel)
    -c, --cache-from IMAGE    Use image as cache source
    --cleanup                 Clean up old images after building
    -h, --help                Show this help message

ENVIRONMENT VARIABLES:
    DOCKER_REGISTRY           Docker registry URL
    DOCKER_TAG                Image tag
    DOCKER_PUSH               Set to 'true' to push images
    DOCKER_PARALLEL           Set to 'false' to build sequentially
    DOCKER_CACHE_FROM         Cache source image

EXAMPLES:
    $0                                    # Build all services locally
    $0 -r myregistry.com -t v1.0.0 -p    # Build and push to registry
    $0 -s --cleanup                       # Build sequentially and cleanup
    $0 -c myregistry.com/cache:latest     # Build with cache

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -r|--registry)
            REGISTRY="$2"
            shift 2
            ;;
        -t|--tag)
            TAG="$2"
            shift 2
            ;;
        -p|--push)
            PUSH="true"
            shift
            ;;
        -s|--sequential)
            PARALLEL="false"
            shift
            ;;
        -c|--cache-from)
            CACHE_FROM="$2"
            shift 2
            ;;
        --cleanup)
            CLEANUP="true"
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Main execution
main() {
    log_info "Enterprise Agentic AI - Docker Build Script"
    log_info "============================================="
    
    # Check if Docker is running
    if ! docker info >/dev/null 2>&1; then
        log_error "Docker is not running or not accessible"
        exit 1
    fi
    
    # Build all services
    if build_all; then
        log_success "Build process completed successfully!"
        
        # Cleanup if requested
        if [[ "${CLEANUP:-false}" == "true" ]]; then
            cleanup
        fi
        
        exit 0
    else
        log_error "Build process failed!"
        exit 1
    fi
}

# Run main function
main "$@"
