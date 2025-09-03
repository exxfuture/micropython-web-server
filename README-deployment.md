# MicroPython Device Deployment Script

This script (`deploy-to-device.sh`) automates the process of building the Angular application and deploying it to a MicroPython device.

## Features

- **Automated Build Process**: Builds the Angular app and copies artifacts to local `/www/` folder
- **Device Auto-Detection**: Automatically finds and connects to MicroPython devices
- **Simple Device Selection**: Manual device path input with helpful device scanning
- **Robust Error Handling**: Comprehensive error checking and user feedback
- **Command Line Options**: Support for various deployment scenarios

## Requirements

Before using this script, ensure you have:

1. **mpremote** - Install with: `pip install mpremote`
2. **Node.js and npm** - For building the Angular application
3. **MicroPython device** - Connected via USB

## Usage

### Basic Usage

```bash
./deploy-to-device.sh
```

This will:
1. Clean the local `/www/` folder
2. Build the Angular application
3. Copy build artifacts to local `/www/`
4. Auto-detect and connect to MicroPython device
5. Deploy `/www/` folder to the device

### Command Line Options

```bash
# Show help
./deploy-to-device.sh --help

# Specify a specific device
./deploy-to-device.sh --device /dev/cu.wchusbserial120
```

### Options

- `-h, --help` - Show help message and exit
- `-d, --device <path>` - Specify device path (e.g., `/dev/cu.wchusbserial120`)

## Device Selection

The script uses a simple device selection method:

1. **Automatic Detection**: First tries the default device `/dev/cu.wchusbserial120`
2. **Device Scanning**: If default fails, scans for available USB serial devices
3. **Manual Input**: Prompts user to enter the device path manually
4. **Validation**: Checks if the entered device exists and warns if not found

## Default Device

The script first tries to connect to `/dev/cu.wchusbserial120` by default. If this device is not available or doesn't respond, it will scan for other available devices.

## Troubleshooting

### Common Issues

1. **mpremote not found**
   ```bash
   pip install mpremote
   ```

2. **No devices found**
   - Ensure your MicroPython device is connected via USB
   - Check that the device is recognized by your system: `ls /dev/cu.*`

3. **Permission denied**
   - Make the script executable: `chmod +x deploy-to-device.sh`
   - You may need to add your user to the dialout group (Linux)

4. **Build fails**
   - Ensure you're in the correct directory (web-server folder)
   - Check that `mcu-control-app/package.json` exists
   - Run `npm install` in the mcu-control-app directory if needed

### Device Connection Issues

If the script can't connect to your device:

1. Check device connection: `mpremote connect list`
2. Try specifying the device manually: `./deploy-to-device.sh --device /dev/cu.yourdevice`
3. Ensure the device is running MicroPython and responding

## What the Script Does

### Step 1: Clean Local Files
- Removes contents of local `/www/` folder
- Creates the folder if it doesn't exist

### Step 2: Build Angular App
- Changes to `mcu-control-app` directory
- Runs `npm run build`
- Copies build artifacts from `dist/mcu-control-app/browser/` to `../www/`

### Step 3: Device Connection
- Checks if mpremote is available
- Tries default device first
- If needed, scans for available devices and presents selection menu

### Step 4: Deploy to Device
- Removes existing `/www/` folder on the MicroPython device
- Copies local `/www/` folder to the device using `mpremote cp -r`

## File Structure

After successful deployment, your MicroPython device will have:

```
/www/
├── index.html
├── main-*.js
├── chunk-*.js
├── styles-*.css
└── favicon.ico
```

## Notes

- The script uses colors for better user experience
- All operations include progress feedback
- Error messages are clearly displayed
- The script exits cleanly on any error

## Examples

```bash
# Basic deployment
./deploy-to-device.sh

# Deploy to specific device
./deploy-to-device.sh -d /dev/cu.wchusbserial120

# Get help
./deploy-to-device.sh --help
```
