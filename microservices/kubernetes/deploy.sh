#!/bin/bash
# ============================================================================
# Enterprise Microservices Kubernetes Deployment Script
# ============================================================================
# Production-ready deployment script for enterprise agentic AI microservices

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="enterprise-agentic-ai"
CONTEXT="${KUBE_CONTEXT:-}"
DRY_RUN="${DRY_RUN:-false}"
WAIT_TIMEOUT="${WAIT_TIMEOUT:-300}"

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

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if kubectl is installed
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not installed or not in PATH"
        exit 1
    fi
    
    # Check if kubectl can connect to cluster
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot connect to Kubernetes cluster"
        exit 1
    fi
    
    # Set context if provided
    if [[ -n "$CONTEXT" ]]; then
        kubectl config use-context "$CONTEXT"
        log_info "Using Kubernetes context: $CONTEXT"
    fi
    
    log_success "Prerequisites check passed"
}

# Deploy namespace and RBAC
deploy_namespace() {
    log_info "Deploying namespace and RBAC..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        kubectl apply --dry-run=client -f namespace.yaml
    else
        kubectl apply -f namespace.yaml
        kubectl wait --for=condition=Ready --timeout=60s namespace/$NAMESPACE || true
    fi
    
    log_success "Namespace and RBAC deployed"
}

# Deploy ConfigMaps and Secrets
deploy_config() {
    log_info "Deploying ConfigMaps and Secrets..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        kubectl apply --dry-run=client -f configmap.yaml
        kubectl apply --dry-run=client -f secrets.yaml
    else
        kubectl apply -f configmap.yaml
        kubectl apply -f secrets.yaml
    fi
    
    log_success "ConfigMaps and Secrets deployed"
}

# Deploy infrastructure services
deploy_infrastructure() {
    log_info "Deploying infrastructure services..."
    
    # Deploy PostgreSQL
    log_info "Deploying PostgreSQL..."
    if [[ "$DRY_RUN" == "true" ]]; then
        kubectl apply --dry-run=client -f infrastructure/postgres.yaml
    else
        kubectl apply -f infrastructure/postgres.yaml
        kubectl wait --for=condition=Ready --timeout=$WAIT_TIMEOUT pod -l app.kubernetes.io/name=postgres -n $NAMESPACE
    fi
    
    # Deploy Redis
    log_info "Deploying Redis..."
    if [[ "$DRY_RUN" == "true" ]]; then
        kubectl apply --dry-run=client -f infrastructure/redis.yaml
    else
        kubectl apply -f infrastructure/redis.yaml
        kubectl wait --for=condition=Ready --timeout=$WAIT_TIMEOUT pod -l app.kubernetes.io/name=redis -n $NAMESPACE
    fi
    
    # Deploy Consul
    log_info "Deploying Consul..."
    if [[ "$DRY_RUN" == "true" ]]; then
        kubectl apply --dry-run=client -f infrastructure/consul.yaml
    else
        kubectl apply -f infrastructure/consul.yaml
        kubectl wait --for=condition=Ready --timeout=$WAIT_TIMEOUT pod -l app.kubernetes.io/name=consul -n $NAMESPACE
    fi
    
    # Deploy RabbitMQ
    log_info "Deploying RabbitMQ..."
    if [[ "$DRY_RUN" == "true" ]]; then
        kubectl apply --dry-run=client -f infrastructure/rabbitmq.yaml
    else
        kubectl apply -f infrastructure/rabbitmq.yaml
        kubectl wait --for=condition=Ready --timeout=$WAIT_TIMEOUT pod -l app.kubernetes.io/name=rabbitmq -n $NAMESPACE
    fi
    
    # Deploy Milvus
    log_info "Deploying Milvus..."
    if [[ "$DRY_RUN" == "true" ]]; then
        kubectl apply --dry-run=client -f infrastructure/milvus.yaml
    else
        kubectl apply -f infrastructure/milvus.yaml
        kubectl wait --for=condition=Ready --timeout=$WAIT_TIMEOUT pod -l app.kubernetes.io/name=milvus -n $NAMESPACE
    fi
    
    log_success "Infrastructure services deployed"
}

