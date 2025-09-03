#!/usr/bin/env python3
"""
ESP32 CYD (Cheap Yellow Display) HTTP Server
Using MicroPython-HTTP-Server (ahttpserver) for better memory efficiency

This server provides REST API endpoints for controlling RGB LEDs and monitoring buttons
on the ESP32 CYD board, with static file serving for Angular web applications.

Features:
- Async HTTP server with low memory footprint
- RGB LED control with PWM brightness (Red: Pin 4, Green: Pin 16, Blue: Pin 17)
- Button monitoring (Boot button: Pin 0)
- Network configuration (WiFi/Ethernet)
- Static file serving with chunked delivery
- Memory-efficient operation using asyncio

Author: Generated for ESP32 CYD project
"""

import gc
import json
import machine
import network
import os
import time
import uasyncio as asyncio

# Import the async HTTP server
from ahttpserver import HTTPResponse, HTTPServer, sendfile

# ============================================================================
# ===( Configuration )=======================================================
# ============================================================================

# Storage Configuration
USE_SD_CARD = False              # True = use SD card (/sd/www), False = use flash memory (/www)

# Network Configuration  
USE_WIFI = True                # True = use WiFi, False = use Ethernet (LAN)
WIFI_SSID = "Test"   # WiFi network name
WIFI_PASSWORD = "Test"  # WiFi password

# File serving configuration
CHUNK_SIZE = 1024               # Chunk size for file reading (1KB)
LARGE_FILE_THRESHOLD = 50000    # Files larger than this will be logged (50KB)
HUGE_FILE_THRESHOLD = 500000    # Files larger than this get special handling (500KB)

# ============================================================================
# ===( LED Control Functions )===============================================
# ============================================================================

# RGB LED pins for ESP32 CYD
LED_RED_PIN = 4      # Red LED
LED_GREEN_PIN = 16   # Green LED  
LED_BLUE_PIN = 17    # Blue LED

# Initialize PWM for RGB LEDs
led_red = machine.PWM(machine.Pin(LED_RED_PIN))
led_green = machine.PWM(machine.Pin(LED_GREEN_PIN))
led_blue = machine.PWM(machine.Pin(LED_BLUE_PIN))

# Set PWM frequency (1000 Hz is good for LEDs)
led_red.freq(1000)
led_green.freq(1000)
led_blue.freq(1000)

# LED state tracking
led_states = [False, False, False]  # Red, Green, Blue
led_brightness = [50, 50, 50]       # Default 50% brightness
led_names = ["Red", "Green", "Blue"]

def set_led_state(led_index, state):
    """Set LED on/off state"""
    global led_states
    led_states[led_index] = state
    
    if state:
        # Turn on with current brightness
        set_led_brightness(led_index, led_brightness[led_index])
    else:
        # Turn off
        if led_index == 0:
            led_red.duty(0)
        elif led_index == 1:
            led_green.duty(0)
        elif led_index == 2:
            led_blue.duty(0)

def set_led_brightness(led_index, brightness):
    """Set LED brightness (0-100%)"""
    global led_brightness, led_states
    
    # Clamp brightness to valid range
    brightness = max(0, min(100, brightness))
    led_brightness[led_index] = brightness
    
    # Convert percentage to PWM duty cycle (0-1023)
    duty = int((brightness / 100.0) * 1023)
    
    if brightness > 0:
        led_states[led_index] = True
        if led_index == 0:
            led_red.duty(duty)
        elif led_index == 1:
            led_green.duty(duty)
        elif led_index == 2:
            led_blue.duty(duty)
    else:
        led_states[led_index] = False
        if led_index == 0:
            led_red.duty(0)
        elif led_index == 1:
            led_green.duty(0)
        elif led_index == 2:
            led_blue.duty(0)

def get_led_state(led_index):
    """Get LED on/off state"""
    return led_states[led_index]

def get_led_brightness(led_index):
    """Get LED brightness (0-100%)"""
    return led_brightness[led_index]

