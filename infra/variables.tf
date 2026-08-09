variable "aws_region" {
  type    = string
  default = "us-east-1"
}
variable "project" {
  type    = string
  default = "workiva"
}
variable "github_owner" {
  type = string
}
variable "backend_repository" {
  type    = string
  default = "hr-backend"
}
variable "frontend_repository" {
  type    = string
  default = "workiva-frontend"
}
variable "db_instance_class" {
  type    = string
  default = "db.t4g.micro"
}
variable "redis_node_type" {
  type    = string
  default = "cache.t4g.micro"
}
variable "production_deletion_protection" {
  type    = bool
  default = true
}
variable "domain_name" {
  type    = string
  default = "workiva.com.ng"
}
variable "cloudfront_certificate_arn" {
  type    = string
  default = "arn:aws:acm:us-east-1:172170847621:certificate/59f28f6d-c5e3-4a03-ac85-f93440d6ade7"
}
