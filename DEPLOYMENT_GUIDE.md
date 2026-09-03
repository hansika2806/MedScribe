# MedScribe Production Deployment Guide

Complete guide for deploying MedScribe to production with all security and compliance features enabled.

---

## Prerequisites

- Docker and Docker Compose installed
- Domain name configured
- SSL certificate (Let's Encrypt or commercial)
- PostgreSQL 15+
- Minimum 8GB RAM, 50GB disk space
- Ubuntu 22.04 LTS or similar Linux distribution

---

## Quick Start (Development)

```bash
# Clone repository
git clone <repository-url>
cd MedScribe

# Copy environment file
cp .env.example .env

# Edit .env with your API keys
nano .env

# Start services
docker-compose up -d

# Check logs
docker-compose logs -f

# Access application
# Frontend: http://localhost:80
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

---

## Production Deployment

### Step 1: Prepare Environment

```bash
# Update system
sudo apt-get update && sudo apt-get upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verify installation
docker --version
docker-compose --version
```

### Step 2: Configure Environment Variables

```bash
# Copy production environment template
cp .env.production .env

# Generate secrets
python -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(64))" >> .env
python -c "from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())" >> .env

# Edit .env file
nano .env
```

Required environment variables:
- `GROQ_API_KEY` - Get from console.groq.com
- `HF_TOKEN` - Get from huggingface.co/settings/tokens
- `POSTGRES_PASSWORD` - Strong database password
- `JWT_SECRET_KEY` - Generated above
- `ENCRYPTION_KEY` - Generated above
- `CORS_ORIGINS` - Your domain (https://yourdomain.com)

### Step 3: Setup SSL Certificates

```bash
# Install Certbot
sudo apt-get install certbot

# Obtain certificate
sudo certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com

# Copy certificates
sudo mkdir -p nginx/ssl
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem nginx/ssl/cert.pem
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem nginx/ssl/key.pem

# Generate DH parameters
sudo openssl dhparam -out nginx/ssl/dhparam.pem 2048

# Set permissions
sudo chmod 644 nginx/ssl/cert.pem
sudo chmod 600 nginx/ssl/key.pem
```

### Step 4: Load Clinical Guidelines

```bash
# Create guidelines directory
mkdir -p data/guidelines

# Download guidelines (see MANUAL_STEPS.md for URLs)
# Place PDFs in data/guidelines/

# Install dependencies
pip install PyPDF2

# Load guidelines into corpus
python backend/tools/load_real_guidelines.py
```

### Step 5: Start Services

```bash
# Start with production profile
docker-compose --profile production up -d

# Check all services are running
docker-compose ps

# View logs
docker-compose logs -f

# Wait for services to be healthy
docker-compose ps | grep healthy
```

### Step 6: Verify Deployment

```bash
# Test health endpoint
curl https://yourdomain.com/health

# Test API
curl https://yourdomain.com/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"dr.sharma","password":"medscribe123"}'

# Check database
docker-compose exec postgres psql -U medscribe_user -d medscribe -c "\dt"

# Check audit logs
tail -f logs/audit.log
```

---

## Security Hardening

### 1. Change Default Passwords

```bash
# Generate new password hashes
python backend/generate_hashes.py

# Update .env with new hashes
nano .env
```

### 2. Configure Firewall

```bash
# Install UFW
sudo apt-get install ufw

# Allow SSH, HTTP, HTTPS
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Enable firewall
sudo ufw enable

# Check status
sudo ufw status
```

### 3. Enable Fail2Ban

```bash
# Install Fail2Ban
sudo apt-get install fail2ban

# Configure
sudo cp /etc/fail2ban/jail.conf /etc/fail2ban/jail.local
sudo nano /etc/fail2ban/jail.local

# Start service
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

### 4. Setup Automated Backups

```bash
# Create backup script
cat > /usr/local/bin/medscribe-backup.sh << 'EOF'
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/var/backups/medscribe"
mkdir -p $BACKUP_DIR

# Backup database
docker-compose -f /path/to/MedScribe/docker-compose.yml exec -T postgres \
  pg_dump -U medscribe_user medscribe | gzip > $BACKUP_DIR/db_$DATE.sql.gz

# Backup data directory
tar -czf $BACKUP_DIR/data_$DATE.tar.gz /path/to/MedScribe/data

# Keep only last 30 days
find $BACKUP_DIR -name "*.gz" -mtime +30 -delete

echo "Backup completed: $DATE"
EOF

chmod +x /usr/local/bin/medscribe-backup.sh

# Add to crontab (daily at 2 AM)
(crontab -l 2>/dev/null; echo "0 2 * * * /usr/local/bin/medscribe-backup.sh") | crontab -
```

---

## Monitoring Setup

### Prometheus + Grafana

```bash
# Start monitoring stack
docker-compose --profile monitoring up -d

# Access Grafana
# URL: https://yourdomain.com:3000
# Default: admin/admin (change immediately)

# Import MedScribe dashboard
# Dashboard ID: (create custom dashboard)
```

### Log Monitoring

```bash
# Install Loki for log aggregation
docker-compose -f docker-compose.monitoring.yml up -d

# View logs in Grafana
# Add Loki data source
# Query: {job="medscribe"}
```

