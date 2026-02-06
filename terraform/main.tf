terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  required_version = ">= 1.0"
}

provider "aws" {
  region = var.aws_region
}

# Lightsail Instance
resource "aws_lightsail_instance" "video_library" {
  name              = var.instance_name
  availability_zone = "${var.aws_region}a"
  blueprint_id      = "ubuntu_22_04"
  bundle_id         = var.bundle_id

  user_data = <<-EOF
    #!/bin/bash
    apt-get update
    apt-get install -y python3-venv python3-pip ffmpeg git

    # Create app directory
    mkdir -p /home/ubuntu/video-library
    cd /home/ubuntu/video-library

    # Clone repository
    git clone ${var.git_repo_url} .

    # Setup virtual environment
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    pip install gunicorn supabase boto3

    # Create .env file
    cat > .env << 'ENVEOF'
    SUPABASE_URL=${var.supabase_url}
    SUPABASE_KEY=${var.supabase_key}
    AWS_ACCESS_KEY_ID=${var.aws_access_key_id}
    AWS_SECRET_ACCESS_KEY=${var.aws_secret_access_key}
    AWS_S3_BUCKET=${var.s3_bucket}
    AWS_REGION=${var.aws_region}
    SECRET_KEY=${var.secret_key}
    DROPBOX_APP_KEY=${var.dropbox_app_key}
    SMTP_SERVER=${var.smtp_server}
    SMTP_PORT=${var.smtp_port}
    SMTP_USERNAME=${var.smtp_username}
    SMTP_PASSWORD=${var.smtp_password}
    ENVEOF

    # Set ownership
    chown -R ubuntu:ubuntu /home/ubuntu/video-library

    # Create systemd service
    cat > /etc/systemd/system/video-library.service << 'SERVICEEOF'
    [Unit]
    Description=Video Library Gunicorn Service
    After=network.target

    [Service]
    User=ubuntu
    Group=ubuntu
    WorkingDirectory=/home/ubuntu/video-library
    Environment="PATH=/home/ubuntu/video-library/venv/bin"
    ExecStart=/home/ubuntu/video-library/venv/bin/gunicorn --bind 0.0.0.0:5001 --workers 2 --timeout 120 app:app
    Restart=always

    [Install]
    WantedBy=multi-user.target
    SERVICEEOF

    systemctl daemon-reload
    systemctl enable video-library
    systemctl start video-library
  EOF

  tags = {
    Name        = var.instance_name
    Environment = var.environment
  }
}

# Static IP
resource "aws_lightsail_static_ip" "video_library" {
  name = "${var.instance_name}-static-ip"
}

# Attach Static IP to Instance
resource "aws_lightsail_static_ip_attachment" "video_library" {
  static_ip_name = aws_lightsail_static_ip.video_library.name
  instance_name  = aws_lightsail_instance.video_library.name
}

# Firewall rules
resource "aws_lightsail_instance_public_ports" "video_library" {
  instance_name = aws_lightsail_instance.video_library.name

  port_info {
    protocol  = "tcp"
    from_port = 22
    to_port   = 22
  }

  port_info {
    protocol  = "tcp"
    from_port = 80
    to_port   = 80
  }

  port_info {
    protocol  = "tcp"
    from_port = 443
    to_port   = 443
  }

  port_info {
    protocol  = "tcp"
    from_port = 5001
    to_port   = 5001
  }
}
