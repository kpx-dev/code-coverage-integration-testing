#!/bin/bash
set -e

# Validation script for Lambda Coverage Layer package integrity
# Performs comprehensive checks on the built layer package

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DIST_DIR="$PROJECT_ROOT/dist"
BUILD_DIR="$PROJECT_ROOT/build"

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

# Function to show usage
show_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Validate Lambda Coverage Layer package integrity

OPTIONS:
    -v, --version VERSION    Layer version to validate (default: from VERSION file or 1.0.0)
    -p, --package PACKAGE    Specific package file to validate
    -d, --detailed          Show detailed validation output
    -h, --help              Show this help message

EXAMPLES:
    $0                      # Validate latest version
    $0 -v 2.0.0            # Validate specific version
    $0 -p /path/to/layer.zip # Validate specific package file

EOF
}

# Function to parse command line arguments
parse_args() {
    VERSION_ARG=""
    PACKAGE_ARG=""
    DETAILED=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            -v|--version)
                VERSION_ARG="$2"
                shift 2
                ;;
            -p|--package)
                PACKAGE_ARG="$2"
                shift 2
                ;;
            -d|--detailed)
                DETAILED=true
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
    
    # Set version
    if [ -n "$VERSION_ARG" ]; then
        VERSION="$VERSION_ARG"
    else
        VERSION=$(cat "$PROJECT_ROOT/VERSION" 2>/dev/null || echo "1.0.0")
    fi
    
    # Set package file
    if [ -n "$PACKAGE_ARG" ]; then
        PACKAGE_FILE="$PACKAGE_ARG"
    else
        PACKAGE_FILE="$DIST_DIR/lambda-coverage-layer-${VERSION}.zip"
    fi
}

# Function to validate package exists
validate_package_exists() {
    log_info "Validating package existence..."
    
    if [ ! -f "$PACKAGE_FILE" ]; then
        log_error "Package file not found: $PACKAGE_FILE"
        return 1
    fi
    
    log_info "✓ Package file exists: $PACKAGE_FILE"
    
    # Show package size
    local size=$(du -h "$PACKAGE_FILE" | cut -f1)
    log_info "  Package size: $size"
    
    return 0
}

