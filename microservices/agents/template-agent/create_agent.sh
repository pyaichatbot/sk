#!/bin/bash

# ============================================================================
# microservices/agents/template-agent/create_agent.sh
# ============================================================================
# Script to create a new agent from the template

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
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

# Check if agent name is provided
if [ $# -eq 0 ]; then
    print_error "Usage: $0 <agent-name> [port]"
    print_info "Example: $0 my-agent 8007"
    exit 1
fi

AGENT_NAME=$1
AGENT_PORT=${2:-8006}
TEMPLATE_DIR="$(dirname "$0")"
AGENTS_DIR="$(dirname "$TEMPLATE_DIR")"
NEW_AGENT_DIR="$AGENTS_DIR/$AGENT_NAME"

# Validate agent name
if [[ ! "$AGENT_NAME" =~ ^[a-z0-9-]+$ ]]; then
    print_error "Agent name must contain only lowercase letters, numbers, and hyphens"
    exit 1
fi

# Check if agent already exists
if [ -d "$NEW_AGENT_DIR" ]; then
    print_error "Agent '$AGENT_NAME' already exists at $NEW_AGENT_DIR"
    exit 1
fi

print_info "Creating new agent: $AGENT_NAME"
print_info "Port: $AGENT_PORT"
print_info "Template directory: $TEMPLATE_DIR"
print_info "New agent directory: $NEW_AGENT_DIR"

# Create new agent directory
print_info "Creating directory structure..."
mkdir -p "$NEW_AGENT_DIR"

# Copy template files
print_info "Copying template files..."
cp "$TEMPLATE_DIR/main.py" "$NEW_AGENT_DIR/"
cp "$TEMPLATE_DIR/requirements.txt" "$NEW_AGENT_DIR/"
cp "$TEMPLATE_DIR/Dockerfile" "$NEW_AGENT_DIR/"
cp "$TEMPLATE_DIR/README.md" "$NEW_AGENT_DIR/"

# Rename agent file
print_info "Renaming agent file..."
mv "$NEW_AGENT_DIR/template_agent.py" "$NEW_AGENT_DIR/${AGENT_NAME}_agent.py"

# Update main.py
print_info "Updating main.py..."
sed -i.bak "s/template_agent/${AGENT_NAME}_agent/g" "$NEW_AGENT_DIR/main.py"
sed -i.bak "s/TemplateAgent/${AGENT_NAME^}Agent/g" "$NEW_AGENT_DIR/main.py"
sed -i.bak "s/template-agent/$AGENT_NAME/g" "$NEW_AGENT_DIR/main.py"
sed -i.bak "s/Template Agent/${AGENT_NAME^} Agent/g" "$NEW_AGENT_DIR/main.py"
sed -i.bak "s/8006/$AGENT_PORT/g" "$NEW_AGENT_DIR/main.py"
rm "$NEW_AGENT_DIR/main.py.bak"

# Update agent file
print_info "Updating agent file..."
sed -i.bak "s/TemplateAgent/${AGENT_NAME^}Agent/g" "$NEW_AGENT_DIR/${AGENT_NAME}_agent.py"
sed -i.bak "s/template-agent/$AGENT_NAME/g" "$NEW_AGENT_DIR/${AGENT_NAME}_agent.py"
sed -i.bak "s/Template Agent/${AGENT_NAME^} Agent/g" "$NEW_AGENT_DIR/${AGENT_NAME}_agent.py"
sed -i.bak "s/template-agent-001/$AGENT_NAME-001/g" "$NEW_AGENT_DIR/${AGENT_NAME}_agent.py"
rm "$NEW_AGENT_DIR/${AGENT_NAME}_agent.py.bak"

# Update Dockerfile
print_info "Updating Dockerfile..."
sed -i.bak "s/template-agent/$AGENT_NAME/g" "$NEW_AGENT_DIR/Dockerfile"
sed -i.bak "s/8006/$AGENT_PORT/g" "$NEW_AGENT_DIR/Dockerfile"
rm "$NEW_AGENT_DIR/Dockerfile.bak"

# Update README
print_info "Updating README..."
sed -i.bak "s/template-agent/$AGENT_NAME/g" "$NEW_AGENT_DIR/README.md"
sed -i.bak "s/Template Agent/${AGENT_NAME^} Agent/g" "$NEW_AGENT_DIR/README.md"
sed -i.bak "s/8006/$AGENT_PORT/g" "$NEW_AGENT_DIR/README.md"
rm "$NEW_AGENT_DIR/README.md.bak"

# Create .gitignore
print_info "Creating .gitignore..."
cat > "$NEW_AGENT_DIR/.gitignore" << EOF
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
env/
ENV/

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Logs
*.log
logs/

# Environment
.env
.env.local
.env.*.local
EOF

print_success "Agent '$AGENT_NAME' created successfully!"
print_info "Next steps:"
print_info "1. cd $NEW_AGENT_DIR"
print_info "2. Customize the agent logic in ${AGENT_NAME}_agent.py"
print_info "3. Update requirements.txt with your dependencies"
print_info "4. Test the agent: docker build -f Dockerfile -t $AGENT_NAME:latest ."
print_info "5. Run the agent: docker run --rm -p $AGENT_PORT:$AGENT_PORT $AGENT_NAME:latest"
print_info "6. Test health: curl http://localhost:$AGENT_PORT/health"

print_warning "Don't forget to:"
print_warning "- Update the agent capabilities and logic"
print_warning "- Add your specific dependencies to requirements.txt"
print_warning "- Customize the endpoints in main.py"
print_warning "- Update the README.md with your agent's specific information"
