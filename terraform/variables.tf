variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-2"
}

variable "instance_name" {
  description = "Name for the Lightsail instance"
  type        = string
  default     = "video-library"
}

variable "bundle_id" {
  description = "Lightsail bundle ID (instance size)"
  type        = string
  default     = "nano_3_0" # $3.50/month - 512MB RAM, 2 vCPUs, 20GB SSD
  # Options: nano_3_0, micro_3_0, small_3_0, medium_3_0, large_3_0
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "production"
}

variable "git_repo_url" {
  description = "Git repository URL"
  type        = string
  default     = "https://github.com/kdrivas1989/kd-video-library.git"
}

# Supabase
variable "supabase_url" {
  description = "Supabase project URL"
  type        = string
  sensitive   = true
}

variable "supabase_key" {
  description = "Supabase API key"
  type        = string
  sensitive   = true
}

# AWS S3
variable "aws_access_key_id" {
  description = "AWS Access Key ID for S3"
  type        = string
  sensitive   = true
}

variable "aws_secret_access_key" {
  description = "AWS Secret Access Key for S3"
  type        = string
  sensitive   = true
}

variable "s3_bucket" {
  description = "S3 bucket name"
  type        = string
  default     = "uspa-video-library"
}

# App
variable "secret_key" {
  description = "Flask secret key"
  type        = string
  sensitive   = true
}

variable "dropbox_app_key" {
  description = "Dropbox app key"
  type        = string
  default     = ""
}

# SMTP
variable "smtp_server" {
  description = "SMTP server"
  type        = string
  default     = "smtp.gmail.com"
}

variable "smtp_port" {
  description = "SMTP port"
  type        = string
  default     = "587"
}

variable "smtp_username" {
  description = "SMTP username"
  type        = string
  sensitive   = true
}

variable "smtp_password" {
  description = "SMTP password"
  type        = string
  sensitive   = true
}
