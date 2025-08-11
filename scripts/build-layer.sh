#!/bin/bash
set -e

# Build script for Lambda Coverage Layer
# This script installs dependencies and packages the layer for deployment

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LAYER_DIR="$PROJECT_ROOT/layer"
BUILD_DIR="$PROJECT_ROOT/build"
DIST_DIR="$PROJECT_ROOT/dist"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
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

# Function to check if required tools are installed
check_dependencies() {
    log_info "Checking dependencies..."
    
    if ! command -v python3 &> /dev/null; then
        log_error "python3 is required but not installed"
        exit 1
    fi
    
    if ! command -v pip3 &> /dev/null; then
        log_error "pip3 is required but not installed"
        exit 1
    fi
    
    if ! command -v zip &> /dev/null; then
        log_error "zip is required but not installed"
        exit 1
    fi
    
    log_info "All dependencies are available"
}

# Function to clean previous builds
clean_build() {
    log_info "Cleaning previous builds..."
    rm -rf "$BUILD_DIR"
    rm -rf "$DIST_DIR"
    mkdir -p "$BUILD_DIR"
    mkdir -p "$DIST_DIR"
}

# Function to install layer dependencies
install_dependencies() {
    log_info "Installing layer dependencies..."
    
    # Create temporary directory for installing dependencies
    TEMP_PYTHON_DIR="$BUILD_DIR/python"
    mkdir -p "$TEMP_PYTHON_DIR"
    
    # Install dependencies from requirements.txt
    if [ -f "$LAYER_DIR/requirements.txt" ]; then
        log_info "Installing dependencies from requirements.txt..."
        pip3 install -r "$LAYER_DIR/requirements.txt" -t "$TEMP_PYTHON_DIR" --no-deps
    else
        log_warn "No requirements.txt found in layer directory"
    fi
    
    # Copy coverage_wrapper package
    log_info "Copying coverage_wrapper package..."
    cp -r "$LAYER_DIR/python/coverage_wrapper" "$TEMP_PYTHON_DIR/"
    
    log_info "Dependencies installed successfully"
}

# Function to validate layer structure
validate_layer() {
    log_info "Validating layer structure..."
    
    PYTHON_DIR="$BUILD_DIR/python"
    
    # Check if python directory exists
    if [ ! -d "$PYTHON_DIR" ]; then
        log_error "Python directory not found in build"
        exit 1
    fi
    
    # Check if coverage_wrapper package exists
    if [ ! -d "$PYTHON_DIR/coverage_wrapper" ]; then
        log_error "coverage_wrapper package not found"
        exit 1
    fi
    
    # Check if required modules exist
    required_modules=("__init__.py" "wrapper.py" "s3_uploader.py" "health_check.py" "combiner.py")
    for module in "${required_modules[@]}"; do
        if [ ! -f "$PYTHON_DIR/coverage_wrapper/$module" ]; then
            log_error "Required module $module not found"
            exit 1
        fi
    done
    
    log_info "Layer structure validation passed"
}

# Function to create layer package
create_package() {
    log_info "Creating layer package..."
    
    cd "$BUILD_DIR"
    
    # Get version from version file or use default
    VERSION=$(cat "$PROJECT_ROOT/VERSION" 2>/dev/null || echo "1.0.0")
    PACKAGE_NAME="lambda-coverage-layer-${VERSION}.zip"
    
    # Create zip package
    zip -r "$DIST_DIR/$PACKAGE_NAME" python/ -x "**/__pycache__/*" "**/*.pyc"
    
    # Create latest symlink
    cd "$DIST_DIR"
    ln -sf "$PACKAGE_NAME" "lambda-coverage-layer-latest.zip"
    
    log_info "Package created: $DIST_DIR/$PACKAGE_NAME"
    
    # Display package info
    PACKAGE_SIZE=$(du -h "$DIST_DIR/$PACKAGE_NAME" | cut -f1)
    log_info "Package size: $PACKAGE_SIZE"
}

# Function to run tests on the built layer
test_layer() {
    log_info "Running layer tests..."
    
    # Set PYTHONPATH to include the built layer
    export PYTHONPATH="$BUILD_DIR/python:$PYTHONPATH"
    
    # Run basic import tests
    python3 -c "
import sys
sys.path.insert(0, '$BUILD_DIR/python')

try:
    import coverage_wrapper
    print('✓ coverage_wrapper import successful')
    
    from coverage_wrapper import coverage_handler
    print('✓ coverage_handler import successful')
    
    from coverage_wrapper.health_check import health_check_handler
    print('✓ health_check_handler import successful')
    
    from coverage_wrapper.combiner import combine_coverage_files
    print('✓ combine_coverage_files import successful')
    
    print('All imports successful!')
except ImportError as e:
    print(f'Import error: {e}')
    sys.exit(1)
"
    
    log_info "Layer tests passed"
}

# Main execution
main() {
    log_info "Starting Lambda Coverage Layer build process..."
    
    check_dependencies
    clean_build
    install_dependencies
    validate_layer
    create_package
    test_layer
    
    log_info "Build completed successfully!"
    log_info "Layer package available at: $DIST_DIR/"
}

# Run main function
main "$@"