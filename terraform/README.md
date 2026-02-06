# Video Library Terraform

Deploy the video library app to AWS Lightsail.

## Prerequisites

1. [Terraform](https://www.terraform.io/downloads) installed
2. AWS CLI configured with credentials

## Usage

1. Copy the example variables file:
   ```bash
   cp terraform.tfvars.example terraform.tfvars
   ```

2. Edit `terraform.tfvars` with your values

3. Initialize Terraform:
   ```bash
   terraform init
   ```

4. Preview changes:
   ```bash
   terraform plan
   ```

5. Apply:
   ```bash
   terraform apply
   ```

## Outputs

After apply, you'll see:
- `static_ip` - Your server's IP address
- `app_url` - URL to access the app
- `ssh_command` - Command to SSH into the server

## Destroy

To tear down the infrastructure:
```bash
terraform destroy
```

## Bundle Options (Instance Sizes)

| Bundle ID    | RAM    | vCPUs | SSD    | Price/month |
|--------------|--------|-------|--------|-------------|
| nano_3_0     | 512 MB | 2     | 20 GB  | $3.50       |
| micro_3_0    | 1 GB   | 2     | 40 GB  | $5.00       |
| small_3_0    | 2 GB   | 2     | 60 GB  | $10.00      |
| medium_3_0   | 4 GB   | 2     | 80 GB  | $20.00      |
| large_3_0    | 8 GB   | 2     | 160 GB | $40.00      |