def cleanup_leds():
    """Turn off all LEDs"""
    for i in range(3):
        set_led_state(i, False)

# ============================================================================
# ===( Utility Functions )===================================================
# ============================================================================

def get_web_root():
    """Get the web root directory based on configuration"""
    return '/sd/www' if USE_SD_CARD else '/www'

# ============================================================================
# ===( Network Setup )=======================================================
# ============================================================================

def setup_wifi():
    """Setup WiFi connection"""
    try:
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        print(wlan.scan())
        
        if not wlan.isconnected():
            print(f"Connecting to WiFi: {WIFI_SSID}")
            wlan.connect(WIFI_SSID, WIFI_PASSWORD)
            
            # Wait for connection with timeout
            timeout = 20
            print(f"Start waiting for Wifi for: {timeout} seconds")
            while not wlan.isconnected() and timeout > 0:
                time.sleep(1)
                timeout -= 1
                print(f"Waiting for Wifi for: {timeout} seconds...")
                print(".", end="")
            
            print()
            
        if wlan.isconnected():
            net_cfg = wlan.ifconfig()
            print(f"WiFi connected: {net_cfg[0]}")
            return net_cfg
        else:
            print("WiFi connection failed")
            return None
            
    except Exception as e:
        print(f"WiFi setup error: {e}")
        return None

def setup_ethernet():
    """Setup Ethernet connection (if available)"""
    try:
        lan = network.LAN(0)
        lan.active(True)
        
        # Wait for connection
        timeout = 10
        while not lan.isconnected() and timeout > 0:
            time.sleep(1)
            timeout -= 1
            
        if lan.isconnected():
            net_cfg = lan.ifconfig()
            print(f"Ethernet connected: {net_cfg[0]}")
            return net_cfg
        else:
            print("Ethernet connection failed")
            return None
            
    except Exception as e:
        print(f"Ethernet setup error: {e}")
        return None

def setup_network():
    """Setup network connection based on configuration"""
    if USE_WIFI:
        print("Network mode: WiFi")
        net_cfg = setup_wifi()
        if net_cfg is None:
            print("WiFi failed, falling back to Ethernet...")
            net_cfg = setup_ethernet()
    else:
        print("Network mode: Ethernet")
        net_cfg = setup_ethernet()
        if net_cfg is None:
            print("Ethernet failed, trying WiFi...")
            net_cfg = setup_wifi()

    if net_cfg:
        print(f"Network IP: {net_cfg[0]}")
        return net_cfg
    else:
        print("All network connections failed!")
        return None

# Setup network connection
net_cfg = setup_network()
if not net_cfg:
    print("Warning: No network connection available")
    net_cfg = ['0.0.0.0', '255.255.255.0', '0.0.0.0', '0.0.0.0']  # Fallback

# ============================================================================
# ===( Hardware Setup )======================================================
# ============================================================================

# Boot button on ESP32 CYD (Pin 0)
BTN_BOOT = machine.Pin(0, machine.Pin.IN, machine.Pin.PULL_UP)

print("ESP32 CYD hardware initialized:")
print(f"  RGB LEDs: {led_names} on pins 4, 16, 17")
print(f"  Boot button: Pin 0")

# ============================================================================
# ===( HTTP Server Setup )===================================================
# ============================================================================

# Create async HTTP server instance
app = HTTPServer(host="0.0.0.0", port=80, timeout=30)

# ============================================================================
# ===( API Endpoints )=======================================================
# ============================================================================

# CORS preflight handler for all API endpoints
@app.route("OPTIONS", "/api/status")
@app.route("OPTIONS", "/api/leds")
@app.route("OPTIONS", "/api/lamp")
@app.route("OPTIONS", "/api/network")
async def api_options(reader, writer, request):
    """Handle CORS preflight requests"""
    cors_headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Max-Age": "86400"
    }
    response = HTTPResponse(200, "text/plain", close=True, header=cors_headers)
    await response.send(writer)
    await writer.drain()

