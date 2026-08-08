data "aws_availability_zones" "available" {
  state = "available"
}
data "aws_caller_identity" "current" {}

locals {
  environments = toset(["staging", "prod"])
  azs          = slice(data.aws_availability_zones.available.names, 0, 2)
  cidrs = {
    staging = "10.20.0.0/16", prod = "10.30.0.0/16"
  }
  bucket_base = "${var.project}-${data.aws_caller_identity.current.account_id}"
}

resource "aws_vpc" "this" {
  for_each             = local.environments
  cidr_block           = local.cidrs[each.key]
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags = {
    Name = "${var.project}-${each.key}"
  }
}

resource "aws_internet_gateway" "this" {
  for_each = local.environments
  vpc_id   = aws_vpc.this[each.key].id
}

resource "aws_subnet" "public" {
  for_each = {
    for item in setproduct(local.environments, toset(["0", "1"])) : "${item[0]}-${item[1]}" => {
      env = item[0], index = tonumber(item[1])
    }
  }
  vpc_id                  = aws_vpc.this[each.value.env].id
  availability_zone       = local.azs[each.value.index]
  cidr_block              = cidrsubnet(local.cidrs[each.value.env], 8, each.value.index)
  map_public_ip_on_launch = true
  tags = {
    Name = "${var.project}-${each.value.env}-public-${each.value.index + 1}"
  }
}

resource "aws_subnet" "private" {
  for_each = {
    for item in setproduct(local.environments, toset(["0", "1"])) : "${item[0]}-${item[1]}" => {
      env = item[0], index = tonumber(item[1])
    }
  }
  vpc_id            = aws_vpc.this[each.value.env].id
  availability_zone = local.azs[each.value.index]
  cidr_block        = cidrsubnet(local.cidrs[each.value.env], 8, each.value.index + 10)
  tags = {
    Name = "${var.project}-${each.value.env}-private-${each.value.index + 1}"
  }
}

resource "aws_eip" "nat" {
  for_each = local.environments
  domain   = "vpc"
}
resource "aws_nat_gateway" "this" {
  for_each      = local.environments
  allocation_id = aws_eip.nat[each.key].id
  subnet_id     = aws_subnet.public["${each.key}-0"].id
  depends_on    = [aws_internet_gateway.this]
}
resource "aws_route_table" "public" {
  for_each = local.environments
  vpc_id   = aws_vpc.this[each.key].id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this[each.key].id
  }
}
resource "aws_route_table" "private" {
  for_each = local.environments
  vpc_id   = aws_vpc.this[each.key].id
  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.this[each.key].id
  }
}
resource "aws_route_table_association" "public" {
  for_each       = aws_subnet.public
  subnet_id      = each.value.id
  route_table_id = aws_route_table.public[split("-", each.key)[0]].id
}
resource "aws_route_table_association" "private" {
  for_each       = aws_subnet.private
  subnet_id      = each.value.id
  route_table_id = aws_route_table.private[split("-", each.key)[0]].id
}

resource "aws_s3_bucket" "frontend" {
  for_each = local.environments
  bucket   = "${local.bucket_base}-${each.key}-frontend"
}
resource "aws_s3_bucket_public_access_block" "frontend" {
  for_each                = local.environments
  bucket                  = aws_s3_bucket.frontend[each.key].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket" "app" {
  for_each = local.environments
  bucket   = "${local.bucket_base}-${each.key}-app"
}
resource "aws_s3_bucket_public_access_block" "app" {
  for_each                = local.environments
  bucket                  = aws_s3_bucket.app[each.key].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket_versioning" "app" {
  for_each = local.environments
  bucket   = aws_s3_bucket.app[each.key].id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_cloudfront_origin_access_control" "frontend" {
  for_each                          = local.environments
  name                              = "${var.project}-${each.key}-frontend"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}
resource "aws_cloudfront_distribution" "frontend" {
  for_each            = local.environments
  enabled             = true
  default_root_object = "index.html"
  origin {
    domain_name              = aws_s3_bucket.frontend[each.key].bucket_regional_domain_name
    origin_id                = "s3"
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend[each.key].id

  }
  default_cache_behavior {
    target_origin_id       = "s3"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }
    min_ttl     = 0
    default_ttl = 3600
    max_ttl     = 86400

  }
  custom_error_response {
    error_code         = 403
    response_code      = 200
    response_page_path = "/index.html"
  }
  custom_error_response {
    error_code         = 404
    response_code      = 200
    response_page_path = "/index.html"
  }
  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }
  viewer_certificate {
    cloudfront_default_certificate = true
  }
}
resource "aws_s3_bucket_policy" "frontend" {
  for_each = local.environments
  bucket   = aws_s3_bucket.frontend[each.key].id
  policy = jsonencode({
    Version = "2012-10-17", Statement = [{
      Effect = "Allow", Principal = {
        Service = "cloudfront.amazonaws.com"
        }, Action = "s3:GetObject", Resource = "${aws_s3_bucket.frontend[each.key].arn}/*", Condition = {
        StringEquals = {
          "AWS:SourceArn" = aws_cloudfront_distribution.frontend[each.key].arn
        }
      }
    }]
  })
}

