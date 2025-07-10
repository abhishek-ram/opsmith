provider "aws" {
  region = var.region
}

data "aws_ssm_parameter" "ecs_optimized_ami" {
  name = "/aws/service/ecs/optimized-ami/amazon-linux-2023/arm64/recommended"
}

locals {
  ami_id = jsondecode(data.aws_ssm_parameter.ecs_optimized_ami.value)["image_id"]
}

resource "aws_security_group" "instance_sg" {
  name        = "${var.app_name}-sg"
  description = "Security group for ${var.app_name} monolithic instance"

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"] # WARNING: Open to the world. For demo purposes.
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.app_name}-sg"
  }
}

resource "aws_key_pair" "deployer_key" {
  key_name   = "${var.app_name}-key"
  public_key = var.ssh_pub_key
}

resource "aws_instance" "app_server" {
  ami           = local.ami_id
  instance_type = var.instance_type
  key_name      = aws_key_pair.deployer_key.key_name

  vpc_security_group_ids = [aws_security_group.instance_sg.id]

  tags = {
    Name = "${var.app_name}-monolithic-server"
  }
}