---

## Compliance Configuration

### Enable Audit Logging

Already enabled by default. Verify:

```bash
# Check audit log file
tail -f logs/audit.log

# Query audit database
docker-compose exec postgres psql -U medscribe_user -d medscribe \
  -c "SELECT COUNT(*) FROM audit_log;"

# View recent audit entries
docker-compose exec postgres psql -U medscribe_user -d medscribe \
  -c "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT 10;"
```

### Data Retention Policy

```bash
# Create retention script
cat > /usr/local/bin/medscribe-retention.sh << 'EOF'
#!/bin/bash
# Delete consultations older than 7 years (as per regulations)
docker-compose -f /path/to/MedScribe/docker-compose.yml exec -T postgres \
  psql -U medscribe_user -d medscribe -c \
  "DELETE FROM consultations WHERE created_at < NOW() - INTERVAL '7 years';"

echo "Retention policy applied: $(date)"
EOF

chmod +x /usr/local/bin/medscribe-retention.sh

# Run monthly
(crontab -l 2>/dev/null; echo "0 0 1 * * /usr/local/bin/medscribe-retention.sh") | crontab -
```

---

## Scaling

### Horizontal Scaling

```bash
# Scale backend workers
docker-compose up -d --scale backend=3

# Use load balancer (nginx already configured)
```

### Database Optimization

```bash
# Connect to PostgreSQL
docker-compose exec postgres psql -U medscribe_user -d medscribe

# Create additional indexes
CREATE INDEX CONCURRENTLY idx_consultations_created_physician 
  ON consultations(created_at DESC, physician_username);

CREATE INDEX CONCURRENTLY idx_soap_notes_confidence 
  ON soap_notes(overall_confidence) WHERE approved = false;

# Analyze tables
ANALYZE consultations;
ANALYZE soap_notes;
```

---

## Troubleshooting

### Service Won't Start

```bash
# Check logs
docker-compose logs backend
docker-compose logs postgres

# Restart services
docker-compose restart

# Full reset (WARNING: deletes data)
docker-compose down -v
docker-compose up -d
```

### Database Connection Issues

```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Test connection
docker-compose exec postgres psql -U medscribe_user -d medscribe -c "SELECT 1;"

# Check connection string in .env
grep DATABASE_URL .env
```

### SSL Certificate Issues

```bash
# Check certificate validity
openssl x509 -in nginx/ssl/cert.pem -text -noout | grep "Not After"

# Renew Let's Encrypt certificate
sudo certbot renew

# Copy renewed certificate
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem nginx/ssl/cert.pem
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem nginx/ssl/key.pem

# Restart nginx
docker-compose restart nginx-proxy
```

### High Memory Usage

```bash
# Check memory usage
docker stats

# Reduce backend workers
docker-compose up -d --scale backend=2

# Add swap space
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

---

## Maintenance

### Regular Tasks

**Daily:**
- Check logs for errors: `docker-compose logs --tail=100`
- Verify backups completed: `ls -lh /var/backups/medscribe/`

**Weekly:**
- Review audit logs for suspicious activity
- Check disk space: `df -h`
- Update Docker images: `docker-compose pull && docker-compose up -d`

**Monthly:**
- Review and rotate logs
- Update SSL certificates if needed
- Review and update dependencies
- Perform security scan

### Updates

```bash
# Pull latest code
git pull origin main

# Rebuild containers
docker-compose build

# Restart with new images
docker-compose up -d

# Run database migrations if needed
docker-compose exec backend python -m alembic upgrade head
```

---

## Performance Tuning

### PostgreSQL Tuning

Edit `postgresql.conf`:

```ini
# Memory
shared_buffers = 2GB
effective_cache_size = 6GB
maintenance_work_mem = 512MB
work_mem = 32MB

# Connections
max_connections = 100

# Checkpoints
checkpoint_completion_target = 0.9
wal_buffers = 16MB

# Query Planning
random_page_cost = 1.1
effective_io_concurrency = 200
```

### Nginx Tuning

Edit `nginx/nginx.conf`:

```nginx
worker_processes auto;
worker_connections 2048;

# Enable caching
proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=api_cache:10m max_size=1g;
```

---

## Disaster Recovery

### Backup Restoration

```bash
# Stop services
docker-compose down

# Restore database
gunzip < /var/backups/medscribe/db_20240521_020000.sql.gz | \
  docker-compose exec -T postgres psql -U medscribe_user -d medscribe

# Restore data directory
tar -xzf /var/backups/medscribe/data_20240521_020000.tar.gz -C /

# Start services
docker-compose up -d
```

### Failover Procedure

1. Update DNS to point to backup server
2. Restore latest backup on backup server
3. Start services on backup server
4. Verify functionality
5. Investigate primary server issue

---

## Support

For additional help:

1. Check documentation in `docs/` directory
2. Review `MANUAL_STEPS.md` for detailed procedures
3. Check GitHub issues
4. Contact support team

---

**Last Updated:** 2024-05-21  
**Version:** 1.0  
**Maintainer:** MedScribe Team