resource "aws_security_group" "alb" {
  for_each = local.environments
  name     = "${var.project}-${each.key}-alb"
  vpc_id   = aws_vpc.this[each.key].id
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
resource "aws_security_group" "ecs" {
  for_each = local.environments
  name     = "${var.project}-${each.key}-ecs"
  vpc_id   = aws_vpc.this[each.key].id
  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb[each.key].id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
resource "aws_security_group" "data" {
  for_each = local.environments
  name     = "${var.project}-${each.key}-data"
  vpc_id   = aws_vpc.this[each.key].id
  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs[each.key].id]
  }
  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs[each.key].id]
  }
}

resource "random_password" "db" {
  for_each = local.environments
  length   = 32
  special  = false
}
resource "random_password" "django" {
  for_each = local.environments
  length   = 50
  special  = false
}
resource "aws_db_subnet_group" "this" {
  for_each   = local.environments
  name       = "${var.project}-${each.key}"
  subnet_ids = [for i in range(2) : aws_subnet.private["${each.key}-${i}"].id]
}
resource "aws_db_instance" "this" {
  for_each                   = local.environments
  identifier                 = "${var.project}-${each.key}"
  engine                     = "postgres"
  engine_version             = "17"
  instance_class             = var.db_instance_class
  allocated_storage          = 20
  max_allocated_storage      = 100
  storage_encrypted          = true
  db_name                    = "workiva"
  username                   = "workiva_admin"
  password                   = random_password.db[each.key].result
  db_subnet_group_name       = aws_db_subnet_group.this[each.key].name
  vpc_security_group_ids     = [aws_security_group.data[each.key].id]
  publicly_accessible        = false
  backup_retention_period    = each.key == "prod" ? 14 : 3
  deletion_protection        = each.key == "prod" ? var.production_deletion_protection : false
  skip_final_snapshot        = each.key != "prod"
  final_snapshot_identifier  = each.key == "prod" ? "${var.project}-prod-final" : null
  auto_minor_version_upgrade = true
}
resource "aws_elasticache_subnet_group" "this" {
  for_each   = local.environments
  name       = "${var.project}-${each.key}"
  subnet_ids = [for i in range(2) : aws_subnet.private["${each.key}-${i}"].id]
}
resource "aws_elasticache_replication_group" "this" {
  for_each                   = local.environments
  replication_group_id       = "${var.project}-${each.key}"
  description                = "${var.project} ${each.key} cache"
  node_type                  = var.redis_node_type
  num_cache_clusters         = each.key == "prod" ? 2 : 1
  engine                     = "redis"
  port                       = 6379
  subnet_group_name          = aws_elasticache_subnet_group.this[each.key].name
  security_group_ids         = [aws_security_group.data[each.key].id]
  transit_encryption_enabled = true
  at_rest_encryption_enabled = true
  automatic_failover_enabled = each.key == "prod"
}

resource "aws_sqs_queue" "mail_dlq" {
  for_each                  = local.environments
  name                      = "${var.project}-${each.key}-mail-dlq"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
}
resource "aws_sqs_queue" "mail" {
  for_each                   = local.environments
  name                       = "${var.project}-${each.key}-mail"
  visibility_timeout_seconds = 120
  sqs_managed_sse_enabled    = true
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.mail_dlq[each.key].arn, maxReceiveCount = 5
  })
}