@app.route("GET", "/api/status")
async def api_status(reader, writer, request):
    """Get LED and button status"""
    data = {
        "leds": {
            "1": get_led_state(0),      # Red LED
            "2": get_led_state(1),      # Green LED
            "3": get_led_state(2),      # Blue LED
        },
        "led_brightness": {
            "1": get_led_brightness(0), # Red brightness
            "2": get_led_brightness(1), # Green brightness
            "3": get_led_brightness(2), # Blue brightness
        },
        "buttons": {
            "boot": BTN_BOOT.value(),   # Boot button (0 = pressed, 1 = not pressed)
        }
    }

    # Add CORS headers
    cors_headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    }
    response = HTTPResponse(200, "application/json", close=True, header=cors_headers)
    await response.send(writer)
    writer.write(json.dumps(data))
    await writer.drain()

@app.route("POST", "/api/leds")
async def api_set_led(reader, writer, request):
    """Control LEDs"""
    try:
        # Read the request body
        content_length = 0
        if b'content-length' in request.header:
            content_length = int(request.header[b'content-length'])
        elif b'Content-Length' in request.header:
            content_length = int(request.header[b'Content-Length'])

        if content_length > 0:
            body_data = await reader.read(content_length)
            body = json.loads(body_data.decode('utf-8'))
        else:
            body = {}

        if not body:
            response = HTTPResponse(400, "application/json", close=True)
            await response.send(writer)
            writer.write(json.dumps({"error": "bad request"}))
            await writer.drain()
            return

        led = int(body.get("led", 0))
        value = body.get("value", False)
        brightness = int(body.get("brightness", 50))  # Default 50% brightness

        # Validate LED index (1-3 for Red, Green, Blue)
        if led < 1 or led > 3:
            response = HTTPResponse(400, "application/json", close=True)
            await response.send(writer)
            writer.write(json.dumps({"error": "invalid led, must be 1-3"}))
            await writer.drain()
            return

        # Validate brightness
        brightness = max(0, min(100, brightness))

        led_index = led - 1  # Convert to 0-based index

        if value:
            # Turn on LED with specified brightness
            set_led_brightness(led_index, brightness)
        else:
            # Turn off LED
            set_led_state(led_index, False)

    except Exception as e:
        response = HTTPResponse(400, "application/json", close=True)
        await response.send(writer)
        writer.write(json.dumps({"error": "bad request"}))
        await writer.drain()
        return

    response_data = {
        "ok": True,
        "led": led,
        "value": get_led_state(led_index),
        "brightness": get_led_brightness(led_index)
    }

    # Add CORS headers
    cors_headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    }
    response = HTTPResponse(200, "application/json", close=True, header=cors_headers)
    await response.send(writer)
    writer.write(json.dumps(response_data))
    await writer.drain()

@app.route("GET", "/api/lamp")
async def api_get_lamp_status(reader, writer, request):
    """Get current lamp status - adapted for ESP32 CYD RGB LEDs"""

    # Map RGB LEDs to lamp status format
    # Red LED = nearInfraredStatus, Green+Blue = redLightStatus
    red_on = get_led_state(0)
    green_on = get_led_state(1)
    blue_on = get_led_state(2)

    # Return lamp status in the expected format
    data = {
        "nearInfraredStatus": {
            "power": "ON" if red_on else "OFF",
            "mode": "STATIC",
            "brightness": get_led_brightness(0),
            "speed": 20,
            "timer": 10,
            "elapsedTime": 0
        },
        "redLightStatus": {
            "power": "ON" if (green_on or blue_on) else "OFF",
            "mode": "STATIC",
            "brightness": max(get_led_brightness(1), get_led_brightness(2)),
            "speed": 20,
            "timer": 10,
            "elapsedTime": 0
        }
    }

    # Add CORS headers
    cors_headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    }
    response = HTTPResponse(200, "application/json", close=True, header=cors_headers)
    await response.send(writer)
    writer.write(json.dumps(data))
    await writer.drain()

