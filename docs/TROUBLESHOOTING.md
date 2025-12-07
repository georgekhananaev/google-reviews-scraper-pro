# Troubleshooting Guide

This guide covers common issues and their solutions when running Google Reviews Scraper Pro.

---

## Table of Contents

1. [Chrome & ChromeDriver Issues](#chrome--chromedriver-issues)
2. [MongoDB Issues](#mongodb-issues)
3. [AWS S3 Issues](#aws-s3-issues)
4. [Scraping Issues](#scraping-issues)
5. [API Server Issues](#api-server-issues)
6. [Image Download Issues](#image-download-issues)
7. [Configuration Issues](#configuration-issues)
8. [Performance Issues](#performance-issues)
9. [Python & Dependencies Issues](#python--dependencies-issues)

---

## Chrome & ChromeDriver Issues

### Issue: ChromeDriver Version Mismatch

**Error Message:**
```
SessionNotCreatedException: Message: session not created: This version of ChromeDriver only supports Chrome version 143
Current browser version is 142.0.7444.176
```

**Cause:** Chrome/ChromeDriver version mismatch (this issue is now automatically handled by SeleniumBase).

**Solution:**

**Good News:** With SeleniumBase UC Mode, version mismatches are automatically resolved!

1. **Update Chrome to latest version:**
   - macOS: Open Chrome → Menu → Help → About Google Chrome
   - Or run: `open -a "Google Chrome" "chrome://settings/help"`

2. **Upgrade SeleniumBase (if needed):**
   ```bash
   pip install --upgrade seleniumbase
   ```

3. **Run scraper again** - SeleniumBase automatically downloads the matching ChromeDriver.

---

### Issue: ChromeOptions Reuse Error

**Error Message:**
```
RuntimeError: you cannot reuse the ChromeOptions object
```

**Cause:** Internal error when retrying Chrome initialization.

**Solution:** Clear the ChromeDriver cache (see above) and restart the scraper.

---

### Issue: Chrome Binary Not Found

**Error Message:**
```
WebDriverException: Message: unknown error: cannot find Chrome binary
```

**Cause:** Chrome is not installed or not in the expected location.

**Solution:**

1. **Install Chrome:**
   - Download from: https://www.google.com/chrome/

2. **For custom Chrome location, set environment variable:**
   ```bash
   export CHROME_BIN=/path/to/chrome
   ```

3. **Docker users:** Ensure Chrome is installed in Dockerfile:
   ```dockerfile
   RUN apt-get update && apt-get install -y google-chrome-stable
   ENV CHROME_BIN=/usr/bin/google-chrome
   ```

---

### Issue: Chrome Crashes in Headless Mode

**Error Message:**
```
WebDriverException: Message: chrome not reachable
```

**Solution:**

1. **Add required flags** (already included in scraper, but verify):
   ```
   --no-sandbox
   --disable-dev-shm-usage
   --disable-gpu
   ```

2. **Increase shared memory** (Docker):
   ```bash
   docker run --shm-size=2g your-image
   ```

3. **Try non-headless mode** to debug:
   ```bash
   python start.py --headless false
   ```

---

## MongoDB Issues

### Issue: Connection Timeout

**Error Message:**
```
ServerSelectionTimeoutError: connection timed out
```

**Cause:** MongoDB server unreachable or network issues.

**Solution:**

1. **Verify MongoDB is running:**
   ```bash
   # Local MongoDB
   mongosh --eval "db.adminCommand('ping')"

   # Check service status
   sudo systemctl status mongod
   ```

2. **Check connection URI:**
   ```yaml
   # config.yaml
   mongodb:
     uri: "mongodb://username:password@host:27017/"
   ```

3. **For MongoDB Atlas:**
   - Whitelist your IP address in Atlas dashboard
   - Verify cluster is active
   - Check network connectivity

4. **Test connection manually:**
   ```bash
   python -c "from pymongo import MongoClient; c = MongoClient('your-uri', serverSelectionTimeoutMS=5000); print(c.server_info())"
   ```

---

### Issue: Authentication Failed

**Error Message:**
```
OperationFailure: Authentication failed
```

**Solution:**

1. **Verify credentials** in connection URI
2. **Check database name** matches the authentication database
3. **Use correct URI format:**
   ```
   mongodb://username:password@host:27017/database?authSource=admin
   ```

---

### Issue: SSL Certificate Error

**Error Message:**
```
SSL: CERTIFICATE_VERIFY_FAILED
```

**Solution:**

1. **For macOS**, run:
   ```bash
   /Applications/Python\ 3.x/Install\ Certificates.command
   ```

2. **Or install certifi:**
   ```bash
   pip install --upgrade certifi
   ```

3. **The scraper auto-handles this**, but if issues persist:
   ```python
   import certifi
   import os
   os.environ['SSL_CERT_FILE'] = certifi.where()
   ```

---

## AWS S3 Issues

### Issue: Access Denied

**Error Message:**
```
ClientError: An error occurred (AccessDenied) when calling the PutObject operation
```

**Solution:**

1. **Verify AWS credentials:**
   ```yaml
   # config.yaml
   s3:
     aws_access_key_id: "YOUR_ACCESS_KEY"
     aws_secret_access_key: "YOUR_SECRET_KEY"
   ```

2. **Check IAM permissions** - required policy:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "s3:PutObject",
           "s3:GetObject",
           "s3:ListBucket",
           "s3:PutObjectAcl"
         ],
         "Resource": [
           "arn:aws:s3:::your-bucket-name",
           "arn:aws:s3:::your-bucket-name/*"
         ]
       }
     ]
   }
   ```

3. **Check bucket policy** allows public-read if using public URLs

---

### Issue: Bucket Not Found

**Error Message:**
```
ClientError: An error occurred (NoSuchBucket)
```

**Solution:**

1. **Verify bucket name** in config.yaml
2. **Check region** matches bucket location:
   ```yaml
   s3:
     region_name: "us-east-1"  # Must match bucket region
     bucket_name: "your-bucket"
   ```

3. **Create bucket** if it doesn't exist via AWS Console or CLI

---

### Issue: Invalid Credentials

**Error Message:**
```
NoCredentialsError: Unable to locate credentials
```

**Solution:**

1. **Set credentials in config.yaml** or environment variables:
   ```bash
   export AWS_ACCESS_KEY_ID=your_key
   export AWS_SECRET_ACCESS_KEY=your_secret
   ```

2. **Or use AWS credentials file:**
   ```
   ~/.aws/credentials
   [default]
   aws_access_key_id = YOUR_KEY
   aws_secret_access_key = YOUR_SECRET
   ```

---

## Scraping Issues

### Issue: Reviews Tab Not Found

**Error Message:**
```
TimeoutException: Reviews tab not found or could not be clicked
```

**Cause:** Google Maps UI changed or page didn't load properly.

**Solution:**

1. **Try non-headless mode** to see what's happening:
   ```bash
   python start.py --headless false
   ```

2. **Check the URL** is a valid Google Maps place URL

3. **Increase timeout** - network may be slow

4. **Clear cookies/cache** - Google may be showing consent dialogs

5. **Try different sort order:**
   ```bash
   python start.py --sort relevance
   ```

---

### Issue: No Reviews Found

**Error Message:**
```
WARNING: No review cards found in this iteration
```

**Cause:** Page structure changed or place has no reviews.

**Solution:**

1. **Verify the place has reviews** by opening URL in browser
2. **Check if page requires login** for reviews
3. **Wait longer** for page to load - add delay in config
4. **Check for CAPTCHA** - may need to solve manually first

---

### Issue: Stale Element Reference

**Error Message:**
```
StaleElementReferenceException: stale element reference: element is not attached to the page document
```

**Cause:** Page updated while scraping.

**Solution:** This is handled automatically by the scraper. If persistent:

1. **Reduce scroll speed** - increase sleep time
2. **Run in non-headless mode** to observe behavior
3. **Restart scraper** - temporary DOM issue

---

### Issue: Cookie Consent Blocking

**Cause:** Cookie dialog not being dismissed.

**Solution:**

1. **Clear browser data:**
   ```bash
   rm -rf ~/Library/Application\ Support/undetected_chromedriver
   ```

2. **The scraper handles this automatically**, but you can:
   - Open the URL manually first and accept cookies
   - Use a different Google account region

---

## API Server Issues

### Issue: Port Already in Use

**Error Message:**
```
OSError: [Errno 48] Address already in use
```

**Solution:**

1. **Find and kill the process:**
   ```bash
   # Find process using port 8000
   lsof -i :8000

   # Kill the process
   kill -9 <PID>
   ```

2. **Use different port:**
   ```bash
   uvicorn api_server:app --port 8080
   ```

---

### Issue: Max Concurrent Jobs Reached

**Error Message:**
```
HTTP 429: Maximum concurrent jobs (3) reached
```

**Solution:**

1. **Wait for existing jobs** to complete
2. **Cancel pending jobs:**
   ```bash
   curl -X POST "http://localhost:8000/jobs/{job_id}/cancel"
   ```
3. **Increase limit** in `api_server.py` (not recommended for stability)

---

### Issue: CORS Errors (Browser)

**Error Message:**
```
Access-Control-Allow-Origin header missing
```

**Solution:** CORS is enabled by default. If issues persist:

1. **Check allowed origins** in `api_server.py`
2. **For development**, ensure middleware is configured:
   ```python
   app.add_middleware(
       CORSMiddleware,
       allow_origins=["*"],
       allow_methods=["*"],
       allow_headers=["*"],
   )
   ```

---

## Image Download Issues

### Issue: Images Not Downloading

**Cause:** Network issues or Google blocking requests.

**Solution:**

1. **Check network connectivity**
2. **Verify image URLs** are accessible
3. **Reduce parallel downloads:**
   ```yaml
   download_threads: 2  # Reduce from default 4
   ```

4. **Check disk space** for image storage

---

### Issue: Images Corrupted or Wrong Size

**Cause:** Partial downloads or URL issues.

**Solution:**

1. **Clear image directory** and re-run:
   ```bash
   rm -rf review_images/
   ```

2. **Check max dimensions** in config:
   ```yaml
   max_width: 1200
   max_height: 1200
   ```

---

### Issue: Permission Denied Writing Images

**Error Message:**
```
PermissionError: [Errno 13] Permission denied
```

**Solution:**

1. **Check directory permissions:**
   ```bash
   chmod 755 review_images/
   ```

2. **Use different directory:**
   ```yaml
   image_dir: "/path/with/write/access"
   ```

---

## Configuration Issues

### Issue: Config File Not Found

**Error Message:**
```
FileNotFoundError: config.yaml not found
```

**Solution:**

1. **Create config.yaml** from example:
   ```bash
   cp examples/config-example.txt config.yaml
   ```

2. **Specify custom path:**
   ```bash
   python start.py --config /path/to/config.yaml
   ```

---

### Issue: Invalid YAML Syntax

**Error Message:**
```
yaml.scanner.ScannerError: mapping values are not allowed here
```

**Solution:**

1. **Validate YAML syntax** using online validator
2. **Check indentation** - use spaces, not tabs
3. **Escape special characters** in strings:
   ```yaml
   url: "https://example.com?param=value"  # Use quotes
   ```

---

### Issue: Invalid Configuration Values

**Error Message:**
```
ValueError: Invalid sort_by value
```

**Solution:**

1. **Check allowed values:**
   - `sort_by`: newest, highest, lowest, relevance
   - `headless`: true, false

2. **Verify types:**
   ```yaml
   download_threads: 4      # Integer, not string
   headless: true           # Boolean, not string "true"
   ```

---

## Performance Issues

### Issue: Scraping Too Slow

**Solution:**

1. **Use headless mode:**
   ```bash
   python start.py --headless
   ```

2. **Reduce image download threads** if network is slow:
   ```yaml
   download_threads: 2
   ```

3. **Disable image downloading** for faster scraping:
   ```yaml
   download_images: false
   ```

4. **Use SSD** for faster JSON/image writes

---

### Issue: High Memory Usage

**Solution:**

1. **Process in batches** - use `stop_on_match` for incremental scraping
2. **Disable image downloading** temporarily
3. **Close other applications**
4. **Increase system swap** if needed

---

### Issue: Chrome Using Too Much CPU

**Solution:**

1. **Use headless mode** - reduces rendering overhead
2. **Add GPU flags:**
   ```
   --disable-gpu
   --disable-software-rasterizer
   ```
3. **Limit concurrent jobs** in API mode

---

## Python & Dependencies Issues

### Issue: Module Not Found

**Error Message:**
```
ModuleNotFoundError: No module named 'undetected_chromedriver'
```

**Solution:**

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Verify virtual environment is activated:**
   ```bash
   source venv/bin/activate  # Linux/macOS
   venv\Scripts\activate     # Windows
   ```

---

### Issue: Incompatible Package Versions

**Error Message:**
```
ImportError: cannot import name 'X' from 'Y'
```

**Solution:**

1. **Reinstall all dependencies:**
   ```bash
   pip uninstall -r requirements.txt -y
   pip install -r requirements.txt
   ```

2. **Create fresh virtual environment:**
   ```bash
   python -m venv fresh_venv
   source fresh_venv/bin/activate
   pip install -r requirements.txt
   ```

---

### Issue: Python Version Incompatibility

**Error Message:**
```
SyntaxError: invalid syntax
```

**Solution:**

1. **Check Python version** (requires 3.9+):
   ```bash
   python --version
   ```

2. **Install correct Python version:**
   ```bash
   # macOS with pyenv
   pyenv install 3.13.1
   pyenv local 3.13.1

   # Or use system package manager
   ```

---

## Getting Help

If your issue isn't listed here:

1. **Enable debug logging:**
   ```bash
   LOG_LEVEL=DEBUG python start.py
   ```

2. **Check logs** for detailed error messages

3. **Search existing issues** on GitHub

4. **Create a new issue** with:
   - Error message (full traceback)
   - Python version (`python --version`)
   - OS and version
   - Chrome version
   - Steps to reproduce