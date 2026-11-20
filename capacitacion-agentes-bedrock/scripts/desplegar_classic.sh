#!/usr/bin/env bash
# [Anexo A - Bedrock Agents Classic] Empaqueta la Lambda y despliega el stack de CloudFormation.
# Uso: ./scripts/desplegar_classic.sh <bucket-s3-artefactos> [nombre-stack] [parametros extra...]
#   ej: ./scripts/desplegar_classic.sh mi-bucket-artefactos arquitecto-documental ModoSimulacion=false \
#         M365SecretArn=arn:aws:secretsmanager:us-east-1:123456789012:secret:m365-proyectos
set -euo pipefail
cd "$(dirname "$0")/.."

BUCKET="${1:?Indique el bucket S3 para artefactos}"
STACK="${2:-arquitecto-documental}"
shift $(( $# >= 2 ? 2 : 1 ))

rm -rf build && mkdir -p build/lambda
pip install -r requirements-lambda.txt -t build/lambda \
  --platform manylinux2014_x86_64 --python-version 3.12 --only-binary=:all: --quiet
cp -r src/* build/lambda/
find build/lambda -name "__pycache__" -prune -exec rm -rf {} +

aws cloudformation package \
  --template-file infra/classic/template.yaml \
  --s3-bucket "$BUCKET" \
  --output-template-file build/empaquetado.yaml

aws cloudformation deploy \
  --template-file build/empaquetado.yaml \
  --stack-name "$STACK" \
  --capabilities CAPABILITY_IAM \
  ${@:+--parameter-overrides "$@"}

aws cloudformation describe-stacks --stack-name "$STACK" \
  --query "Stacks[0].Outputs" --output table