@app.route("POST", "/api/lamp")
async def api_set_lamp(reader, writer, request):
    """Set lamp configuration - adapted for ESP32 CYD RGB LEDs"""
    try:
        # Read the request body
        content_length = 0
        if b'content-length' in request.header:
            content_length = int(request.header[b'content-length'])
        elif b'Content-Length' in request.header:
            content_length = int(request.header[b'Content-Length'])

        if content_length > 0:
            body_data = await reader.read(content_length)
            body = json.loads(body_data.decode('utf-8'))
        else:
            body = {}

        if not body:
            response = HTTPResponse(400, "application/json", close=True)
            await response.send(writer)
            writer.write(json.dumps({"error": "Missing request body"}))
            await writer.drain()
            return

        print("=== LAMP REQUEST DEBUG ===")
        print("Full request body:", body)

        # Handle the actual request structure - data is wrapped in "request" object
        if "request" in body:
            request_data = body["request"]
        else:
            request_data = body

        # Process nearInfraredStatus (maps to Red LED)
        if "nearInfraredStatus" in request_data:
            near_ir_st = request_data["nearInfraredStatus"]

            power = near_ir_st.get("power", "OFF").upper()
            brightness = int(near_ir_st.get("brightness", 0))
            brightness = max(0, min(100, brightness))

            if power == "ON" and brightness > 0:
                set_led_brightness(0, brightness)  # Red LED
            else:
                set_led_state(0, False)  # Turn off Red LED

        # Process redLightStatus (maps to Green and Blue LEDs)
        if "redLightStatus" in request_data:
            red_light_st = request_data["redLightStatus"]

            power = red_light_st.get("power", "OFF").upper()
            brightness = int(red_light_st.get("brightness", 0))
            brightness = max(0, min(100, brightness))

            if power == "ON" and brightness > 0:
                set_led_brightness(1, brightness)  # Green LED
                set_led_brightness(2, brightness)  # Blue LED
            else:
                set_led_state(1, False)  # Turn off Green LED
                set_led_state(2, False)  # Turn off Blue LED

        # Return the processed values
        response_data = {
            "ok": True,
            "nearInfraredStatus": {
                "power": "ON" if get_led_state(0) else "OFF",
                "mode": "STATIC",
                "brightness": get_led_brightness(0),
                "speed": 20,
                "timer": 10,
                "elapsedTime": 0
            },
            "redLightStatus": {
                "power": "ON" if (get_led_state(1) or get_led_state(2)) else "OFF",
                "mode": "STATIC",
                "brightness": max(get_led_brightness(1), get_led_brightness(2)),
                "speed": 20,
                "timer": 10,
                "elapsedTime": 0
            }
        }

        # Add CORS headers
        cors_headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        }
        response = HTTPResponse(200, "application/json", close=True, header=cors_headers)
        await response.send(writer)
        writer.write(json.dumps(response_data))
        await writer.drain()

    except Exception as e:
        print(f"Error in set_lamp: {e}")
        response = HTTPResponse(500, "application/json", close=True)
        await response.send(writer)
        writer.write(json.dumps({"error": f"Server error: {str(e)}"}))
        await writer.drain()

@app.route("GET", "/api/network")
async def api_get_network_status(reader, writer, request):
    """Get current network configuration and status"""
    try:
        # Get current network interface status
        network_info = {
            "configured_mode": "WiFi" if USE_WIFI else "Ethernet",
            "ip_address": net_cfg[0] if net_cfg else "0.0.0.0",
            "subnet_mask": net_cfg[1] if net_cfg and len(net_cfg) > 1 else "255.255.255.0",
            "gateway": net_cfg[2] if net_cfg and len(net_cfg) > 2 else "0.0.0.0",
            "dns": net_cfg[3] if net_cfg and len(net_cfg) > 3 else "0.0.0.0",
            "connected": net_cfg[0] != "0.0.0.0" if net_cfg else False,
            "web_storage": "SD Card" if USE_SD_CARD else "Flash Memory",
            "web_root": get_web_root(),
            "device_type": "ESP32 CYD"
        }

        # Add WiFi specific info if using WiFi
        if USE_WIFI:
            try:
                wlan = network.WLAN(network.STA_IF)
                if wlan.active():
                    network_info["wifi_ssid"] = WIFI_SSID
                    network_info["wifi_connected"] = wlan.isconnected()
            except:
                pass

        # Add CORS headers
        cors_headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        }
        response = HTTPResponse(200, "application/json", close=True, header=cors_headers)
        await response.send(writer)
        writer.write(json.dumps(network_info))
        await writer.drain()

    except Exception as e:
        print(f"Error in get_network_status: {e}")
        response = HTTPResponse(500, "application/json", close=True)
        await response.send(writer)
        writer.write(json.dumps({"error": f"Server error: {str(e)}"}))
        await writer.drain()

