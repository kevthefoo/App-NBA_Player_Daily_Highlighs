# AWS Deployment Guide - NBA Player Daily Highlights

This guide walks through deploying the NBA highlights automation system on AWS.

## Architecture Overview

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  EventBridge    │────▶│   EC2 Instance  │────▶│    YouTube      │
│  (Scheduler)    │     │  (Ubuntu 22.04) │     │    Upload       │
└─────────────────┘     └────────┬────────┘     └─────────────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │   S3 Bucket     │
                        │ (Video Storage) │
                        └─────────────────┘
```

## Prerequisites

- AWS Account with appropriate permissions
- YouTube API credentials (`client_secrets.json`)
- Basic familiarity with AWS Console or CLI

---

## Step 1: Launch EC2 Instance

### 1.1 Choose Instance Type

1. Go to **EC2 Dashboard** → **Launch Instance**
2. Configure:
   - **Name**: `nba-highlights-automation`
   - **AMI**: Ubuntu Server 22.04 LTS (64-bit x86)
   - **Instance type**: `t3.medium` (2 vCPU, 4GB RAM) - needed for video processing
   - **Key pair**: Create or select existing key pair for SSH access

### 1.2 Configure Storage

- **Root volume**: 30 GB gp3 (for OS, dependencies, and temporary video files)

### 1.3 Configure Security Group

Create a security group with:
- **SSH (22)**: Your IP only
- **Outbound**: All traffic (for API calls and uploads)

### 1.4 Launch and Connect

```bash
# Connect via SSH
ssh -i your-key.pem ubuntu@<ec2-public-ip>
```

---

## Step 2: Install System Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3.11+ and pip
sudo apt install -y python3.11 python3.11-venv python3-pip

# Install FFmpeg (required for video processing)
sudo apt install -y ffmpeg

# Install additional dependencies for MoviePy
sudo apt install -y libsm6 libxext6 libxrender-dev

# Verify installations
python3.11 --version
ffmpeg -version
```

---

## Step 3: Clone and Setup Project

```bash
# Create app directory
mkdir -p ~/apps && cd ~/apps

# Clone your repository (or upload files)
git clone https://github.com/your-username/nba-highlights.git
cd nba-highlights

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

---

## Step 4: Configure Environment Variables

```bash
# Create .env file
nano .env
```

Add the following content:

```env
# YouTube API (optional if using headless auth)
YOUTUBE_CHANNEL_ID=your_channel_id_here

# Chrome paths not needed on server (we use API-based upload)
```

---

## Step 5: Setup YouTube API Credentials

### 5.1 Upload Client Secrets

```bash
# From your local machine, upload client_secrets.json
scp -i your-key.pem client_secrets.json ubuntu@<ec2-public-ip>:~/apps/nba-highlights/
```

### 5.2 Authenticate YouTube API (One-time Setup)

Since EC2 doesn't have a browser, authenticate locally first:

**Option A: Local Authentication Then Transfer**

1. Run authentication locally:
   ```bash
   # On your local machine
   python -c "from src.video.upload_video import YouTubeUploader; u = YouTubeUploader(); u.authenticate()"
   ```

2. Upload the generated `token.pickle` to EC2:
   ```bash
   scp -i your-key.pem token.pickle ubuntu@<ec2-public-ip>:~/apps/nba-highlights/
   ```

**Option B: SSH Tunnel Authentication**

1. Create SSH tunnel with port forwarding:
   ```bash
   ssh -i your-key.pem -L 8080:localhost:8080 ubuntu@<ec2-public-ip>
   ```

2. Run authentication on EC2:
   ```bash
   cd ~/apps/nba-highlights
   source venv/bin/activate
   python -c "from src.video.upload_video import YouTubeUploader; u = YouTubeUploader(); u.authenticate()"
   ```

3. Open the authorization URL in your local browser

---

## Step 6: Test the Application

```bash
# Activate virtual environment
cd ~/apps/nba-highlights
source venv/bin/activate

# Run with a specific date to test
python main.py --date 2025-01-19

# Check logs
ls -la build/
```

---

## Step 7: Setup Automated Scheduling

### Option A: Using Cron (Simple)

```bash
# Edit crontab
crontab -e

# Add this line to run daily at 10:00 AM UTC (after games finish)
0 10 * * * cd /home/ubuntu/apps/nba-highlights && /home/ubuntu/apps/nba-highlights/venv/bin/python main.py >> /home/ubuntu/apps/nba-highlights/cron.log 2>&1
```

### Option B: Using Systemd Timer (Recommended)

Create service file:

```bash
sudo nano /etc/systemd/system/nba-highlights.service
```

```ini
[Unit]
Description=NBA Highlights Automation
After=network.target

