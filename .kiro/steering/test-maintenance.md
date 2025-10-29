# Test Maintenance Guidelines

## When to Analyze Tests

### After Feature Completion (Primary Trigger)
- Run full test suite to identify broken tests
- Comprehensive test review across all related components
- Analyze test coverage for new/modified code in the entire feature
- Update or remove obsolete tests
- Add missing test cases for new functionality
- Integration test validation
- End-to-end test updates
- Performance test considerations

### Individual Task Completion
- Only run quick smoke tests to ensure basic functionality
- Save comprehensive test analysis for feature completion

## Test Analysis Process

1. **Run Full Test Suite**: `python3 -m pytest -v --tb=short`
2. **Coverage Analysis**: Check coverage reports for gaps
3. **Test Categorization**:
   - ✅ Passing tests (no action needed)
   - ❌ Broken tests (need fixes)
   - 🔄 Outdated tests (need updates)
   - ➕ Missing tests (need creation)
4. **Prioritize Updates**: Fix broken tests first, then add missing coverage

## Test Update Guidelines

- Fix existing tests before adding new ones
- Focus on core functionality testing
- Keep tests minimal and focused
- Update test data/fixtures as needed
- Maintain test isolation and independence

## Integration with Workflow

- Run comprehensive test analysis after completing all tasks in a feature
- Block feature completion until all tests pass
- Document test changes in feature completion notes
- Individual tasks only require basic functionality verification