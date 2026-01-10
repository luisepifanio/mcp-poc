# Install NGINX Ingress Controller for Docker Desktop
# Docker Desktop uses KIND as cluster provisioning method
# KIND provider uses hostPort to expose ports on localhost:80/443
local_resource(
    'nginx-ingress-controller',
    cmd='kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.14.1/deploy/static/provider/kind/deploy.yaml',               
    labels=['infrastructure'],
)

# Build the gateway-api Docker image
docker_build("gateway-api", './gateway-api', dockerfile="gateway-api/Dockerfile")

# Define services and their k8s manifests
services = [ "ingress", "redis-stream", "gateway-api"]
yaml_files = ["k8s/%s.yaml" % service for service in services]

# Apply k8s configurations
k8s_yaml(yaml_files)

# Configure resources
# Note: No port forwarding needed - access via Ingress at localhost/api/*
k8s_resource(
    workload="gateway-api",
    labels=['gateway-api'],
    resource_deps=['nginx-ingress-controller', 'redis-stream'],
    objects=[
        'gateway-api-configuration:configmap',
        'gateway-api-credentials:secret'
    ]
)

# Redis Stream resource
k8s_resource(
    workload="redis-stream",
    labels=['infrastructure'],
    resource_deps=['nginx-ingress-controller'],
    objects=[
        'redis-stream-configuration:configmap',
        'redis-stream-credentials:secret',
        'redis-stream-pvc:persistentvolumeclaim'
    ]
)

# Make ingress controller visible in Tilt UI
k8s_resource(
    objects=['gateway-ingress:ingress'],
    new_name='gateway-ingress',
    labels=['infrastructure'],
    resource_deps=['nginx-ingress-controller']
)