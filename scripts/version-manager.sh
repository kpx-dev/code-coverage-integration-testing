#!/bin/bash
set -e

# Version management script for Lambda Coverage Layer
# Implements semantic versioning for layer releases

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VERSION_FILE="$PROJECT_ROOT/VERSION"

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
Usage: $0 COMMAND [OPTIONS]

Semantic version management for Lambda Coverage Layer

COMMANDS:
    current                 Show current version
    bump LEVEL             Bump version (major|minor|patch)
    set VERSION            Set specific version
    validate VERSION       Validate version format
    changelog              Generate changelog for current version

OPTIONS:
    -d, --dry-run          Show what would be changed without making changes
    -h, --help             Show this help message

EXAMPLES:
    $0 current                    # Show current version
    $0 bump patch                 # Bump patch version (1.0.0 -> 1.0.1)
    $0 bump minor                 # Bump minor version (1.0.1 -> 1.1.0)
    $0 bump major                 # Bump major version (1.1.0 -> 2.0.0)
    $0 set 2.1.0                 # Set specific version
    $0 validate 1.2.3            # Validate version format

EOF
}

# Function to get current version
get_current_version() {
    if [ -f "$VERSION_FILE" ]; then
        cat "$VERSION_FILE"
    else
        echo "1.0.0"
    fi
}

# Function to validate semantic version format
validate_version() {
    local version=$1
    
    if [[ ! $version =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        log_error "Invalid version format: $version"
        log_error "Expected format: MAJOR.MINOR.PATCH (e.g., 1.2.3)"
        return 1
    fi
    
    return 0
}

# Function to parse version components
parse_version() {
    local version=$1
    IFS='.' read -r MAJOR MINOR PATCH <<< "$version"
}

# Function to bump version
bump_version() {
    local level=$1
    local current_version=$(get_current_version)
    local dry_run=${2:-false}
    
    parse_version "$current_version"
    
    case $level in
        major)
            MAJOR=$((MAJOR + 1))
            MINOR=0
            PATCH=0
            ;;
        minor)
            MINOR=$((MINOR + 1))
            PATCH=0
            ;;
        patch)
            PATCH=$((PATCH + 1))
            ;;
        *)
            log_error "Invalid bump level: $level"
            log_error "Valid levels: major, minor, patch"
            return 1
            ;;
    esac
    
    local new_version="${MAJOR}.${MINOR}.${PATCH}"
    
    log_info "Version bump: $current_version -> $new_version"
    
    if [ "$dry_run" = true ]; then
        log_debug "DRY RUN: Would update version to $new_version"
        return 0
    fi
    
    echo "$new_version" > "$VERSION_FILE"
    log_info "Version updated to $new_version"
    
    # Update version in other files if they exist
    update_version_references "$new_version"
}

# Function to set specific version
set_version() {
    local version=$1
    local dry_run=${2:-false}
    
    if ! validate_version "$version"; then
        return 1
    fi
    
    local current_version=$(get_current_version)
    
    log_info "Version change: $current_version -> $version"
    
    if [ "$dry_run" = true ]; then
        log_debug "DRY RUN: Would set version to $version"
        return 0
    fi
    
    echo "$version" > "$VERSION_FILE"
    log_info "Version set to $version"
    
    # Update version in other files if they exist
    update_version_references "$version"
}

# Function to update version references in other files
update_version_references() {
    local version=$1
    
    # Update CDK stack if it exists
    local cdk_stack="$PROJECT_ROOT/cdk/lambda_coverage_layer_stack.py"
    if [ -f "$cdk_stack" ]; then
        # This is a placeholder - actual implementation would depend on how version is referenced
        log_debug "Would update version reference in CDK stack"
    fi
    
    # Update package.json if it exists (for CDK projects)
    local package_json="$PROJECT_ROOT/package.json"
    if [ -f "$package_json" ]; then
        log_debug "Would update version in package.json"
    fi
    
    # Update setup.py if it exists
    local setup_py="$PROJECT_ROOT/setup.py"
    if [ -f "$setup_py" ]; then
        log_debug "Would update version in setup.py"
    fi
}

# Function to generate changelog
generate_changelog() {
    local version=$(get_current_version)
    local changelog_file="$PROJECT_ROOT/CHANGELOG.md"
    
    log_info "Generating changelog for version $version"
    
    # Create changelog if it doesn't exist
    if [ ! -f "$changelog_file" ]; then
        cat > "$changelog_file" << EOF
# Changelog

All notable changes to the Lambda Coverage Layer will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

EOF
    fi
    
    # Add entry for current version if not already present
    if ! grep -q "## \[$version\]" "$changelog_file"; then
        local date=$(date +%Y-%m-%d)
        local temp_file=$(mktemp)
        
        # Insert new version entry after the header
        awk -v version="$version" -v date="$date" '
        /^# Changelog/ {
            print $0
            print ""
            print "All notable changes to the Lambda Coverage Layer will be documented in this file."
            print ""
            print "The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),"
            print "and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)."
            print ""
            print "## [" version "] - " date
            print ""
            print "### Added"
            print "- Initial release of Lambda Coverage Layer"
            print ""
            print "### Changed"
            print ""
            print "### Fixed"
            print ""
            next
        }
        { print }
        ' "$changelog_file" > "$temp_file"
        
        mv "$temp_file" "$changelog_file"
        log_info "Changelog updated for version $version"
    else
        log_info "Changelog entry for version $version already exists"
    fi
}

# Function to show current version
show_current_version() {
    local version=$(get_current_version)
    echo "$version"
}

# Main function
main() {
    local command=$1
    local dry_run=false
    
    # Parse global options
    while [[ $# -gt 0 ]]; do
        case $1 in
            -d|--dry-run)
                dry_run=true
                shift
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            *)
                break
                ;;
        esac
    done
    
    # Re-parse command after options
    command=$1
    
    case $command in
        current)
            show_current_version
            ;;
        bump)
            if [ -z "$2" ]; then
                log_error "Bump level required (major|minor|patch)"
                show_usage
                exit 1
            fi
            bump_version "$2" "$dry_run"
            ;;
        set)
            if [ -z "$2" ]; then
                log_error "Version required"
                show_usage
                exit 1
            fi
            set_version "$2" "$dry_run"
            ;;
        validate)
            if [ -z "$2" ]; then
                log_error "Version required"
                show_usage
                exit 1
            fi
            if validate_version "$2"; then
                log_info "Version $2 is valid"
            fi
            ;;
        changelog)
            generate_changelog
            ;;
        *)
            log_error "Unknown command: $command"
            show_usage
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"