[Service]
Type=oneshot
User=ubuntu
WorkingDirectory=/home/ubuntu/apps/nba-highlights
Environment="PATH=/home/ubuntu/apps/nba-highlights/venv/bin"
ExecStart=/home/ubuntu/apps/nba-highlights/venv/bin/python main.py
StandardOutput=append:/home/ubuntu/apps/nba-highlights/logs/output.log
StandardError=append:/home/ubuntu/apps/nba-highlights/logs/error.log

[Install]
WantedBy=multi-user.target
```

Create timer file:

```bash
sudo nano /etc/systemd/system/nba-highlights.timer
```

```ini
[Unit]
Description=Run NBA Highlights daily

[Timer]
OnCalendar=*-*-* 10:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

Enable and start:

```bash
# Create logs directory
mkdir -p ~/apps/nba-highlights/logs

# Enable and start timer
sudo systemctl daemon-reload
sudo systemctl enable nba-highlights.timer
sudo systemctl start nba-highlights.timer

# Check status
sudo systemctl status nba-highlights.timer
sudo systemctl list-timers
```

---

## Step 8: Setup S3 for Video Storage (Optional)

If you want to archive videos to S3:

### 8.1 Create S3 Bucket

```bash
aws s3 mb s3://nba-highlights-archive --region us-east-1
```

### 8.2 Configure IAM Role

1. Go to **IAM** → **Roles** → **Create Role**
2. Select **EC2** as use case
3. Attach policy: `AmazonS3FullAccess` (or create custom policy)
4. Attach role to EC2 instance

### 8.3 Sync Videos to S3

Add to your cron job or create a separate script:

```bash
# Sync build folder to S3
aws s3 sync ~/apps/nba-highlights/build/ s3://nba-highlights-archive/

# Or add to main.py after processing
```

---

## Step 9: Monitoring and Alerts (Optional)

### 9.1 CloudWatch Logs

```bash
# Install CloudWatch agent
sudo apt install -y amazon-cloudwatch-agent

# Configure to send logs
sudo nano /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json
```

```json
{
  "logs": {
    "logs_collected": {
      "files": {
        "collect_list": [
          {
            "file_path": "/home/ubuntu/apps/nba-highlights/logs/*.log",
            "log_group_name": "nba-highlights",
            "log_stream_name": "{instance_id}"
          }
        ]
      }
    }
  }
}
```

### 9.2 SNS Alerts for Failures

Create a simple alert script:

```bash
nano ~/apps/nba-highlights/run_with_alert.sh
```

```bash
#!/bin/bash
cd /home/ubuntu/apps/nba-highlights
source venv/bin/activate

if ! python main.py; then
    aws sns publish \
        --topic-arn "arn:aws:sns:us-east-1:123456789:nba-highlights-alerts" \
        --message "NBA Highlights job failed on $(date)"
fi
```

---

## Step 10: Cost Optimization

### Estimated Monthly Costs

| Resource | Specification | Cost/Month |
|----------|--------------|------------|
| EC2 t3.medium | On-demand | ~$30 |
| EC2 t3.medium | Reserved (1yr) | ~$18 |
| EBS Storage | 30 GB gp3 | ~$2.50 |
| S3 Storage | 50 GB | ~$1.15 |
| Data Transfer | 100 GB out | ~$9 |
| **Total** | | **~$30-45** |

### Cost Saving Tips

1. **Use Spot Instances**: Up to 90% savings for interruptible workloads
2. **Schedule Instance**: Start/stop EC2 only when needed
3. **Reserved Instances**: 1-year commitment saves ~40%
4. **Clean up old videos**: Delete from build/ after S3 upload

---

## Troubleshooting

### Common Issues

**1. MoviePy/FFmpeg errors**
```bash
# Ensure FFmpeg is installed
sudo apt install -y ffmpeg
# Check path
which ffmpeg
```

**2. YouTube API quota exceeded**
- Default quota: 10,000 units/day
- Video upload: 1,600 units each
- Request quota increase in Google Cloud Console

**3. Memory issues during video processing**
```bash
# Check memory
free -h
# Consider upgrading to t3.large if needed
```

**4. Token expired**
```bash
# Delete old token and re-authenticate
rm token.pickle
python -c "from src.video.upload_video import YouTubeUploader; u = YouTubeUploader(); u.authenticate()"
```

---

## Quick Reference Commands

```bash
# SSH into instance
ssh -i your-key.pem ubuntu@<ec2-public-ip>

# Activate environment
cd ~/apps/nba-highlights && source venv/bin/activate

# Run manually
python main.py --date 2025-01-19

# Check timer status
sudo systemctl status nba-highlights.timer

# View logs
tail -f logs/output.log

# Check disk space
df -h
```

---

## Security Best Practices

1. **Never commit credentials** - Keep `client_secrets.json` and `token.pickle` out of git
2. **Use IAM roles** - Don't hardcode AWS credentials
3. **Restrict SSH access** - Only allow your IP in security group
4. **Enable MFA** - On your AWS root account
5. **Regular updates** - `sudo apt update && sudo apt upgrade`
