# AWS infrastructure

Terraform provisions isolated `staging` and `prod` environments. Each has its own
VPC, private application/data subnets, PostgreSQL RDS instance, encrypted Redis,
frontend and application S3 buckets, CloudFront distribution, SQS mail queue/DLQ,
and ECS/Fargate backend service. EventBridge Scheduler starts a short-lived Fargate
task every five minutes for periodic jobs.

## Bootstrap

```bash
cp terraform.tfvars.example terraform.tfvars
# Set github_owner in terraform.tfvars
terraform init
terraform plan
terraform apply
```

This initial configuration uses local Terraform state. Before team use, create an
encrypted/versioned S3 state bucket plus DynamoDB lock table and add an `s3`
backend block. Never commit state or `terraform.tfvars`; both can contain secrets.

After apply, use the outputs to configure GitHub environment variables for both
the `staging` and `prod` environments:

- `AWS_REGION`
- `AWS_DEPLOY_ROLE_ARN` from `github_actions_role_arn`
- Frontend only: `FRONTEND_BUCKET`, `CLOUDFRONT_DISTRIBUTION_ID`, and
  `VITE_API_BASE_URL`

Pushes to `staging` deploy staging. Pushes to `main` deploy production. Add GitHub
environment protection/required reviewers to `prod` before the first release.

## Operational notes

- RDS and Redis are not publicly reachable. ECS tasks run in private subnets and
  use a NAT gateway for outbound dependencies.
- The backend task role can invoke the US Amazon Nova Pro Bedrock inference
  profile. Bedrock usage is metered; monitor model-invocation spend and quotas.
- The default CloudFront hostname and HTTP ALB hostname make initial deployment
  testable. Add Route 53, ACM certificates, and an HTTPS ALB listener before a
  public production launch.
- Terraform generates database/Django secrets. Terraform state is sensitive and
  must be encrypted and access-controlled.
- The scheduled command currently invokes the existing durable email job command.
  Application producers/consumers must be switched to `MAIL_QUEUE_URL` to make SQS
  the source of truth before removing the database-backed queue.
- NAT gateways, RDS, ElastiCache, ALBs, and Fargate incur ongoing AWS charges.
