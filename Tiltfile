# Install NGINX Ingress Controller for Docker Desktop
# This is required for Ingress resources to work
local_resource(
    'nginx-ingress-controller',
    cmd='kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.10.0/deploy/static/provider/cloud/deploy.yaml',
    labels=['infrastructure'],
)

# Build the gateway-api Docker image
docker_build("gateway-api", './gateway-api', dockerfile="gateway-api/Dockerfile")

# Define services and their k8s manifests
services = ["gateway-api", "ingress"]
yaml_files = ["k8s/%s.yaml" % service for service in services]

# Apply k8s configurations
k8s_yaml(yaml_files)

# Configure resources
k8s_resource(
    workload="gateway-api", 
    port_forwards="8000:80",
    resource_deps=['nginx-ingress-controller']
)

# Make ingress controller visible in Tilt UI
k8s_resource(
    objects=['gateway-ingress:ingress'],
    new_name='gateway-ingress',
    resource_deps=['nginx-ingress-controller']
)