# ============================================================================
# ===( Static File Serving )=================================================
# ============================================================================

def get_content_type(filename):
    """Get MIME type based on file extension"""
    if filename.endswith('.html'):
        return 'text/html'
    elif filename.endswith('.js'):
        return 'application/javascript'
    elif filename.endswith('.css'):
        return 'text/css'
    elif filename.endswith('.ico'):
        return 'image/x-icon'
    elif filename.endswith('.png'):
        return 'image/png'
    elif filename.endswith('.jpg') or filename.endswith('.jpeg'):
        return 'image/jpeg'
    elif filename.endswith('.svg'):
        return 'image/svg+xml'
    elif filename.endswith('.json'):
        return 'application/json'
    else:
        return 'text/plain'

async def serve_file_chunked(writer, file_path, content_type):
    """Serve files with chunked delivery for memory efficiency"""
    try:
        # Get file size
        file_size = os.stat(file_path)[6]

        # Log file access
        if file_size > LARGE_FILE_THRESHOLD:
            print(f"Loading large file {file_path} ({file_size} bytes)")

        # Set response headers
        response = HTTPResponse(200, content_type, close=True)
        await response.send(writer)

        # Use the efficient sendfile function for chunked transfer
        await sendfile(writer, file_path)
        await writer.drain()

    except Exception as e:
        print(f"Error serving file {file_path}: {e}")
        response = HTTPResponse(500, "application/json", close=True)
        await response.send(writer)
        writer.write(json.dumps({"error": "file read error"}))
        await writer.drain()

@app.route("GET", "/")
async def serve_index(reader, writer, request):
    """Serve the main Angular application"""
    try:
        web_root = get_web_root()
        file_path = f'{web_root}/index.html'

        # Check if file exists
        try:
            os.stat(file_path)
            await serve_file_chunked(writer, file_path, 'text/html')
        except:
            # Fallback HTML if Angular files not found
            await serve_fallback_html(writer)
    except Exception as e:
        print(f"Error serving index: {e}")
        await serve_fallback_html(writer)

async def serve_fallback_html(writer):
    """Serve fallback HTML when Angular files are not found"""
    web_root = get_web_root()
    storage_type = "SD card" if USE_SD_CARD else "flash memory"
    fallback_html = f"""<!DOCTYPE html>
<html>
<head>
    <title>ESP32 CYD Server</title>
    <style>
        body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; }}
        .error {{ color: #f44336; }}
        .info {{ color: #2196F3; }}
        .device {{ color: #4CAF50; font-weight: bold; }}
    </style>
</head>
<body>
    <h1>ESP32 CYD Server Running</h1>
    <p class="device">Device: ESP32 Cheap Yellow Display</p>
    <p class="info">Angular application files not found on {storage_type}.</p>
    <p>Available API endpoints:</p>
    <ul style="display: inline-block; text-align: left;">
        <li><strong>GET /api/status</strong> - Get RGB LED and button status</li>
        <li><strong>POST /api/leds</strong> - Control RGB LEDs</li>
        <li><strong>GET /api/lamp</strong> - Get lamp status</li>
        <li><strong>POST /api/lamp</strong> - Control lamp settings</li>
        <li><strong>GET /api/network</strong> - Network configuration and status</li>
    </ul>
    <p class="info">Upload the Angular build files to {web_root}/ directory on the ESP32.</p>
    <p class="device">RGB LEDs: Red (Pin 4), Green (Pin 16), Blue (Pin 17)</p>
</body>
</html>"""

    response = HTTPResponse(200, 'text/html', close=True)
    await response.send(writer)
    writer.write(fallback_html)
    await writer.drain()

