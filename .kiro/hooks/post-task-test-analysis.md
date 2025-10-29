# Post-Feature Test Analysis Hook

## Trigger
- Manual button: "Analyze Tests After Feature"
- Description: "Run comprehensive test analysis after completing all tasks in a feature"

## Hook Behavior

When triggered, this hook should:

1. **Run Full Test Suite**
   - Execute all tests with detailed output
   - Capture failures and errors
   - Generate coverage report for the entire codebase

2. **Analyze Test Results**
   - Identify broken tests that need fixing
   - Find gaps in test coverage for all modified code in the feature
   - Detect obsolete tests that should be removed
   - Check integration points between feature components

3. **Generate Action Plan**
   - List specific tests that need updates
   - Suggest new tests for uncovered functionality
   - Prioritize fixes by impact and feature criticality
   - Identify end-to-end test scenarios

4. **Present Options**
   - Fix broken tests immediately
   - Add missing test coverage
   - Update integration tests
   - Schedule comprehensive test refactoring

## Usage Pattern

Use this hook after completing ALL tasks within a feature to ensure the entire feature is properly tested and doesn't break existing functionality.