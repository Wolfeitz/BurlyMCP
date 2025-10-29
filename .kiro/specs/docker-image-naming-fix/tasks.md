# Implementation Plan

- [x] 1. Update GitHub Actions workflow environment variables
  - Modify the IMAGE_NAME environment variable to use lowercase format "wolfeitz/burlymcp"
  - Ensure REGISTRY environment variable remains "ghcr.io"
  - Update any workflow-level environment variable references
  - _Requirements: 1.1, 1.4, 2.3_

- [x] 2. Fix container image validation script
  - [x] 2.1 Update hardcoded image references in validation scripts
    - Replace "Wolfeitz/BurlyMCP" with "wolfeitz/burlymcp" in MAIN_TAG construction
    - Update any other hardcoded image references in the validation script
    - _Requirements: 1.2, 1.3_
  
  - [x] 2.2 Verify Docker pull and run commands use correct image format
    - Ensure docker pull command uses the corrected lowercase image name
    - Update docker run command to reference the correct image
    - _Requirements: 1.2, 1.3_

- [x] 3. Fix security scanning integration
  - [x] 3.1 Update Trivy security scan configuration
    - Ensure Trivy scan targets the correct lowercase image name
    - Verify SARIF file generation path and naming
    - _Requirements: 3.1, 3.2, 3.4_
  
  - [x] 3.2 Fix SARIF file upload step
    - Ensure trivy-results.sarif file is generated in the expected location
    - Verify the upload-sarif action can find and process the file
    - Add error handling for missing SARIF files
    - _Requirements: 3.2, 3.3_

- [x] 4. Update documentation and references
  - [x] 4.1 Update README.md with new image references
    - Replace any references to the old image name format
    - Update usage examples and deployment instructions
    - _Requirements: 2.5_
  
  - [x] 4.2 Update deployment documentation
    - Update docker-compose files with new image references
    - Update any deployment scripts or configuration files
    - _Requirements: 2.5_

- [x] 5. Test the complete workflow
  - [x] 5.1 Validate workflow execution with new naming
    - Run the complete GitHub Actions workflow to ensure it passes
    - Verify image publishing succeeds without format errors
    - _Requirements: 1.2, 1.3_
  
  - [x] 5.2 Test image deployment and functionality
    - Pull and run the published image to verify functionality
    - Test health endpoint and MCP endpoint responses
    - _Requirements: 1.3, 3.4_