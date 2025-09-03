#!/bin/bash

# Deploy Angular App to MicroPython Device
# This script builds the Angular app and deploys it to a connected MicroPython device
#
# Usage: ./deploy-to-device.sh [options]
# Options:
#   -h, --help     Show this help message
#   -d, --device   Specify device path (e.g., /dev/cu.wchusbserial120)
#
# Requirements:
#   - mpremote (pip install mpremote)
#   - Node.js and npm (for Angular build)
#   - MicroPython device connected via USB

set -e  # Exit on any error

# Function to show help
show_help() {
    echo "Deploy Angular App to MicroPython Device"
    echo
    echo "Usage: $0 [options]"
    echo
    echo "Options:"
    echo "  -h, --help     Show this help message"
    echo "  -d, --device   Specify device path (e.g., /dev/cu.wchusbserial120)"
    echo
    echo "This script will:"
    echo "  1. Clean the local /www/ folder"
    echo "  2. Build the Angular application"
    echo "  3. Copy build artifacts to local /www/"
    echo "  4. Connect to MicroPython device"
    echo "  5. Deploy /www/ folder to the device"
    echo
    echo "Requirements:"
    echo "  - mpremote (install with: pip install mpremote)"
    echo "  - Node.js and npm"
    echo "  - MicroPython device connected via USB"
    echo
    exit 0
}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default device path
DEFAULT_DEVICE="/dev/cu.wchusbserial120"

# Command line options
SPECIFIED_DEVICE=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            ;;
        -d|--device)
            SPECIFIED_DEVICE="$2"
            shift 2
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}=== MicroPython Device Deployment Script ===${NC}"
echo

