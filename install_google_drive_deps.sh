#!/bin/bash

# Install Google Drive API dependencies for REC.IO trading system

echo "🔧 Installing Google Drive API dependencies..."

# Check if we're in a virtual environment
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "⚠️  Warning: Not in a virtual environment"
    echo "   Consider activating your virtual environment first:"
    echo "   source venv/bin/activate"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Install required packages
echo "📦 Installing Google Drive API packages..."
pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client

# Check installation
echo "🔍 Verifying installation..."
python -c "
try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
    print('✅ Google Drive API packages installed successfully')
except ImportError as e:
    print(f'❌ Import error: {e}')
    exit(1)
"

if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 Google Drive dependencies installed successfully!"
    echo ""
    echo "📋 Next steps:"
    echo "1. Follow the setup guide in GOOGLE_DRIVE_SETUP_GUIDE.md"
    echo "2. Set up your Google Cloud project and credentials"
    echo "3. Configure environment variables:"
    echo "   export GOOGLE_DRIVE_CREDENTIALS=/path/to/credentials.json"
    echo "   export GOOGLE_DRIVE_FOLDER_ID=your_folder_id"
    echo "   export TRADING_SYSTEM_STORAGE=cloud"
    echo "4. Test the integration: python test_cloud_storage.py"
else
    echo "❌ Installation failed. Please check the error messages above."
    exit 1
fi 