resource "aws_ecr_repository" "backend" {
  name                 = "${var.project}-backend"
  image_tag_mutability = "MUTABLE"
  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_iam_role" "codebuild" {
  name = "${var.project}-codebuild"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "codebuild.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "codebuild" {
  role = aws_iam_role.codebuild.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:PutImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_codebuild_project" "backend_bootstrap" {
  name         = "${var.project}-backend-bootstrap"
  service_role = aws_iam_role.codebuild.arn

  source {
    type            = "GITHUB"
    location        = "https://github.com/${var.github_owner}/${var.backend_repository}.git"
    git_clone_depth = 1
    buildspec       = <<-YAML
      version: 0.2
      phases:
        pre_build:
          commands:
            - aws ecr get-login-password --region $AWS_DEFAULT_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com
        build:
          commands:
            - docker build -t $REPOSITORY_URI:prod -t $REPOSITORY_URI:staging .
        post_build:
          commands:
            - docker push $REPOSITORY_URI:prod
            - docker push $REPOSITORY_URI:staging
    YAML
  }

  artifacts { type = "NO_ARTIFACTS" }
  environment {
    compute_type                = "BUILD_GENERAL1_SMALL"
    image                       = "aws/codebuild/standard:7.0"
    type                        = "LINUX_CONTAINER"
    image_pull_credentials_type = "CODEBUILD"
    privileged_mode             = true
    environment_variable {
      name  = "AWS_ACCOUNT_ID"
      value = data.aws_caller_identity.current.account_id
    }
    environment_variable {
      name  = "REPOSITORY_URI"
      value = aws_ecr_repository.backend.repository_url
    }
  }
}
resource "aws_ecs_cluster" "this" {
  for_each = local.environments
  name     = "${var.project}-${each.key}"
}
resource "aws_cloudwatch_log_group" "backend" {
  for_each          = local.environments
  name              = "/ecs/${var.project}-${each.key}"
  retention_in_days = 30
}

