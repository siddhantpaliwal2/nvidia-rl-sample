#!/usr/bin/env bash

set -euo pipefail

for command_name in aws docker; do
    if ! command -v "$command_name" >/dev/null 2>&1; then
        echo "missing required command: $command_name" >&2
        exit 1
    fi
done

NVIDIA_ECR_REGION="${NVIDIA_ECR_REGION:-us-east-1}"
NVIDIA_ECR_REGISTRY="${NVIDIA_ECR_REGISTRY:-237343249281.dkr.ecr.us-east-1.amazonaws.com}"

aws_command=(aws)
if [ -n "${NVIDIA_AWS_PROFILE:-}" ]; then
    aws_command+=(--profile "$NVIDIA_AWS_PROFILE")
fi

echo "Logging in to $NVIDIA_ECR_REGISTRY in $NVIDIA_ECR_REGION"
"${aws_command[@]}" ecr get-login-password --region "$NVIDIA_ECR_REGION" \
    | docker login --username AWS --password-stdin "$NVIDIA_ECR_REGISTRY"

# Local task alias | shared private ECR repository | immutable NVIDIA digest
images=(
    "paigo-backend-eng504-billing-base|rl-images/enterprise-backend-eng504-billing-base|sha256:10b3f96ee015d6eb6ce865d85b59a7ac84114c8f6511c67ddda4b04647587ea0"
    "paigo-backend-eng504-identity-base|rl-images/enterprise-backend-eng504-identity-base|sha256:f0d75e4f53f7cad239a120876fb3b5b90ff1acb424de0141bae46018fac81c1d"
    "paigo-backend-eng830-base|rl-images/enterprise-backend-eng830-base|sha256:9c68e01a7179b991042023076e2f2b4c3738376cfb2314ec8de4c50aca3b81a4"
    "paigo-backend-eng411-base|rl-images/enterprise-backend-eng411-base|sha256:3101b3c5acb819261de4bd3c88197f39b234db185f8fa69c4bf6273b231ef771"
    "paigo-backend-eng1167-base|rl-images/enterprise-backend-eng1167-base|sha256:b90d0e896c7613693dc33903d85cf70d6c2f54c110e1113c13afa37a4b334434"
    "champ-state-machine-champ2197-base|rl-images/enterprise-state-machine-email2197-base|sha256:a371c2ed15c81ddf473a810c5b811075f3d7b18a5ae71966248a3aae41bf0f62"
    "finbit-bank-parser-base|rl-images/enterprise-bank-parser-base|sha256:7670d9b4a0ea343cd657ef7421a79e370bea3154ecc7da5c55df4f3ca1f84f76"
    "finbit-google-cloud-storage-base|rl-images/enterprise-google-cloud-storage-base|sha256:03cddf82213e2ffa6714487eb1da82e1b85979b213e4edbd3e1b3215827ad2ac"
)

for item in "${images[@]}"; do
    IFS='|' read -r local_name repository digest <<<"$item"
    remote_reference="$NVIDIA_ECR_REGISTRY/$repository@$digest"
    echo "Pulling $local_name from $repository@$digest"
    docker pull --platform linux/amd64 "$remote_reference"
    docker tag "$remote_reference" "$local_name:v1"

    architecture=$(docker image inspect "$local_name:v1" --format '{{.Architecture}}')
    if [ "$architecture" != "amd64" ]; then
        echo "$local_name:v1 has architecture $architecture, expected amd64" >&2
        exit 1
    fi
done

echo
echo "Installed 8 sealed linux/amd64 base images:"
for item in "${images[@]}"; do
    IFS='|' read -r local_name _ _ <<<"$item"
    architecture=$(docker image inspect "$local_name:v1" --format '{{.Architecture}}')
    image_id=$(docker image inspect "$local_name:v1" --format '{{.Id}}')
    printf '  %s:v1  %s  %s\n' "$local_name" "$architecture" "$image_id"
done