# Deploy microservices
deploy_microservices() {
    log_info "Deploying microservices..."
    
    # Deploy services first
    log_info "Deploying services..."
    if [[ "$DRY_RUN" == "true" ]]; then
        kubectl apply --dry-run=client -f services.yaml
    else
        kubectl apply -f services.yaml
    fi
    
    # Deploy deployments
    log_info "Deploying deployments..."
    if [[ "$DRY_RUN" == "true" ]]; then
        kubectl apply --dry-run=client -f deployments.yaml
    else
        kubectl apply -f deployments.yaml
        
        # Wait for deployments to be ready
        log_info "Waiting for deployments to be ready..."
        kubectl wait --for=condition=Available --timeout=$WAIT_TIMEOUT deployment/api-gateway -n $NAMESPACE
        kubectl wait --for=condition=Available --timeout=$WAIT_TIMEOUT deployment/orchestration -n $NAMESPACE
        kubectl wait --for=condition=Available --timeout=$WAIT_TIMEOUT deployment/rag-agent -n $NAMESPACE
        kubectl wait --for=condition=Available --timeout=$WAIT_TIMEOUT deployment/search-agent -n $NAMESPACE
        kubectl wait --for=condition=Available --timeout=$WAIT_TIMEOUT deployment/jira-agent -n $NAMESPACE
        kubectl wait --for=condition=Available --timeout=$WAIT_TIMEOUT deployment/llm-agent -n $NAMESPACE
    fi
    
    log_success "Microservices deployed"
}

# Deploy monitoring
deploy_monitoring() {
    log_info "Deploying monitoring stack..."
    
    # Deploy Prometheus
    log_info "Deploying Prometheus..."
    if [[ "$DRY_RUN" == "true" ]]; then
        kubectl apply --dry-run=client -f monitoring/prometheus.yaml
    else
        kubectl apply -f monitoring/prometheus.yaml
        kubectl wait --for=condition=Ready --timeout=$WAIT_TIMEOUT pod -l app.kubernetes.io/name=prometheus -n $NAMESPACE
    fi
    
    # Deploy Grafana
    log_info "Deploying Grafana..."
    if [[ "$DRY_RUN" == "true" ]]; then
        kubectl apply --dry-run=client -f monitoring/grafana.yaml
    else
        kubectl apply -f monitoring/grafana.yaml
        kubectl wait --for=condition=Ready --timeout=$WAIT_TIMEOUT pod -l app.kubernetes.io/name=grafana -n $NAMESPACE
    fi
    
    # Deploy Jaeger
    log_info "Deploying Jaeger..."
    if [[ "$DRY_RUN" == "true" ]]; then
        kubectl apply --dry-run=client -f monitoring/jaeger.yaml
    else
        kubectl apply -f monitoring/jaeger.yaml
        kubectl wait --for=condition=Ready --timeout=$WAIT_TIMEOUT pod -l app.kubernetes.io/name=jaeger -n $NAMESPACE
    fi
    
    log_success "Monitoring stack deployed"
}

# Deploy autoscaling
deploy_autoscaling() {
    log_info "Deploying autoscaling configurations..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        kubectl apply --dry-run=client -f hpa.yaml
    else
        kubectl apply -f hpa.yaml
    fi
    
    log_success "Autoscaling configurations deployed"
}

# Deploy ingress
deploy_ingress() {
    log_info "Deploying ingress..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        kubectl apply --dry-run=client -f ingress.yaml
    else
        kubectl apply -f ingress.yaml
    fi
    
    log_success "Ingress deployed"
}

# Verify deployment
verify_deployment() {
    log_info "Verifying deployment..."
    
    # Check namespace
    if kubectl get namespace $NAMESPACE &> /dev/null; then
        log_success "Namespace exists"
    else
        log_error "Namespace does not exist"
        return 1
    fi
    
    # Check pods
    log_info "Checking pod status..."
    kubectl get pods -n $NAMESPACE
    
    # Check services
    log_info "Checking services..."
    kubectl get services -n $NAMESPACE
    
    # Check ingress
    log_info "Checking ingress..."
    kubectl get ingress -n $NAMESPACE
    
    # Check HPA
    log_info "Checking HPA..."
    kubectl get hpa -n $NAMESPACE
    
    log_success "Deployment verification completed"
}

# Show status
show_status() {
    log_info "Deployment Status:"
    echo "=================="
    
    echo -e "\n${BLUE}Namespaces:${NC}"
    kubectl get namespaces | grep $NAMESPACE || echo "Namespace not found"
    
    echo -e "\n${BLUE}Pods:${NC}"
    kubectl get pods -n $NAMESPACE
    
    echo -e "\n${BLUE}Services:${NC}"
    kubectl get services -n $NAMESPACE
    
    echo -e "\n${BLUE}Ingress:${NC}"
    kubectl get ingress -n $NAMESPACE
    
    echo -e "\n${BLUE}HPA:${NC}"
    kubectl get hpa -n $NAMESPACE
    
    echo -e "\n${BLUE}Deployments:${NC}"
    kubectl get deployments -n $NAMESPACE
}

