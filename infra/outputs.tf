output "github_actions_role_arn" {
  value = aws_iam_role.github.arn
}
output "ecr_repository_url" {
  value = aws_ecr_repository.backend.repository_url
}
output "api_urls" {
  value = {
    for env, lb in aws_lb.this : env => "http://${lb.dns_name}"
  }
}
output "frontend_urls" {
  value = {
    for env, cdn in aws_cloudfront_distribution.frontend : env => "https://${cdn.domain_name}"
  }
}
output "frontend_buckets" {
  value = {
    for env, b in aws_s3_bucket.frontend : env => b.id
  }
}
output "cloudfront_distribution_ids" {
  value = {
    for env, cdn in aws_cloudfront_distribution.frontend : env => cdn.id
  }
}
output "mail_queue_urls" {
  value = {
    for env, q in aws_sqs_queue.mail : env => q.url
  }
}
output "local_dev_uploads_access_key_id" {
  value = aws_iam_access_key.local_dev_uploads.id
}
output "local_dev_uploads_secret_access_key" {
  value     = aws_iam_access_key.local_dev_uploads.secret
  sensitive = true
}
