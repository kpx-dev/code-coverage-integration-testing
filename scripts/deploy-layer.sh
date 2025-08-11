#!/bin/bash
set -e

# Deployment script for Lambda Coverage Layer
# Supports multi-region deployment with version management

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DIST_DIR="$PROJECT_ROOT/dist"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_debug() {
    echo -e "${BLUE}[DEBUG]${NC} $1"
}

# Default configuration
DEFAULT_REGIONS=("us-east-1" "us-west-2" "eu-west-1")
LAYER_NAME="lambda-coverage-layer"

# Function to show usage
show_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Deploy Lambda Coverage Layer to AWS regions

OPTIONS:
    -r, --regions REGIONS    Comma-separated list of AWS regions (default: us-east-1,us-west-2,eu-west-1)
    -v, --version VERSION    Layer version (default: from VERSION file or 1.0.0)
    -n, --name NAME          Layer name (default: lambda-coverage-layer)
    -p, --profile PROFILE    AWS profile to use
    -d, --dry-run           Show what would be deployed without actually deploying
    -h, --help              Show this help message

EXAMPLES:
    $0                                          # Deploy to default regions
    $0 -r us-east-1,eu-west-1                 # Deploy to specific regions
    $0 -v 2.0.0 -p production                 # Deploy specific version with AWS profile
    $0 --dry-run                               # Preview deployment without executing

EOF
}

# Function to parse command line arguments
parse_args() {
    REGIONS_ARG=""
    VERSION_ARG=""
    PROFILE_ARG=""
    DRY_RUN=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            -r|--regions)
                REGIONS_ARG="$2"
                shift 2
                ;;
            -v|--version)
                VERSION_ARG="$2"
                shift 2
                ;;
            -n|--name)
                LAYER_NAME="$2"
                shift 2
                ;;
            -p|--profile)
                PROFILE_ARG="$2"
                shift 2
                ;;
            -d|--dry-run)
                DRY_RUN=true
                shift
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done
    
    # Set regions
    if [ -n "$REGIONS_ARG" ]; then
        IFS=',' read -ra REGIONS <<< "$REGIONS_ARG"
    else
        REGIONS=("${DEFAULT_REGIONS[@]}")
    fi
    
    # Set version
    if [ -n "$VERSION_ARG" ]; then
        VERSION="$VERSION_ARG"
    else
        VERSION=$(cat "$PROJECT_ROOT/VERSION" 2>/dev/null || echo "1.0.0")
    fi
    
    # Set AWS profile if provided
    if [ -n "$PROFILE_ARG" ]; then
        export AWS_PROFILE="$PROFILE_ARG"
        log_info "Using AWS profile: $PROFILE_ARG"
    fi
}

# Function to check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if AWS CLI is installed
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI is required but not installed"
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS credentials not configured or invalid"
        exit 1
    fi
    
    # Check if layer package exists
    PACKAGE_FILE="$DIST_DIR/lambda-coverage-layer-${VERSION}.zip"
    if [ ! -f "$PACKAGE_FILE" ]; then
        log_error "Layer package not found: $PACKAGE_FILE"
        log_info "Run './scripts/build-layer.sh' first to build the layer"
        exit 1
    fi
    
    log_info "Prerequisites check passed"
}

# Function to deploy layer to a specific region
deploy_to_region() {
    local region=$1
    local package_file="$DIST_DIR/lambda-coverage-layer-${VERSION}.zip"
    
    log_info "Deploying to region: $region"
    
    if [ "$DRY_RUN" = true ]; then
        log_debug "DRY RUN: Would deploy $package_file to $region as $LAYER_NAME"
        return 0
    fi
    
    # Deploy the layer
    local layer_arn
    layer_arn=$(aws lambda publish-layer-version \
        --region "$region" \
        --layer-name "$LAYER_NAME" \
        --description "Lambda layer for automated code coverage tracking v${VERSION}" \
        --zip-file "fileb://$package_file" \
        --compatible-runtimes python3.8 python3.9 python3.10 python3.11 python3.12 \
        --query 'LayerArn' \
        --output text)
    
    if [ $? -eq 0 ]; then
        log_info "✓ Successfully deployed to $region"
        log_info "  Layer ARN: $layer_arn"
        
        # Store deployment info
        echo "$region:$layer_arn" >> "$DIST_DIR/deployment-${VERSION}.txt"
    else
        log_error "✗ Failed to deploy to $region"
        return 1
    fi
}