# Function to validate package structure
validate_package_structure() {
    log_info "Validating package structure..."
    
    # Create temporary directory for extraction
    local temp_dir=$(mktemp -d)
    trap "rm -rf $temp_dir" EXIT
    
    # Extract package
    if ! unzip -q "$PACKAGE_FILE" -d "$temp_dir"; then
        log_error "Failed to extract package"
        return 1
    fi
    
    # Check for python directory
    if [ ! -d "$temp_dir/python" ]; then
        log_error "Missing python/ directory in package"
        return 1
    fi
    
    log_info "✓ Package structure is valid"
    
    # Check coverage_wrapper package
    if [ ! -d "$temp_dir/python/coverage_wrapper" ]; then
        log_error "Missing coverage_wrapper package"
        return 1
    fi
    
    log_info "✓ coverage_wrapper package found"
    
    # Validate required modules
    local required_modules=("__init__.py" "wrapper.py" "s3_uploader.py" "health_check.py" "combiner.py" "models.py" "error_handling.py" "logging_utils.py")
    local missing_modules=()
    
    for module in "${required_modules[@]}"; do
        if [ ! -f "$temp_dir/python/coverage_wrapper/$module" ]; then
            missing_modules+=("$module")
        fi
    done
    
    if [ ${#missing_modules[@]} -gt 0 ]; then
        log_error "Missing required modules: ${missing_modules[*]}"
        return 1
    fi
    
    log_info "✓ All required modules present"
    
    # Show detailed structure if requested
    if [ "$DETAILED" = true ]; then
        log_debug "Package contents:"
        find "$temp_dir" -type f | sort | sed 's|^'$temp_dir'/|  |'
    fi
    
    return 0
}

# Function to validate Python imports
validate_python_imports() {
    log_info "Validating Python imports..."
    
    # Create temporary directory for extraction
    local temp_dir=$(mktemp -d)
    trap "rm -rf $temp_dir" EXIT
    
    # Extract package
    unzip -q "$PACKAGE_FILE" -d "$temp_dir"
    
    # Test imports
    local python_path="$temp_dir/python"
    
    python3 -c "
import sys
import os
sys.path.insert(0, '$python_path')

errors = []

# Test basic imports
try:
    import coverage_wrapper
    print('✓ coverage_wrapper import successful')
except ImportError as e:
    errors.append(f'coverage_wrapper: {e}')

try:
    from coverage_wrapper import coverage_handler
    print('✓ coverage_handler import successful')
except ImportError as e:
    errors.append(f'coverage_handler: {e}')

try:
    from coverage_wrapper.health_check import health_check_handler
    print('✓ health_check_handler import successful')
except ImportError as e:
    errors.append(f'health_check_handler: {e}')

try:
    from coverage_wrapper.combiner import combine_coverage_files
    print('✓ combine_coverage_files import successful')
except ImportError as e:
    errors.append(f'combine_coverage_files: {e}')

try:
    from coverage_wrapper.s3_uploader import upload_coverage_file
    print('✓ upload_coverage_file import successful')
except ImportError as e:
    errors.append(f'upload_coverage_file: {e}')

try:
    from coverage_wrapper.models import CoverageConfig
    print('✓ CoverageConfig import successful')
except ImportError as e:
    errors.append(f'CoverageConfig: {e}')

if errors:
    print('Import errors:')
    for error in errors:
        print(f'  ✗ {error}')
    sys.exit(1)
else:
    print('✓ All imports successful')
"
    
    if [ $? -eq 0 ]; then
        log_info "✓ Python import validation passed"
        return 0
    else
        log_error "✗ Python import validation failed"
        return 1
    fi
}

# Function to validate dependencies
validate_dependencies() {
    log_info "Validating dependencies..."
    
    # Create temporary directory for extraction
    local temp_dir=$(mktemp -d)
    trap "rm -rf $temp_dir" EXIT
    
    # Extract package
    unzip -q "$PACKAGE_FILE" -d "$temp_dir"
    
    # Check for coverage package
    if [ ! -d "$temp_dir/python/coverage" ]; then
        log_warn "Coverage package not found in layer (may be installed separately)"
    else
        log_info "✓ Coverage package found in layer"
    fi
    
    # Check for boto3 (should not be in layer as it's provided by Lambda runtime)
    if [ -d "$temp_dir/python/boto3" ]; then
        log_warn "boto3 found in layer (not recommended - use Lambda runtime version)"
    else
        log_info "✓ boto3 not in layer (using Lambda runtime version)"
    fi
    
    return 0
}

# Function to validate file permissions
validate_file_permissions() {
    log_info "Validating file permissions..."
    
    # Create temporary directory for extraction
    local temp_dir=$(mktemp -d)
    trap "rm -rf $temp_dir" EXIT
    
    # Extract package
    unzip -q "$PACKAGE_FILE" -d "$temp_dir"
    
    # Check for executable files (should not be present)
    local executable_files=$(find "$temp_dir" -type f -executable | wc -l)
    
    if [ "$executable_files" -gt 0 ]; then
        log_warn "Found $executable_files executable files in package"
        if [ "$DETAILED" = true ]; then
            find "$temp_dir" -type f -executable | sed 's|^'$temp_dir'/|  |'
        fi
    else
        log_info "✓ No unexpected executable files found"
    fi
    
    return 0
}

# Function to validate package size
validate_package_size() {
    log_info "Validating package size..."
    
    local size_bytes=$(stat -f%z "$PACKAGE_FILE" 2>/dev/null || stat -c%s "$PACKAGE_FILE" 2>/dev/null)
    local size_mb=$((size_bytes / 1024 / 1024))
    
    # AWS Lambda layer size limit is 250MB uncompressed
    if [ "$size_mb" -gt 200 ]; then
        log_warn "Package size is large: ${size_mb}MB (AWS limit is 250MB uncompressed)"
    else
        log_info "✓ Package size is acceptable: ${size_mb}MB"
    fi
    
    return 0
}

# Function to run all validations
run_all_validations() {
    local validation_count=0
    local passed_count=0
    
    log_info "Starting comprehensive layer validation..."
    log_info "Package: $PACKAGE_FILE"
    log_info "Version: $VERSION"
    echo ""
    
    # Run validations
    local validations=(
        "validate_package_exists"
        "validate_package_structure" 
        "validate_python_imports"
        "validate_dependencies"
        "validate_file_permissions"
        "validate_package_size"
    )
    
    for validation in "${validations[@]}"; do
        validation_count=$((validation_count + 1))
        if $validation; then
            passed_count=$((passed_count + 1))
        fi
        echo ""
    done
    
    # Summary
    log_info "Validation Summary:"
    log_info "  Total validations: $validation_count"
    log_info "  Passed: $passed_count"
    log_info "  Failed: $((validation_count - passed_count))"
    
    if [ "$passed_count" -eq "$validation_count" ]; then
        log_info "✓ All validations passed! Layer package is ready for deployment."
        return 0
    else
        log_error "✗ Some validations failed. Please review and fix issues before deployment."
        return 1
    fi
}

# Main function
main() {
    run_all_validations
}

# Parse arguments and run main function
parse_args "$@"
main