# Deployment Guide

This guide covers deployment strategies and procedures for the LLM-as-a-Judge system.

## 🚀 Deployment Overview

The LLM-as-a-Judge system can be deployed in various environments, from local development to production-scale deployments.

### Deployment Options

- **Local Development**: Direct Python execution
- **Docker**: Containerized deployment
- **Cloud Platforms**: AWS, GCP, Azure
- **Kubernetes**: Container orchestration
- **Serverless**: Function-as-a-Service deployment

## 🏠 Local Deployment

### Development Environment

```bash
# Clone repository
git clone <repository-url>
cd llm-as-a-judge

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your API keys

# Run the system
python -m src.llm_judge evaluate "Test" "Test response"
```

### Production-like Local Setup

```bash
# Install production dependencies
pip install -r requirements.txt

# Configure logging
export LOG_LEVEL=INFO
export ENABLE_AUDIT_LOGGING=true

# Run with production settings
python -m src.llm_judge evaluate "Test" "Test response"
```

## 🐳 Docker Deployment

### Dockerfile

```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY examples/ ./examples/

# Set environment variables
ENV PYTHONPATH=/app
ENV LOG_LEVEL=INFO

# Expose port (if running as web service)
EXPOSE 8000

# Default command
CMD ["python", "-m", "src.llm_judge", "--help"]
```

### Docker Compose

```yaml
version: "3.8"

services:
  llm-judge:
    build: .
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - DEFAULT_PROVIDER=anthropic
      - LOG_LEVEL=INFO
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    ports:
      - "8000:8000"
    command:
      ["python", "-m", "src.llm_judge", "evaluate", "Test", "Test response"]
```

### Building and Running

```bash
# Build Docker image
docker build -t llm-as-a-judge .

# Run container
docker run -e OPENAI_API_KEY=your-key llm-as-a-judge

# Run with Docker Compose
docker-compose up
```

## ☁️ Cloud Deployment

### AWS Deployment

#### EC2 Instance

```bash
# Launch EC2 instance
aws ec2 run-instances \
  --image-id ami-0c02fb55956c7d316 \
  --instance-type t3.medium \
  --key-name your-key \
  --security-groups your-sg

# Connect to instance
ssh -i your-key.pem ec2-user@your-instance-ip

# Install dependencies
sudo yum update -y
sudo yum install -y python3 python3-pip git
pip3 install -r requirements.txt

# Run application
python3 -m src.llm_judge evaluate "Test" "Test response"
```

#### ECS (Elastic Container Service)

```yaml
# task-definition.json
{
  "family": "llm-judge",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "executionRoleArn": "arn:aws:iam::account:role/ecsTaskExecutionRole",
  "containerDefinitions":
    [
      {
        "name": "llm-judge",
        "image": "your-account.dkr.ecr.region.amazonaws.com/llm-judge:latest",
        "portMappings": [{ "containerPort": 8000, "protocol": "tcp" }],
        "environment":
          [
            { "name": "OPENAI_API_KEY", "value": "your-openai-key" },
            { "name": "ANTHROPIC_API_KEY", "value": "your-anthropic-key" },
          ],
        "logConfiguration":
          {
            "logDriver": "awslogs",
            "options":
              {
                "awslogs-group": "/ecs/llm-judge",
                "awslogs-region": "us-west-2",
                "awslogs-stream-prefix": "ecs",
              },
          },
      },
    ],
}
```

### Google Cloud Platform

#### Cloud Run

```yaml
# cloudbuild.yaml
steps:
  - name: "gcr.io/cloud-builders/docker"
    args: ["build", "-t", "gcr.io/$PROJECT_ID/llm-judge", "."]
  - name: "gcr.io/cloud-builders/docker"
    args: ["push", "gcr.io/$PROJECT_ID/llm-judge"]
  - name: "gcr.io/cloud-builders/gcloud"
    args:
      [
        "run",
        "deploy",
        "llm-judge",
        "--image",
        "gcr.io/$PROJECT_ID/llm-judge",
        "--region",
        "us-central1",
        "--platform",
        "managed",
        "--allow-unauthenticated",
      ]
```

#### App Engine

```yaml
# app.yaml
runtime: python39

env_variables:
  OPENAI_API_KEY: "your-openai-key"
  ANTHROPIC_API_KEY: "your-anthropic-key"
  DEFAULT_PROVIDER: "anthropic"

automatic_scaling:
  min_instances: 1
  max_instances: 10
  target_cpu_utilization: 0.6
```

### Azure Deployment

#### Container Instances

```bash
# Create resource group
az group create --name llm-judge-rg --location eastus

# Create container instance
az container create \
  --resource-group llm-judge-rg \
  --name llm-judge \
  --image your-registry.azurecr.io/llm-judge:latest \
  --cpu 1 \
  --memory 1 \
  --environment-variables \
    OPENAI_API_KEY=your-openai-key \
    ANTHROPIC_API_KEY=your-anthropic-key
```

## ☸️ Kubernetes Deployment

### Deployment Manifest

```yaml
# k8s-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: llm-judge
spec:
  replicas: 3
  selector:
    matchLabels:
      app: llm-judge
  template:
    metadata:
      labels:
        app: llm-judge
    spec:
      containers:
        - name: llm-judge
          image: your-registry/llm-judge:latest
          ports:
            - containerPort: 8000
          env:
            - name: OPENAI_API_KEY
              valueFrom:
                secretKeyRef:
                  name: llm-judge-secrets
                  key: openai-api-key
            - name: ANTHROPIC_API_KEY
              valueFrom:
                secretKeyRef:
                  name: llm-judge-secrets
                  key: anthropic-api-key
          resources:
            requests:
              memory: "256Mi"
              cpu: "250m"
            limits:
              memory: "512Mi"
              cpu: "500m"
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 30
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /ready
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 5
```