# Function to validate deployment
validate_deployment() {
    local region=$1
    
    log_info "Validating deployment in region: $region"
    
    if [ "$DRY_RUN" = true ]; then
        log_debug "DRY RUN: Would validate deployment in $region"
        return 0
    fi
    
    # Get latest layer version
    local layer_info
    layer_info=$(aws lambda get-layer-version-by-arn \
        --region "$region" \
        --arn "$(aws lambda list-layer-versions \
            --region "$region" \
            --layer-name "$LAYER_NAME" \
            --query 'LayerVersions[0].LayerVersionArn' \
            --output text)" \
        2>/dev/null)
    
    if [ $? -eq 0 ]; then
        log_info "✓ Layer validation passed for $region"
        return 0
    else
        log_warn "⚠ Layer validation failed for $region"
        return 1
    fi
}

# Function to create deployment summary
create_deployment_summary() {
    local summary_file="$DIST_DIR/deployment-summary-${VERSION}.json"
    
    if [ "$DRY_RUN" = true ]; then
        log_debug "DRY RUN: Would create deployment summary at $summary_file"
        return 0
    fi
    
    log_info "Creating deployment summary..."
    
    cat > "$summary_file" << EOF
{
  "version": "$VERSION",
  "layer_name": "$LAYER_NAME",
  "deployment_date": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "regions": [
$(printf '    "%s"' "${REGIONS[@]}" | paste -sd ',' -)
  ],
  "package_file": "lambda-coverage-layer-${VERSION}.zip",
  "aws_profile": "${AWS_PROFILE:-default}"
}
EOF
    
    log_info "Deployment summary created: $summary_file"
}

# Main deployment function
main() {
    log_info "Starting Lambda Coverage Layer deployment..."
    log_info "Version: $VERSION"
    log_info "Regions: ${REGIONS[*]}"
    
    if [ "$DRY_RUN" = true ]; then
        log_warn "DRY RUN MODE - No actual deployment will occur"
    fi
    
    check_prerequisites
    
    # Initialize deployment log
    if [ "$DRY_RUN" = false ]; then
        echo "# Deployment Log for Version $VERSION" > "$DIST_DIR/deployment-${VERSION}.txt"
        echo "# Date: $(date)" >> "$DIST_DIR/deployment-${VERSION}.txt"
        echo "" >> "$DIST_DIR/deployment-${VERSION}.txt"
    fi
    
    # Deploy to each region
    local failed_regions=()
    for region in "${REGIONS[@]}"; do
        if ! deploy_to_region "$region"; then
            failed_regions+=("$region")
        fi
        
        # Add delay between deployments to avoid rate limiting
        if [ "$DRY_RUN" = false ]; then
            sleep 2
        fi
    done
    
    # Validate deployments
    log_info "Validating deployments..."
    for region in "${REGIONS[@]}"; do
        validate_deployment "$region"
    done
    
    # Create deployment summary
    create_deployment_summary
    
    # Report results
    if [ ${#failed_regions[@]} -eq 0 ]; then
        log_info "✓ Deployment completed successfully to all regions!"
    else
        log_warn "⚠ Deployment completed with failures in regions: ${failed_regions[*]}"
        exit 1
    fi
    
    if [ "$DRY_RUN" = false ]; then
        log_info "Deployment artifacts:"
        log_info "  - Package: $DIST_DIR/lambda-coverage-layer-${VERSION}.zip"
        log_info "  - Log: $DIST_DIR/deployment-${VERSION}.txt"
        log_info "  - Summary: $DIST_DIR/deployment-summary-${VERSION}.json"
    fi
}

# Parse arguments and run main function
parse_args "$@"
main