provider "aws" {
  region = var.region
}

resource "aws_ecr_repository" "registry" {
  name = var.registry_name
  force_delete = true

  tags = {
    Application = var.app_name
  }
}