### Service Manifest

```yaml
# k8s-service.yaml
apiVersion: v1
kind: Service
metadata:
  name: llm-judge-service
spec:
  selector:
    app: llm-judge
  ports:
    - protocol: TCP
      port: 80
      targetPort: 8000
  type: LoadBalancer
```

### Secrets

```yaml
# k8s-secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: llm-judge-secrets
type: Opaque
data:
  openai-api-key: <base64-encoded-key>
  anthropic-api-key: <base64-encoded-key>
```

### Deploy to Kubernetes

```bash
# Apply manifests
kubectl apply -f k8s-secrets.yaml
kubectl apply -f k8s-deployment.yaml
kubectl apply -f k8s-service.yaml

# Check deployment status
kubectl get deployments
kubectl get pods
kubectl get services
```

## 🔧 Configuration Management

### Environment Variables

```bash
# Production environment
export OPENAI_API_KEY=your-production-key
export ANTHROPIC_API_KEY=your-production-key
export DEFAULT_PROVIDER=anthropic
export LOG_LEVEL=INFO
export ENABLE_AUDIT_LOGGING=true
export REQUEST_TIMEOUT=30
export MAX_RETRIES=3
```

### Configuration Files

```json
{
  "llm_providers": {
    "openai": {
      "api_key": "your-openai-key",
      "model": "gpt-4"
    },
    "anthropic": {
      "api_key": "your-anthropic-key",
      "model": "claude-sonnet-4-20250514"
    }
  },
  "default_provider": "anthropic",
  "request_settings": {
    "timeout": 30,
    "max_retries": 3
  },
  "logging": {
    "level": "INFO",
    "enable_audit": true
  }
}
```

## 📊 Monitoring and Observability

### Health Checks

```python
# health_check.py
from src.llm_judge import LLMJudge
import asyncio

async def health_check():
    try:
        judge = LLMJudge()
        # Test basic functionality
        candidate = CandidateResponse("Test", "Test response", "test")
        result = await judge.evaluate_multi_criteria(candidate)
        await judge.close()
        return {"status": "healthy", "score": result.aggregated.overall_score}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

if __name__ == "__main__":
    result = asyncio.run(health_check())
    print(result)
```

### Logging Configuration

```python
# logging_config.py
import logging
import json

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/llm_judge.log'),
            logging.StreamHandler()
        ]
    )
```

### Metrics Collection

```python
# metrics.py
from prometheus_client import Counter, Histogram, start_http_server

# Metrics
evaluation_requests = Counter('evaluation_requests_total', 'Total evaluation requests')
evaluation_duration = Histogram('evaluation_duration_seconds', 'Evaluation duration')

def collect_metrics():
    start_http_server(8000)  # Start metrics server
```

## 🔒 Security Considerations

### API Key Management

- **Environment Variables**: Store API keys in environment variables
- **Secrets Management**: Use cloud secrets management services
- **Key Rotation**: Regularly rotate API keys
- **Access Control**: Limit API key permissions

### Network Security

- **TLS/SSL**: Use HTTPS for all communications
- **Firewall Rules**: Restrict network access
- **VPN**: Use VPN for secure access
- **Load Balancer**: Use load balancer with SSL termination

### Data Protection

- **Encryption**: Encrypt data at rest and in transit
- **PII Handling**: Implement PII detection and redaction
- **Data Retention**: Implement data retention policies
- **Backup**: Regular data backups

## 🚀 Deployment Best Practices

### Pre-deployment Checklist

- [ ] **Tests Pass**: All tests pass in CI/CD pipeline
- [ ] **Security Scan**: Security vulnerabilities addressed
- [ ] **Performance Test**: Performance requirements met
- [ ] **Configuration**: Production configuration verified
- [ ] **Monitoring**: Monitoring and alerting configured
- [ ] **Backup**: Backup and recovery procedures tested

### Deployment Strategy

1. **Blue-Green Deployment**: Zero-downtime deployments
2. **Canary Deployment**: Gradual rollout with monitoring
3. **Rolling Deployment**: Update instances gradually
4. **Feature Flags**: Control feature rollouts

### Post-deployment Validation

- [ ] **Health Checks**: All health checks pass
- [ ] **Smoke Tests**: Basic functionality verified
- [ ] **Performance**: Performance metrics within limits
- [ ] **Monitoring**: Monitoring and alerting working
- [ ] **Logs**: Logs are being generated correctly

## 📚 Related Documentation

- **[Production Deployment](production.md)** - Production-specific deployment guide
- **[Monitoring](monitoring.md)** - Monitoring and observability setup
- **[Configuration Guide](../configuration/README.md)** - System configuration
- **[API Reference](../api/README.md)** - Complete API documentation

## 🆘 Troubleshooting

### Common Deployment Issues

1. **API Key Issues**: Verify API keys are correctly set
2. **Network Issues**: Check firewall and network configuration
3. **Resource Issues**: Ensure sufficient CPU and memory
4. **Configuration Issues**: Verify configuration files and environment variables

### Debugging

```bash
# Check logs
docker logs <container-id>

# Check Kubernetes logs
kubectl logs <pod-name>

# Check system resources
kubectl top pods
kubectl top nodes
```

---

**Ready to deploy?** Check out the [Production Deployment Guide](production.md)!
