#!/bin/bash

# EC2 Deployment Script for Database Q&A Application
# Run this script on your EC2 instance after uploading your code

set -e  # Exit on any error

echo "🚀 Starting deployment on EC2..."

# Update system packages
echo "📦 Updating system packages..."
sudo apt-get update
sudo apt-get upgrade -y

# Install Docker and Docker Compose
echo "🐳 Installing Docker..."
if ! command -v docker &> /dev/null; then
    sudo apt-get install -y apt-transport-https ca-certificates curl gnupg lsb-release
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io
    
    # Add current user to docker group
    sudo usermod -aG docker $USER
    echo "⚠️  You may need to log out and back in for Docker permissions to take effect"
fi

# Install Docker Compose
echo "📋 Installing Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
fi

# Install Python and pip (backup option)
echo "🐍 Installing Python dependencies..."
sudo apt-get install -y python3 python3-pip python3-venv

# Create application directory
APP_DIR="/home/ubuntu/database-qa-app"
echo "📁 Setting up application directory: $APP_DIR"

# Create directory if it doesn't exist
mkdir -p $APP_DIR
cd $APP_DIR

# Create logs directory
mkdir -p logs

# Set up environment file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating default .env file..."
    cat > .env << EOF
# Database Configuration
DB_TYPE=postgresql
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=bluswap
POSTGRES_USER=bluswap
POSTGRES_PASSWORD=Password1\$

# LLM Configuration
LLM_PROVIDER=google_genai
LLM_MODEL=gemini-2.5-flash
GOOGLE_API_KEY=your_google_api_key_here

# Application Configuration
HUMAN_INTERVENTION=false
AUTO_APPROVE_QUERIES=true
MAX_QUERY_RESULTS=10

# Server Configuration
HOST=0.0.0.0
PORT=8000
DEBUG=false
LOG_LEVEL=INFO
EOF
    echo "⚠️  Please edit .env file with your actual credentials!"
fi

# Create systemd service file for auto-start
echo "⚙️  Setting up systemd service..."
sudo tee /etc/systemd/system/database-qa.service > /dev/null << EOF
[Unit]
Description=Database Q&A Application
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$APP_DIR
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

# Enable the service
sudo systemctl daemon-reload
sudo systemctl enable database-qa.service

# Set up firewall
echo "🔥 Configuring firewall..."
sudo ufw allow ssh
sudo ufw allow 80
sudo ufw allow 443
sudo ufw allow 8000
sudo ufw --force enable

# Create deployment script
cat > start.sh << 'EOF'
#!/bin/bash
echo "🚀 Starting Database Q&A Application..."
docker-compose down
docker-compose up --build -d
echo "✅ Application started!"
echo "📊 Check status: docker-compose ps"
echo "📋 View logs: docker-compose logs -f"
echo "🌐 API available at: http://$(curl -s ifconfig.me):8000"
echo "📖 API docs at: http://$(curl -s ifconfig.me):8000/docs"
EOF

chmod +x start.sh

# Create stop script
cat > stop.sh << 'EOF'
#!/bin/bash
echo "⏹️  Stopping Database Q&A Application..."
docker-compose down
echo "✅ Application stopped!"
EOF

chmod +x stop.sh

# Create update script
cat > update.sh << 'EOF'
#!/bin/bash
echo "🔄 Updating Database Q&A Application..."
git pull origin main  # If using git
docker-compose down
docker-compose build --no-cache
docker-compose up -d
echo "✅ Application updated and restarted!"
EOF

chmod +x update.sh

# Create backup script
cat > backup.sh << 'EOF'
#!/bin/bash
echo "