# Cleanup deployment
cleanup() {
    log_warning "Cleaning up deployment..."
    
    read -p "Are you sure you want to delete the entire deployment? (yes/no): " confirm
    if [[ "$confirm" == "yes" ]]; then
        kubectl delete namespace $NAMESPACE --ignore-not-found=true
        log_success "Deployment cleaned up"
    else
        log_info "Cleanup cancelled"
    fi
}

# Show usage
usage() {
    cat << EOF
Usage: $0 [OPTIONS] [COMMAND]

Deploy enterprise agentic AI microservices to Kubernetes.

COMMANDS:
    deploy          Deploy all components (default)
    namespace       Deploy namespace and RBAC only
    config          Deploy ConfigMaps and Secrets only
    infrastructure  Deploy infrastructure services only
    microservices   Deploy microservices only
    monitoring      Deploy monitoring stack only
    autoscaling     Deploy autoscaling configurations only
    ingress         Deploy ingress only
    verify          Verify deployment
    status          Show deployment status
    cleanup         Clean up deployment

OPTIONS:
    -c, --context CONTEXT    Kubernetes context to use
    -n, --namespace NAMESPACE Namespace to deploy to (default: enterprise-agentic-ai)
    -d, --dry-run           Show what would be deployed without applying
    -t, --timeout SECONDS   Timeout for waiting operations (default: 300)
    -h, --help              Show this help message

ENVIRONMENT VARIABLES:
    KUBE_CONTEXT            Kubernetes context to use
    DRY_RUN                 Set to 'true' for dry run mode
    WAIT_TIMEOUT            Timeout for waiting operations

EXAMPLES:
    $0                                    # Deploy all components
    $0 deploy                             # Deploy all components
    $0 -d deploy                          # Dry run deployment
    $0 -c my-cluster deploy               # Deploy to specific cluster
    $0 microservices                      # Deploy microservices only
    $0 status                             # Show deployment status
    $0 cleanup                            # Clean up deployment

EOF
}

# Parse command line arguments
COMMAND="deploy"
while [[ $# -gt 0 ]]; do
    case $1 in
        -c|--context)
            CONTEXT="$2"
            shift 2
            ;;
        -n|--namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        -d|--dry-run)
            DRY_RUN="true"
            shift
            ;;
        -t|--timeout)
            WAIT_TIMEOUT="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        deploy|namespace|config|infrastructure|microservices|monitoring|autoscaling|ingress|verify|status|cleanup)
            COMMAND="$1"
            shift
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
    log_info "Enterprise Agentic AI - Kubernetes Deployment Script"
    log_info "====================================================="
    log_info "Command: $COMMAND"
    log_info "Namespace: $NAMESPACE"
    log_info "Context: ${CONTEXT:-'current'}"
    log_info "Dry Run: $DRY_RUN"
    log_info "Timeout: $WAIT_TIMEOUT"
    
    case $COMMAND in
        deploy)
            check_prerequisites
            deploy_namespace
            deploy_config
            deploy_infrastructure
            deploy_microservices
            deploy_monitoring
            deploy_autoscaling
            deploy_ingress
            verify_deployment
            show_status
            ;;
        namespace)
            check_prerequisites
            deploy_namespace
            ;;
        config)
            check_prerequisites
            deploy_config
            ;;
        infrastructure)
            check_prerequisites
            deploy_infrastructure
            ;;
        microservices)
            check_prerequisites
            deploy_microservices
            ;;
        monitoring)
            check_prerequisites
            deploy_monitoring
            ;;
        autoscaling)
            check_prerequisites
            deploy_autoscaling
            ;;
        ingress)
            check_prerequisites
            deploy_ingress
            ;;
        verify)
            check_prerequisites
            verify_deployment
            ;;
        status)
            check_prerequisites
            show_status
            ;;
        cleanup)
            check_prerequisites
            cleanup
            ;;
        *)
            log_error "Unknown command: $COMMAND"
            usage
            exit 1
            ;;
    esac
    
    log_success "Operation completed successfully!"
}

# Run main function
main "$@"