# Note: For catch-all routes, we need to handle them in a custom way
# since the simple HTTP server doesn't support path parameters like <path:filename>
# We'll implement this by checking the request path in a 404 handler

# Store the original 404 handler
original_routes = app._routes.copy()

# Override the server's route handling to add catch-all functionality
original_handle_request = app._handle_request

async def custom_handle_request(reader, writer):
    """Custom request handler with catch-all static file serving"""
    # Import required classes at the beginning to avoid import issues in exception handling
    from ahttpserver import url
    HTTPRequest = url.HTTPRequest
    InvalidRequest = url.InvalidRequest

    request = None  # Initialize request variable to prevent UnboundLocalError
    try:
        request_line = await asyncio.wait_for(reader.readline(), app.timeout)

        if request_line in [b"", b"\r\n"]:
            print(f"empty request line from {writer.get_extra_info('peername')[0]}")
            return

        print(f"request_line {request_line} from {writer.get_extra_info('peername')[0]}")

        try:
            request = HTTPRequest(request_line)
        except InvalidRequest as e:
            while True:
                # read and discard header fields
                if await asyncio.wait_for(reader.readline(), app.timeout) in [b"", b"\r\n"]:
                    break
            response = HTTPResponse(400, "text/plain", close=True)
            await response.send(writer)
            writer.write(repr(e).encode("utf-8"))
            return
        except Exception as e:
            # Handle any other exception during request parsing
            print(f"Error parsing request: {e}")
            response = HTTPResponse(400, "text/plain", close=True)
            await response.send(writer)
            writer.write(b"Bad Request")
            return

        while True:
            # read header fields and add name / value to dict 'header'
            line = await asyncio.wait_for(reader.readline(), app.timeout)

            if line in [b"", b"\r\n"]:
                break
            else:
                if line.find(b":") != -1:
                    name, value = line.split(b':', 1)
                    request.header[name] = value.strip()

        # Ensure request was successfully parsed before using it
        if request is not None:
            # search function which is connected to (method, path)
            func = app._routes.get((request.method, request.path))
            if func:
                await func(reader, writer, request)
            else:
                # Handle static files for any unmatched GET request
                if request.method == "GET" and not request.path.startswith("/api/"):
                    await serve_static_file(reader, writer, request)
                else:
                    # Return 404 for non-GET requests or API paths not found
                    response = HTTPResponse(404, "application/json", close=True)
                    await response.send(writer)
                    writer.write(json.dumps({"error": "not found"}))
        else:
            # Request parsing failed, send error response
            response = HTTPResponse(400, "text/plain", close=True)
            await response.send(writer)
            writer.write(b"Bad Request")

    except asyncio.TimeoutError:
        pass
    except Exception as e:
        import errno
        if type(e) is OSError and e.errno == errno.ECONNRESET:  # connection reset by client
            pass
        else:
            print(f"Request handling error: {e}")
    finally:
        await writer.drain()
        writer.close()
        await writer.wait_closed()

