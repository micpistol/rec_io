# REC.IO Authentication System

This document describes the authentication system for the REC.IO trading platform.

## Overview

The authentication system provides a simple login gateway for cloud deployment while remaining minimally invasive for local development. It includes:

- Username/password authentication
- Device/network remembering functionality
- Local development bypass
- Token-based session management

## Features

### 🔐 Secure Authentication
- Username and password authentication
- Secure token generation and storage
- Password hashing with PBKDF2
- Session expiration management

### 💾 Device Remembering
- "Remember this device" functionality
- Long-term device tokens (365 days)
- Automatic login for remembered devices
- Network-based device identification

### 🚀 Local Development
- Local development bypass button
- Environment variable control (`AUTH_ENABLED`)
- No authentication required for local testing
- Easy toggle between dev and production modes

### 🔄 Session Management
- Automatic token verification
- Secure logout functionality
- Token cleanup on logout
- Session persistence across browser restarts

## Setup

### 1. Initial Setup

Run the authentication setup script:

```bash
python scripts/setup_auth.py
```

This will:
- Update your `user_info.json` with a password
- Create authentication token files
- Set up the necessary directory structure

### 2. Environment Configuration

For local development (no authentication):
```bash
export AUTH_ENABLED=false
```

For production deployment (authentication required):
```bash
export AUTH_ENABLED=true
```

### 3. Testing

Test the authentication system:

```bash
python scripts/test_auth.py
```

## Usage

### Login Flow

1. **Access Login Page**: Navigate to `/login`
2. **Enter Credentials**: Use username and password from `user_info.json`
3. **Remember Device**: Check "Remember this device" for persistent login
4. **Local Bypass**: Click "Local Development Bypass" for immediate access

### Default Credentials

- **Username**: `ewais` (or your user_id from user_info.json)
- **Password**: `admin` (or the password you set during setup)

### API Endpoints

#### Login
```
POST /api/auth/login
{
  "username": "ewais",
  "password": "admin",
  "rememberDevice": true
}
```

#### Verify Token
```
POST /api/auth/verify
{
  "token": "your_token_here",
  "deviceId": "your_device_id"
}
```

#### Logout
```
POST /api/auth/logout
{
  "token": "your_token_here",
  "deviceId": "your_device_id"
}
```

## File Structure

```
backend/data/users/user_0001/
├── user_info.json          # User credentials and info
├── auth_tokens.json        # Active authentication tokens
└── device_tokens.json      # Remembered device tokens
```

## Security Features

### Token Security
- Cryptographically secure token generation
- Token expiration (24 hours default, 30 days with remember device)
- Secure token storage in user-specific files

### Password Security
- PBKDF2 password hashing
- Salt-based password storage
- Secure password verification

### Device Security
- Unique device identification
- Network-based device tracking
- Secure device token storage

## Deployment Considerations

### Local Development
- Authentication is disabled by default
- Local bypass available for quick testing
- No authentication required for development

### Cloud Deployment
- Set `AUTH_ENABLED=true` environment variable
- Authentication required for all access
- Device remembering for user convenience
- Secure token management

### Production Security
- Change default password immediately
- Use strong, unique passwords
- Regularly rotate authentication tokens
- Monitor authentication logs

## Troubleshooting

### Common Issues

1. **Login Page Not Found**
   - Ensure `frontend/login.html` exists in project
   - Check file permissions

2. **Authentication Fails**
   - Verify credentials in `user_info.json`
   - Check authentication token files exist
   - Ensure server is running

3. **Local Bypass Not Working**
   - Check `AUTH_ENABLED` environment variable
   - Verify local development mode is active

4. **Device Not Remembered**
   - Check "Remember this device" checkbox
   - Verify device token files are writable
   - Check browser localStorage support

### Debug Commands

Check authentication status:
```bash
curl -X POST http://localhost:3000/api/auth/verify \
  -H "Content-Type: application/json" \
  -d '{"token":"test","deviceId":"test"}'
```

Test login:
```bash
curl -X POST http://localhost:3000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"ewais","password":"admin"}'
```

## Future Enhancements

- Multi-factor authentication
- Role-based access control
- Session management dashboard
- Audit logging
- Password reset functionality
- Account lockout protection 