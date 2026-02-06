output "instance_name" {
  description = "Name of the Lightsail instance"
  value       = aws_lightsail_instance.video_library.name
}

output "static_ip" {
  description = "Static IP address"
  value       = aws_lightsail_static_ip.video_library.ip_address
}

output "app_url" {
  description = "Application URL"
  value       = "http://${aws_lightsail_static_ip.video_library.ip_address}:5001"
}

output "ssh_command" {
  description = "SSH command to connect"
  value       = "ssh ubuntu@${aws_lightsail_static_ip.video_library.ip_address}"
}
