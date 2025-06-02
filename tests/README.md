# Tests

This directory contains pytest tests for the Google Reviews Scraper.

## Running Tests

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run all tests:
```bash
pytest tests/
```

3. Run specific test files:
```bash
pytest tests/test_mongodb_connection.py
pytest tests/test_s3_connection.py
```

4. Run with verbose output:
```bash
pytest tests/ -v
```

## Test Coverage

### MongoDB Connection Tests (`test_mongodb_connection.py`)
- Tests MongoDB connection when enabled in config
- Validates MongoDB configuration parameters
- Tests basic database operations (insert/find/delete)
- Skips tests when MongoDB is disabled

### S3 Connection Tests (`test_s3_connection.py`)
- Tests S3 connection when enabled in config
- Validates S3 configuration parameters
- Tests file upload/download operations
- Tests S3Handler class initialization
- Skips tests when S3 is disabled

## Configuration

Tests use the main `config.yaml` file in the project root. Make sure your configuration is properly set up:

- For MongoDB tests: Ensure `use_mongodb: true` and valid MongoDB credentials
- For S3 tests: Ensure `use_s3: true` and valid AWS credentials

## Test Results

- Tests will be skipped if the corresponding service (MongoDB/S3) is disabled in config
- Failed connection tests indicate configuration or service availability issues
- All tests should pass when services are properly configured and accessible