# Step 1: Delete contents of local /www/ folder
echo -e "${YELLOW}Step 1: Cleaning local /www/ folder...${NC}"
if [ -d "www" ]; then
    rm -rf www/*
    echo -e "${GREEN}✓ Local /www/ folder cleaned${NC}"
else
    mkdir -p www
    echo -e "${GREEN}✓ Created local /www/ folder${NC}"
fi
echo

# Step 2: Build Angular application and copy artifacts
echo -e "${YELLOW}Step 2: Building Angular application...${NC}"
cd mcu-control-app

# Check if package.json exists
if [ ! -f "package.json" ]; then
    echo -e "${RED}✗ Error: package.json not found in mcu-control-app directory${NC}"
    exit 1
fi

# Build the Angular app
echo "Building Angular app..."
npm run build

# Check if build was successful
if [ ! -d "dist/mcu-control-app/browser" ]; then
    echo -e "${RED}✗ Error: Build failed or browser folder not found${NC}"
    exit 1
fi

# Copy build artifacts to local www folder
echo "Copying build artifacts to local /www/ folder..."
cp -r dist/mcu-control-app/browser/* ../www/
echo -e "${GREEN}✓ Angular app built and copied to local /www/${NC}"

cd ..
echo

# Step 3: Check MicroPython device connection
echo -e "${YELLOW}Step 3: Checking MicroPython device connection...${NC}"

# Function to check if mpremote is available
check_mpremote() {
    if ! command -v mpremote &> /dev/null; then
        echo -e "${RED}✗ Error: mpremote not found. Please install it with: pip install mpremote${NC}"
        exit 1
    fi
}

# Function to list available devices
list_devices() {
    echo "Scanning for available devices..."
    mpremote connect list 2>/dev/null || echo "No devices found with mpremote connect list"
}

# Function to get device input from user
get_device_input() {
    echo -e "${BLUE}Available devices (examples):${NC}"

    # Show available devices for reference
    echo "Scanning for USB serial devices..."
    devices=($(ls /dev/cu.* 2>/dev/null | grep -E "(usbserial|usbmodem)" || true))

    if [ ${#devices[@]} -gt 0 ]; then
        echo "Found devices:"
        for device in "${devices[@]}"; do
            echo "  $device"
        done
    else
        echo "No USB serial devices found automatically."
        echo "Common device patterns:"
        echo "  /dev/cu.wchusbserial*"
        echo "  /dev/cu.usbmodem*"
        echo "  /dev/ttyUSB*"
        echo "  /dev/ttyACM*"
    fi

    echo
    echo -e "${YELLOW}Please enter the device path manually:${NC}"
    echo "Examples:"
    echo "  /dev/cu.wchusbserial120"
    echo "  /dev/cu.usbmodem14101"
    echo "  /dev/ttyUSB0"
    echo

    while true; do
        echo -n "Device path: "
        read -r device_input

        # Remove any leading/trailing whitespace
        device_input=$(echo "$device_input" | xargs)

        if [ -z "$device_input" ]; then
            echo -e "${RED}Please enter a device path${NC}"
            continue
        fi

        # Check if device exists
        if [ ! -e "$device_input" ]; then
            echo -e "${YELLOW}⚠ Warning: Device $device_input does not exist${NC}"
            echo -n "Continue anyway? (y/N): "
            read -r confirm
            if [[ "$confirm" =~ ^[Yy]$ ]]; then
                echo "$device_input"
                return
            else
                continue
            fi
        fi

        echo "$device_input"
        return
    done
}



check_mpremote

# Determine which device to try first
DEVICE_PATH=""
FIRST_TRY_DEVICE="$DEFAULT_DEVICE"

if [ -n "$SPECIFIED_DEVICE" ]; then
    FIRST_TRY_DEVICE="$SPECIFIED_DEVICE"
    echo "Using specified device: $SPECIFIED_DEVICE"
fi

# Try to connect to the first choice device
if [ -e "$FIRST_TRY_DEVICE" ]; then
    echo "Trying device: $FIRST_TRY_DEVICE"
    if mpremote connect "$FIRST_TRY_DEVICE" exec "print('Connected')" &>/dev/null; then
        DEVICE_PATH="$FIRST_TRY_DEVICE"
        echo -e "${GREEN}✓ Connected to device: $FIRST_TRY_DEVICE${NC}"
    else
        echo -e "${YELLOW}⚠ Device not responding: $FIRST_TRY_DEVICE${NC}"
    fi
fi

# If default device didn't work, ask user for device input
if [ -z "$DEVICE_PATH" ]; then
    echo "Default device not available. Please specify device manually."
    list_devices
    echo
    DEVICE_PATH=$(get_device_input)
    
    # Test the selected device
    echo "Testing connection to: $DEVICE_PATH"
    if ! mpremote connect "$DEVICE_PATH" exec "print('Connected')" &>/dev/null; then
        echo -e "${RED}✗ Failed to connect to selected device: $DEVICE_PATH${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Successfully connected to: $DEVICE_PATH${NC}"
fi

echo

# Step 4: Note about exiting mpremote (informational)
echo -e "${YELLOW}Step 4: Device connection established${NC}"
echo -e "${BLUE}Note: When manually using mpremote, you can exit with Ctrl+X${NC}"
echo

# Step 5: Deploy files to device
echo -e "${YELLOW}Step 5: Deploying files to MicroPython device...${NC}"

echo "Removing existing /www/ folder on device..."
mpremote connect "$DEVICE_PATH" exec "
try:
    import os
    def rmtree(path):
        try:
            for item in os.listdir(path):
                item_path = path + '/' + item
                try:
                    stat = os.stat(item_path)
                    if stat[0] & 0x4000:  # Directory
                        rmtree(item_path)
                    else:  # File
                        os.remove(item_path)
                except:
                    pass
            os.rmdir(path)
        except:
            pass
    rmtree('/www')
    print('Removed /www/ folder')
except Exception as e:
    print('Note: /www/ folder may not have existed')
"

echo "Copying /www/ folder to device..."
if mpremote connect "$DEVICE_PATH" cp -r www/ :; then
    echo -e "${GREEN}✓ Successfully deployed /www/ folder to device${NC}"
else
    echo -e "${RED}✗ Failed to copy files to device${NC}"
    exit 1
fi

echo
echo -e "${GREEN}=== Deployment Complete! ===${NC}"
echo -e "${BLUE}Summary:${NC}"
echo "  • Angular app built successfully"
echo "  • Files copied to local /www/ folder"
echo "  • Connected to device: $DEVICE_PATH"
echo "  • Deployed /www/ folder to MicroPython device"
echo
echo -e "${BLUE}Your MicroPython device now has the latest Angular app in /www/${NC}"
