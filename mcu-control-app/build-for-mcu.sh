#!/bin/bash

# Build script for MCU deployment
# This script builds the Angular application and prepares it for MCU deployment

echo "🚀 Building MCU Control Application for deployment..."

# Clean previous build
echo "🧹 Cleaning previous build..."
rm -rf dist/

# Build the application
echo "🔨 Building Angular application..."
npm run build

if [ $? -eq 0 ]; then
    echo "✅ Build successful!"
    
    # Create deployment directory
    echo "📦 Preparing deployment package..."
    mkdir -p deployment/www
    
    # Copy build files to deployment directory
    cp -r dist/mcu-control-app/* deployment/www/
    
    echo "📁 Deployment files ready in: deployment/www/"
    echo ""
    echo "📋 Deployment Instructions:"
    echo "1. Copy the contents of 'deployment/www/' to your MCU device:"
    echo "   - For SD card: /sd/www/"
    echo "   - For flash memory: /www/"
    echo ""
    echo "2. Ensure your MCU web server is configured to serve from the correct path"
    echo ""
    echo "3. Access the application at: http://[MCU_IP_ADDRESS]/"
    echo ""
    echo "🎉 Ready for deployment!"
else
    echo "❌ Build failed!"
    exit 1
fi