resource "aws_iam_role" "ecs_execution" {
  name = "${var.project}-ecs-execution"
  assume_role_policy = jsonencode({
    Version = "2012-10-17", Statement = [{
      Effect = "Allow", Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }, Action = "sts:AssumeRole"
    }]
  })
}
resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}
resource "aws_iam_role" "ecs_task" {
  name = "${var.project}-ecs-task"
  assume_role_policy = jsonencode({
    Version = "2012-10-17", Statement = [{
      Effect = "Allow", Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }, Action = "sts:AssumeRole"
    }]
  })
}
resource "aws_iam_role_policy" "ecs_task" {
  role = aws_iam_role.ecs_task.id
  policy = jsonencode({
    Version = "2012-10-17", Statement = [
      {
        Effect = "Allow", Action = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"], Resource = [for b in aws_s3_bucket.app : "${b.arn}/*"]
      },
      {
        Effect = "Allow", Action = ["sqs:SendMessage", "sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"], Resource = concat([for q in aws_sqs_queue.mail : q.arn], [for q in aws_sqs_queue.mail_dlq : q.arn])
      }
    ]
  })
}

resource "aws_lb" "this" {
  for_each           = local.environments
  name               = "${var.project}-${each.key}"
  load_balancer_type = "application"
  subnets            = [for i in range(2) : aws_subnet.public["${each.key}-${i}"].id]
  security_groups    = [aws_security_group.alb[each.key].id]
}
resource "aws_lb_target_group" "this" {
  for_each    = local.environments
  name        = "${var.project}-${each.key}"
  port        = 8000
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = aws_vpc.this[each.key].id
  health_check {
    path    = "/api/v1/"
    matcher = "200-499"
  }
}
resource "aws_lb_listener" "http" {
  for_each          = local.environments
  load_balancer_arn = aws_lb.this[each.key].arn
  port              = 80
  protocol          = "HTTP"
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.this[each.key].arn
  }
}

resource "aws_ecs_task_definition" "backend" {
  for_each                 = local.environments
  family                   = "${var.project}-${each.key}-backend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn
  container_definitions = jsonencode([{
    name = "backend", image = "${aws_ecr_repository.backend.repository_url}:${each.key}", essential = true, portMappings = [{
      containerPort = 8000
    }],
    environment = [
      {
        name = "DJANGO_ALLOWED_HOSTS", value = aws_lb.this[each.key].dns_name
        }, {
        name = "DJANGO_DEBUG", value = "false"
      },
      {
        name = "DB_NAME", value = aws_db_instance.this[each.key].db_name
        }, {
        name = "DB_USER", value = aws_db_instance.this[each.key].username
      },
      {
        name = "DB_PASSWORD", value = random_password.db[each.key].result
        }, {
        name = "DB_HOST", value = aws_db_instance.this[each.key].address
      },
      {
        name = "DB_SSLMODE", value = "require"
        }, {
        name = "DJANGO_SECRET_KEY", value = random_password.django[each.key].result
      },
      {
        name = "REDIS_URL", value = "rediss://${aws_elasticache_replication_group.this[each.key].primary_endpoint_address}:6379/1"
      },
      {
        name = "AWS_STORAGE_BUCKET_NAME", value = aws_s3_bucket.app[each.key].bucket
        }, {
        name = "MAIL_QUEUE_URL", value = aws_sqs_queue.mail[each.key].url
      },
      {
        name = "AWS_REGION", value = var.aws_region
      }
    ],
    logConfiguration = {
      logDriver = "awslogs", options = {
        "awslogs-group" = aws_cloudwatch_log_group.backend[each.key].name, "awslogs-region" = var.aws_region, "awslogs-stream-prefix" = "backend"
      }
    }

  }])
}
resource "aws_ecs_service" "backend" {
  for_each        = local.environments
  name            = "backend"
  cluster         = aws_ecs_cluster.this[each.key].id
  task_definition = aws_ecs_task_definition.backend[each.key].arn
  desired_count   = each.key == "prod" ? 2 : 1
  launch_type     = "FARGATE"
  network_configuration {
    subnets          = [for i in range(2) : aws_subnet.private["${each.key}-${i}"].id]
    security_groups  = [aws_security_group.ecs[each.key].id]
    assign_public_ip = false
  }
  load_balancer {
    target_group_arn = aws_lb_target_group.this[each.key].arn
    container_name   = "backend"
    container_port   = 8000
  }
  depends_on = [aws_lb_listener.http]
  lifecycle {
    ignore_changes = [task_definition]
  }
}

resource "aws_iam_role" "scheduler" {
  name = "${var.project}-scheduler"
  assume_role_policy = jsonencode({
    Version = "2012-10-17", Statement = [{
      Effect = "Allow", Principal = {
        Service = "scheduler.amazonaws.com"
      }, Action = "sts:AssumeRole"
    }]
  })
}
resource "aws_iam_role_policy" "scheduler" {
  role = aws_iam_role.scheduler.id
  policy = jsonencode({
    Version = "2012-10-17", Statement = [
      {
        Effect = "Allow", Action = "ecs:RunTask", Resource = [for t in aws_ecs_task_definition.backend : t.arn], Condition = {
          ArnLike = {
            "ecs:cluster" = [for c in aws_ecs_cluster.this : c.arn]
          }
        }
      },
      {
        Effect = "Allow", Action = "iam:PassRole", Resource = [aws_iam_role.ecs_execution.arn, aws_iam_role.ecs_task.arn]
      }
    ]
  })
}
resource "aws_scheduler_schedule" "jobs" {
  for_each            = local.environments
  name                = "${var.project}-${each.key}-jobs"
  schedule_expression = "rate(5 minutes)"
  flexible_time_window {
    mode = "OFF"
  }
  target {
    arn      = aws_ecs_cluster.this[each.key].arn
    role_arn = aws_iam_role.scheduler.arn
    ecs_parameters {
      task_definition_arn = aws_ecs_task_definition.backend[each.key].arn
      launch_type         = "FARGATE"
      task_count          = 1
      network_configuration {
        subnets          = [for i in range(2) : aws_subnet.private["${each.key}-${i}"].id]
        security_groups  = [aws_security_group.ecs[each.key].id]
        assign_public_ip = false
      }

    }
    input = jsonencode({
      containerOverrides = [{
        name = "backend", command = ["python", "manage.py", "process_notification_emails", "--once"]
      }]
    })

  }
}

resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
}
resource "aws_iam_role" "github" {
  name = "${var.project}-github-deploy"
  assume_role_policy = jsonencode({
    Version = "2012-10-17", Statement = [{
      Effect = "Allow", Principal = {
        Federated = aws_iam_openid_connect_provider.github.arn
        }, Action = "sts:AssumeRoleWithWebIdentity", Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          }, StringLike = {
          "token.actions.githubusercontent.com:sub" = ["repo:${var.github_owner}/${var.backend_repository}:*", "repo:${var.github_owner}/${var.frontend_repository}:*"]
        }
      }
    }]
  })
}
resource "aws_iam_role_policy" "github" {
  role = aws_iam_role.github.id
  policy = jsonencode({
    Version = "2012-10-17", Statement = [
      {
        Effect = "Allow", Action = ["ecr:GetAuthorizationToken"], Resource = "*"
      },
      {
        Effect = "Allow", Action = ["ecr:BatchCheckLayerAvailability", "ecr:GetDownloadUrlForLayer", "ecr:BatchGetImage", "ecr:PutImage", "ecr:InitiateLayerUpload", "ecr:UploadLayerPart", "ecr:CompleteLayerUpload"], Resource = aws_ecr_repository.backend.arn
      },
      {
        Effect = "Allow", Action = ["ecs:DescribeServices", "ecs:UpdateService"], Resource = "*"
      },
      {
        Effect = "Allow", Action = ["s3:ListBucket", "s3:PutObject", "s3:DeleteObject", "s3:GetObject"], Resource = concat([for b in aws_s3_bucket.frontend : b.arn], [for b in aws_s3_bucket.frontend : "${b.arn}/*"])
      },
      {
        Effect = "Allow", Action = "cloudfront:CreateInvalidation", Resource = [for d in aws_cloudfront_distribution.frontend : d.arn]
      }
    ]
  })
}
