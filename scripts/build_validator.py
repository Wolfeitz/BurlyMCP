#!/usr/bin/env python3
"""
Package build validation script for Burly MCP

This script validates package builds, tests installations, and ensures
distribution readiness before publishing to PyPI or Docker registries.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class BuildValidator:
    """Validates package builds and distribution artifacts."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.dist_dir = project_root / "dist"
        self.build_dir = project_root / "build"
        
    def clean_build_artifacts(self) -> None:
        """Clean existing build artifacts."""
        print("🧹 Cleaning build artifacts...")
        
        for directory in [self.dist_dir, self.build_dir]:
            if directory.exists():
                shutil.rmtree(directory)
                print(f"  Removed {directory}")
        
        # Clean egg-info directories
        for egg_info in self.project_root.glob("*.egg-info"):
            if egg_info.is_dir():
                shutil.rmtree(egg_info)
                print(f"  Removed {egg_info}")
        
        print("✅ Build artifacts cleaned")
    
    def build_package(self) -> Tuple[bool, str]:
        """Build the Python package using build."""
        print("📦 Building Python package...")
        
        try:
            # Install build dependencies
            subprocess.run([
                sys.executable, "-m", "pip", "install", "--upgrade", 
                "pip", "setuptools", "wheel", "build", "twine"
            ], check=True, capture_output=True)
            
            # Build the package
            result = subprocess.run([
                sys.executable, "-m", "build"
            ], cwd=self.project_root, capture_output=True, text=True, check=True)
            
            print("✅ Package built successfully")
            return True, result.stdout
        
        except subprocess.CalledProcessError as e:
            error_msg = f"Build failed: {e.stderr}"
            print(f"❌ {error_msg}")
            return False, error_msg
    
    def validate_package_metadata(self) -> Tuple[bool, List[str]]:
        """Validate package metadata and structure."""
        print("🔍 Validating package metadata...")
        
        issues = []
        
        # Check if dist directory exists and has files
        if not self.dist_dir.exists():
            issues.append("dist/ directory not found")
            return False, issues
        
        # Check for wheel and source distribution
        wheel_files = list(self.dist_dir.glob("*.whl"))
        sdist_files = list(self.dist_dir.glob("*.tar.gz"))
        
        if not wheel_files:
            issues.append("No wheel (.whl) file found in dist/")
        
        if not sdist_files:
            issues.append("No source distribution (.tar.gz) file found in dist/")
        
        # Validate with twine
        try:
            result = subprocess.run([
                sys.executable, "-m", "twine", "check", "dist/*"
            ], cwd=self.project_root, capture_output=True, text=True, check=True)
            
            print("✅ Package metadata validation passed")
        
        except subprocess.CalledProcessError as e:
            issues.append(f"Twine validation failed: {e.stderr}")
        
        return len(issues) == 0, issues
    
    def test_package_installation(self) -> Tuple[bool, str]:
        """Test package installation in a clean environment."""
        print("🧪 Testing package installation...")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            venv_path = Path(temp_dir) / "test_venv"
            
            try:
                # Create virtual environment
                venv.create(venv_path, with_pip=True)
                
                # Get paths for the virtual environment
                if sys.platform == "win32":
                    venv_python = venv_path / "Scripts" / "python.exe"
                    venv_pip = venv_path / "Scripts" / "pip.exe"
                else:
                    venv_python = venv_path / "bin" / "python"
                    venv_pip = venv_path / "bin" / "pip"
                
                # Upgrade pip in the virtual environment
                subprocess.run([
                    str(venv_pip), "install", "--upgrade", "pip"
                ], check=True, capture_output=True)
                
                # Install the package from wheel
                wheel_files = list(self.dist_dir.glob("*.whl"))
                if not wheel_files:
                    return False, "No wheel file found for testing"
                
                wheel_file = wheel_files[0]
                subprocess.run([
                    str(venv_pip), "install", str(wheel_file)
                ], check=True, capture_output=True)
                
                # Test import and version
                test_script = '''
import burly_mcp
print(f"Package version: {burly_mcp.__version__}")
print(f"Package author: {burly_mcp.__author__}")
print("✅ Package import successful")
'''
                
                result = subprocess.run([
                    str(venv_python), "-c", test_script
                ], capture_output=True, text=True, check=True)
                
                print("✅ Package installation test passed")
                return True, result.stdout
            
            except subprocess.CalledProcessError as e:
                error_msg = f"Installation test failed: {e.stderr}"
                print(f"❌ {error_msg}")
                return False, error_msg
    
    def test_console_scripts(self) -> Tuple[bool, str]:
        """Test console script entry points."""
        print("🔧 Testing console scripts...")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            venv_path = Path(temp_dir) / "test_venv"
            
            try:
                # Create virtual environment and install package
                venv.create(venv_path, with_pip=True)
                
                if sys.platform == "win32":
                    venv_python = venv_path / "Scripts" / "python.exe"
                    venv_pip = venv_path / "Scripts" / "pip.exe"
                    script_path = venv_path / "Scripts" / "burly-mingo-mcp.exe"
                else:
                    venv_python = venv_path / "bin" / "python"
                    venv_pip = venv_path / "bin" / "pip"
                    script_path = venv_path / "bin" / "burly-mingo-mcp"
                
                # Install package
                wheel_files = list(self.dist_dir.glob("*.whl"))
                if not wheel_files:
                    return False, "No wheel file found for testing"
                
                subprocess.run([
                    str(venv_pip), "install", str(wheel_files[0])
                ], check=True, capture_output=True)
                
                # Test console script
                if not script_path.exists():
                    return False, f"Console script not found: {script_path}"
                
                # Test script execution (with --help to avoid hanging)
                result = subprocess.run([
                    str(script_path), "--help"
                ], capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    print("✅ Console script test passed")
                    return True, "Console script works correctly"
                else:
                    return False, f"Console script failed: {result.stderr}"
            
            except subprocess.CalledProcessError as e:
                return False, f"Console script test failed: {e.stderr}"
            except subprocess.TimeoutExpired:
                return False, "Console script test timed out"
    
    def validate_docker_build(self) -> Tuple[bool, str]:
        """Validate Docker build process."""
        print("🐳 Validating Docker build...")
        
        dockerfile_path = self.project_root / "Dockerfile.runtime"
        if not dockerfile_path.exists():
            return False, "Dockerfile.runtime not found"
        
        try:
            # Build Docker image
            image_tag = "burly-mcp:build-test"
            result = subprocess.run([
                "docker", "build", "-t", image_tag, "."
            ], cwd=self.project_root, capture_output=True, text=True, check=True)
            
            # Test running the container
            test_result = subprocess.run([
                "docker", "run", "--rm", image_tag, "--help"
            ], capture_output=True, text=True, timeout=30)
            
            # Clean up the test image
            subprocess.run([
                "docker", "rmi", image_tag
            ], capture_output=True)
            
            if test_result.returncode == 0:
                print("✅ Docker build validation passed")
                return True, "Docker image builds and runs correctly"
            else:
                return False, f"Docker container test failed: {test_result.stderr}"
        
        except subprocess.CalledProcessError as e:
            return False, f"Docker build failed: {e.stderr}"
        except subprocess.TimeoutExpired:
            return False, "Docker container test timed out"
        except FileNotFoundError:
            return False, "Docker not available for testing"
    
    def generate_build_report(self, results: Dict[str, Tuple[bool, str]]) -> str:
        """Generate a comprehensive build validation report."""
        report_lines = [
            "# Build Validation Report",
            f"Generated at: {subprocess.run(['date'], capture_output=True, text=True).stdout.strip()}",
            "",
            "## Summary",
            ""
        ]
        
        total_checks = len(results)
        passed_checks = sum(1 for success, _ in results.values() if success)
        
        report_lines.append(f"**Status**: {'✅ PASSED' if passed_checks == total_checks else '❌ FAILED'}")
        report_lines.append(f"**Checks**: {passed_checks}/{total_checks} passed")
        report_lines.append("")
        
        # Detailed results
        report_lines.append("## Detailed Results")
        report_lines.append("")
        
        for check_name, (success, message) in results.items():
            status = "✅ PASS" if success else "❌ FAIL"
            report_lines.append(f"### {check_name}")
            report_lines.append(f"**Status**: {status}")
            report_lines.append(f"**Details**: {message}")
            report_lines.append("")
        
        # Artifacts information
        if self.dist_dir.exists():
            report_lines.append("## Build Artifacts")
            report_lines.append("")
            
            for artifact in self.dist_dir.iterdir():
                if artifact.is_file():
                    size = artifact.stat().st_size
                    size_mb = size / (1024 * 1024)
                    report_lines.append(f"- `{artifact.name}` ({size_mb:.2f} MB)")
            
            report_lines.append("")
        
        return "\n".join(report_lines)
    
    def run_full_validation(self) -> bool:
        """Run complete build validation pipeline."""
        print("🚀 Starting full build validation...")
        print("=" * 50)
        
        results = {}
        
        # Clean and build
        self.clean_build_artifacts()
        success, message = self.build_package()
        results["Package Build"] = (success, message)
        
        if not success:
            print("❌ Build failed, stopping validation")
            return False
        
        # Validate metadata
        success, issues = self.validate_package_metadata()
        results["Metadata Validation"] = (success, "; ".join(issues) if issues else "All checks passed")
        
        # Test installation
        success, message = self.test_package_installation()
        results["Installation Test"] = (success, message)
        
        # Test console scripts
        success, message = self.test_console_scripts()
        results["Console Scripts"] = (success, message)
        
        # Test Docker build (optional)
        success, message = self.validate_docker_build()
        results["Docker Build"] = (success, message)
        
        # Generate report
        report = self.generate_build_report(results)
        
        # Save report
        report_file = self.project_root / "build_validation_report.md"
        report_file.write_text(report)
        
        print("=" * 50)
        print(f"📋 Full report saved to: {report_file}")
        
        # Print summary
        total_checks = len(results)
        passed_checks = sum(1 for success, _ in results.values() if success)
        
        if passed_checks == total_checks:
            print("🎉 All validation checks passed!")
            return True
        else:
            print(f"⚠️  {total_checks - passed_checks} validation checks failed")
            return False


def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(
        description="Validate package builds and distribution readiness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s build                      # Build and validate package
  %(prog)s clean                      # Clean build artifacts
  %(prog)s test-install               # Test package installation
  %(prog)s test-docker                # Test Docker build
  %(prog)s full                       # Run complete validation
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Build command
    subparsers.add_parser("build", help="Build package and validate metadata")
    
    # Clean command
    subparsers.add_parser("clean", help="Clean build artifacts")
    
    # Test installation command
    subparsers.add_parser("test-install", help="Test package installation")
    
    # Test Docker command
    subparsers.add_parser("test-docker", help="Test Docker build")
    
    # Full validation command
    subparsers.add_parser("full", help="Run complete validation pipeline")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Find project root
    project_root = Path(__file__).parent.parent
    validator = BuildValidator(project_root)
    
    try:
        if args.command == "clean":
            validator.clean_build_artifacts()
        
        elif args.command == "build":
            validator.clean_build_artifacts()
            success, message = validator.build_package()
            if success:
                success, issues = validator.validate_package_metadata()
                if not success:
                    print("❌ Metadata validation failed:")
                    for issue in issues:
                        print(f"  - {issue}")
                    sys.exit(1)
            else:
                sys.exit(1)
        
        elif args.command == "test-install":
            success, message = validator.test_package_installation()
            if not success:
                print(f"❌ {message}")
                sys.exit(1)
        
        elif args.command == "test-docker":
            success, message = validator.validate_docker_build()
            if not success:
                print(f"❌ {message}")
                sys.exit(1)
        
        elif args.command == "full":
            success = validator.run_full_validation()
            if not success:
                sys.exit(1)
    
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()