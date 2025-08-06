provider "aws" {
  region = var.region
}

resource "aws_ecr_repository" "registry" {
  name = var.registry_name
  force_delete = var.force_delete

  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = {
    Application = var.app_name
  }
}
