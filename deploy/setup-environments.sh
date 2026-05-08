#!/bin/bash
# Setup script for dev and staging environments
# Run this on your server to get everything running

set -e

echo "🚀 Setting up B2B Lead Research environments..."

# Check if running as root for port 80/443
if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root (or with sudo) for port binding"
    exit 1
fi

# Install Docker if not present
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
fi

# Install Docker Compose if not present
if ! command -v docker-compose &> /dev/null; then
    echo "Installing Docker Compose..."
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
fi

# Create network
mkdir -p /opt/b2b-leads
cd /opt/b2b-leads

# Clone or pull latest
git clone https://github.com/yourusername/b2b-lead-research.git . 2>/dev/null || git pull

# Create environment files
cat > .env.dev << EOF
ENV=dev
GOOGLE_PLACES_API_KEY=your_key_here
COMPANIES_HOUSE_API_KEY=your_key_here
EOF

cat > .env.staging << EOF
ENV=staging
GOOGLE_PLACES_API_KEY=your_key_here
COMPANIES_HOUSE_API_KEY=your_key_here
EOF

# SSL certificates (use Let's Encrypt in production)
mkdir -p deploy/ssl

# Start environments
echo "Starting environments..."
docker-compose -f deploy/docker-compose.yml up -d

echo ""
echo "✅ Environments are running!"
echo ""
echo "Dev:      http://dev-b2b-leads.akzain.com"
echo "Staging:  http://staging-b2b-leads.akzain.com"
echo ""
echo "To view logs:"
echo "  Dev:      docker logs -f b2b-dev-dashboard"
echo "  Staging:  docker logs -f b2b-staging-dashboard"
echo ""
echo "To restart:"
echo "  docker-compose -f deploy/docker-compose.yml restart"