async def serve_static_file(reader, writer, request):
    """Serve static files for any path not handled by API routes"""
    try:
        web_root = get_web_root()
        # Remove leading slash and clean the path
        filename = request.path[1:] if request.path.startswith('/') else request.path

        # Prevent directory traversal
        if '..' in filename or filename.startswith('/'):
            response = HTTPResponse(403, "application/json", close=True)
            await response.send(writer)
            writer.write(json.dumps({"error": "forbidden"}))
            await writer.drain()
            return

        file_path = f'{web_root}/{filename}'

        # Check if file exists
        try:
            os.stat(file_path)
            # Determine content type based on file extension
            content_type = get_content_type(filename)
            await serve_file_chunked(writer, file_path, content_type)
        except:
            # If file not found, serve the main index.html for Angular routing
            try:
                index_path = f'{web_root}/index.html'
                os.stat(index_path)
                await serve_file_chunked(writer, index_path, 'text/html')
            except:
                response = HTTPResponse(404, "application/json", close=True)
                await response.send(writer)
                writer.write(json.dumps({"error": "file not found"}))
                await writer.drain()

    except Exception as e:
        print(f"Error serving static file {request.path}: {e}")
        response = HTTPResponse(500, "application/json", close=True)
        await response.send(writer)
        writer.write(json.dumps({"error": "server error"}))
        await writer.drain()

# Replace the server's request handler with our custom one
app._handle_request = custom_handle_request

# ============================================================================
# ===( Memory Management )====================================================
# ============================================================================

def print_memory_info():
    """Print current memory usage for debugging"""
    try:
        import micropython
        print("Memory info:")
        micropython.mem_info()
    except:
        pass

async def memory_management_task():
    """Background task for memory management"""
    while True:
        gc.collect()
        gc.threshold(gc.mem_free() // 4 + gc.mem_alloc())
        await asyncio.sleep(5)

# ============================================================================
# ===( Server Startup )=======================================================
# ============================================================================

async def main():
    """Main server function"""
    print("Setting up ESP32 CYD Async HTTP Server...")

    # Set up server configuration
    web_root = get_web_root()

    print("Server configuration:")
    print(f"  Device: ESP32 Cheap Yellow Display (CYD)")
    print(f"  Network: {'WiFi' if USE_WIFI else 'Ethernet'}")
    print(f"  IP Address: {net_cfg[0]}")
    print(f"  Port: 80")
    print(f"  Web storage: {'SD Card' if USE_SD_CARD else 'Flash Memory'}")
    print(f"  Root path: {web_root}")
    print("API endpoints:")
    print("  GET  /api/status   - RGB LED and button status")
    print("  POST /api/leds     - Control RGB LEDs")
    print("  GET  /api/lamp     - Get lamp status")
    print("  POST /api/lamp     - Control lamp settings")
    print("  GET  /api/network  - Network configuration and status")
    print("Static files served with async chunked streaming")
    print("RGB LEDs: Red (Pin 4), Green (Pin 16), Blue (Pin 17)")

    # Print initial memory info
    print_memory_info()

    # Force garbage collection before starting
    gc.collect()

    try:
        # Start the async HTTP server
        print("Starting ESP32 CYD Async HTTP Server...")

        # Create background tasks
        memory_task = asyncio.create_task(memory_management_task())
        server_task = asyncio.create_task(app.start())

        print(f"ESP32 CYD Server running on http://{net_cfg[0]}/")
        print("Server is using asyncio for efficient memory usage")

        # Wait for tasks to complete (they run forever)
        await asyncio.gather(memory_task, server_task)

    except KeyboardInterrupt:
        print("Keyboard interrupt received")
    except Exception as e:
        print(f"Server error: {e}")
        print_memory_info()
    finally:
        print("Stopping server...")
        cleanup_leds()  # Turn off all LEDs
        try:
            await app.stop()
        except:
            pass
        print("ESP32 CYD Server stopped")

def run_server():
    """Entry point to run the server"""
    try:
        # Set up exception handler for asyncio
        def handle_exception(loop, context):
            print("Asyncio exception:", context)
            import sys
            if 'exception' in context:
                sys.print_exception(context['exception'])

        loop = asyncio.get_event_loop()
        loop.set_exception_handler(handle_exception)

        # Run the main server
        loop.run_until_complete(main())

    except KeyboardInterrupt:
        print("Server interrupted by user")
    except Exception as e:
        print(f"Fatal server error: {e}")
    finally:
        # Clean up
        cleanup_leds()
        try:
            asyncio.new_event_loop()
        except:
            pass

if __name__ == '__main__':
    run_server()
