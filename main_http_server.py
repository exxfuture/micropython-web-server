#!/usr/bin/env python3
"""
MCU HTTP Server using MicroPython-HTTP-Server (ahttpserver)
Async HTTP server implementation for better memory efficiency

This server provides REST API endpoints for controlling LEDs, buttons, and lamp systems
on a regular MCU board with static file serving for Angular web applications.

Features:
- Async HTTP server with low memory footprint
- 3 LED control (P006, P007, P008)
- 2 Button monitoring (P009, P010)
- 6 PWM lamp control with wave patterns (P111-P115, P608)
- Network configuration (WiFi/Ethernet)
- Static file serving with chunked delivery
- Memory-efficient operation using asyncio

Author: Generated for MCU project
"""

import os, sys, time, network, machine, json
import gc
import uasyncio as asyncio

from machine import Pin, PWM, Timer

# Import the async HTTP server
from ahttpserver import HTTPResponse, HTTPServer, sendfile

# ============================================================================
# ===( Configuration Constants )=============================================
# ============================================================================

# File serving configuration - easily adjustable thresholds
LARGE_FILE_THRESHOLD = 50000    # 50KB - threshold for logging large file access
HUGE_FILE_THRESHOLD = 300000    # 300KB - threshold for network optimization headers
CHUNK_SIZE = 32768              # 32KB - chunk size for fallback chunked reading

# Web files storage configuration
USE_SD_CARD = True              # True = use SD card (/sd/www), False = use flash memory (/www)
WEB_ROOT_SD = "/sd/www"         # Path for web files on SD card
WEB_ROOT_FLASH = "/www"         # Path for web files on flash memory

# Network connection configuration
USE_WIFI = False                # True = use WiFi, False = use Ethernet (LAN)
WIFI_SSID = "Test"   # WiFi network name
WIFI_PASSWORD = "Test"  # WiFi password

# ============================================================================
# ===( Hardware Control Logic - copied from main.py )======================
# ============================================================================

# Lamp control state variables
power = "OFF"   # "ON","OFF","PAUSE"
state = 0   # Will be set to ST_OFF after constants are defined
pwm = 10    # the pwm is between int 1-100%
wave_speed = 20
timer_sw = 10   # SEC
timer_sw_buf = timer_sw

# PWM Pin Setup for lamp control
a = machine.PWM(machine.Pin('P111'))
b = machine.PWM(machine.Pin('P112'))
c = machine.PWM(machine.Pin('P113'))
d = machine.PWM(machine.Pin('P114'))
e = machine.PWM(machine.Pin('P115'))
f = machine.PWM(machine.Pin('P608'))

# STATES
ST_OFF = 0
ST_STATIC = 1
ST_WAVE = 2
ST_PAUSE = 3
ST_PULSE = 4

# Initialize state properly now that constants are defined
state = ST_OFF

# EVENTS
EV_ON_OFF = 0
EV_PAUSE = 1
EV_TOGGLE_MODE = 2
EV_EX = 3
EV_UPDATE = 4

wave_tim_buf = 1

def zatim(timer):
    global timer_sw_buf
    global wave_tim_buf

    if timer_sw_buf != 0:
        timer_sw_buf = timer_sw_buf - 1
        if timer_sw_buf == 0:
            stmachine(EV_EX)
    wave_tim()

tim = Timer(-1)
tim.init(period=1000, mode=Timer.PERIODIC, callback=zatim)

def stop_pwm():
    a.freq(0)
    b.freq(0)
    c.freq(0)
    d.freq(0)
    e.freq(0)
    f.freq(0)

def start_pwm():
    a.freq(1000)
    a.duty(pwm)
    b.freq(1000)
    b.duty(pwm)
    c.freq(1000)
    c.duty(pwm)
    d.freq(1000)
    d.duty(pwm)
    e.freq(1000)
    e.duty(pwm)
    f.freq(1000)
    f.duty(pwm)

def stmachine(event):
    global state
    global mode
    global timer_sw_buf
    global timer_sw
    global wave_speed
    global pwm

    if state == ST_OFF:
       stop_pwm()

    elif state == ST_STATIC:
        if event == EV_UPDATE:
            timer_sw_buf = timer_sw
            start_pwm()

        elif event == EV_EX:
            state = ST_OFF
            stop_pwm()

    elif state == ST_WAVE:
        if event == EV_UPDATE:
            timer_sw_buf = timer_sw
            start_pwm()

        elif event == EV_EX:
            state = ST_OFF
            stop_pwm()

    elif state == EV_PAUSE:
            stop_pwm()

def wave_tim():
    global wave_tim_buf
    global state

    if state != ST_WAVE:
        return

    if wave_tim_buf == 0:
        a.freq(1000)
        a.duty(pwm)
        b.freq(0)
        c.freq(0)
        d.freq(0)
        e.freq(0)
        f.freq(0)
        print("wave 0")

    elif wave_tim_buf == 1:
        a.freq(0)
        b.freq(1000)
        b.duty(pwm)
        c.freq(0)
        d.freq(0)
        e.freq(0)
        f.freq(0)
        print("wave 1")

    elif wave_tim_buf == 2:
        a.freq(0)
        b.freq(0)
        c.freq(1000)
        c.duty(pwm)
        d.freq(0)
        e.freq(0)
        f.freq(0)
        print("wave 2")

    elif wave_tim_buf == 3:
        a.freq(0)
        b.freq(0)
        c.freq(0)
        d.freq(1000)
        d.duty(pwm)
        e.freq(0)
        f.freq(0)
        print("wave 3")

    elif wave_tim_buf == 4:
        a.freq(0)
        b.freq(0)
        c.freq(0)
        d.freq(0)
        e.freq(1000)
        e.duty(pwm)
        f.freq(0)
        print("wave 4")

    elif wave_tim_buf == 5:
        a.freq(0)
        b.freq(0)
        c.freq(0)
        d.freq(0)
        e.freq(0)
        f.freq(1000)
        f.duty(pwm)
        print("wave 5")

    wave_tim_buf = wave_tim_buf + 1
    if wave_tim_buf > 5:
        wave_tim_buf = 0

# Initialize state machine
stmachine(EV_UPDATE)

# ============================================================================
# ===( Web Files Storage Configuration )=====================================
# ============================================================================

def get_web_root():
    """Get the web root path based on configuration and availability"""
    global web_storage_ready
    if USE_SD_CARD and web_storage_ready:
        return WEB_ROOT_SD
    else:
        return WEB_ROOT_FLASH

def setup_web_storage():
    """Setup web file storage based on configuration"""
    global USE_SD_CARD  # Allow modification for fallback

    if USE_SD_CARD:
        # Mount SD card and setup paths
        try:
            sd = machine.SDCard()
            os.mount(sd, "/sd")
            if "/sd/lib" not in sys.path:
                sys.path.insert(0, "/sd/lib")
            print(f"SD card mounted successfully. Web files will be served from: {WEB_ROOT_SD}")
            return True
        except Exception as e:
            print(f"Failed to mount SD card: {e}")
            print(f"Automatically falling back to flash memory: {WEB_ROOT_FLASH}")
            USE_SD_CARD = False  # Update configuration for fallback
            return False
    else:
        print(f"Using flash memory for web files: {WEB_ROOT_FLASH}")
        return True

# Setup web storage
web_storage_ready = setup_web_storage()

# ============================================================================
# ===( Network Configuration )===============================================
# ============================================================================

def setup_ethernet():
    """Setup Ethernet (LAN) connection"""
    try:
        lan = network.LAN()
        lan.active(True)
        timeout = 10
        print("Connecting to Ethernet...")

        while timeout > 0:
            ip = lan.ifconfig()[0]
            if ip != '0.0.0.0':
                print(f"Ethernet connected successfully")
                return lan.ifconfig()
            time.sleep(1)
            timeout -= 1

        print("Ethernet connection timeout")
        return None
    except Exception as e:
        print(f"Ethernet setup failed: {e}")
        return None

def setup_wifi():
    """Setup WiFi connection"""
    try:
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)

        print(f"Connecting to WiFi network: {WIFI_SSID}")
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)

        timeout = 20  # WiFi may take longer to connect
        while timeout > 0:
            if wlan.isconnected():
                config = wlan.ifconfig()
                print(f"WiFi connected successfully")
                return config
            time.sleep(1)
            timeout -= 1

        print("WiFi connection timeout")
        return None
    except Exception as e:
        print(f"WiFi setup failed: {e}")
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

# --- Hardware: 3 LEDs + 2 Buttons ---
LED1 = machine.Pin("P006", machine.Pin.OUT)
LED2 = machine.Pin("P007", machine.Pin.OUT)
LED3 = machine.Pin("P008", machine.Pin.OUT)

BTN1 = machine.Pin("P009", machine.Pin.IN, machine.Pin.PULL_UP)
BTN2 = machine.Pin("P010", machine.Pin.IN, machine.Pin.PULL_UP)

print("MCU hardware initialized:")
print(f"  LEDs: P006, P007, P008")
print(f"  Buttons: P009, P010")
print(f"  Lamp PWM: P111-P115, P608")

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
            "1": LED1.value(),
            "2": LED2.value(),
            "3": LED3.value(),
        },
        "buttons": {
            "1": BTN1.value(),  # 1 = not pressed (pull-up), 0 = pressed
            "2": BTN2.value(),
        }
    }

    response = HTTPResponse(200, "application/json", close=True)
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
        val = 1 if body.get("value") else 0

    except Exception as e:
        response = HTTPResponse(400, "application/json", close=True)
        await response.send(writer)
        writer.write(json.dumps({"error": "bad request"}))
        await writer.drain()
        return

    if led == 1:
        LED1.value(val)
    elif led == 2:
        LED2.value(val)
    elif led == 3:
        LED3.value(val)
    else:
        response = HTTPResponse(400, "application/json", close=True)
        await response.send(writer)
        writer.write(json.dumps({"error": "invalid led"}))
        await writer.drain()
        return

    response_data = {"ok": True, "led": led, "value": val}
    response = HTTPResponse(200, "application/json", close=True)
    await response.send(writer)
    writer.write(json.dumps(response_data))
    await writer.drain()

@app.route("GET", "/api/lamp")
async def api_get_lamp_status(reader, writer, request):
    """Get current lamp status"""
    global pwm, timer_sw, wave_speed, state, timer_sw_buf

    # Convert state to readable format
    power = "OFF"
    mode = "STATIC"

    if state == ST_OFF:
        power = "OFF"
    elif state == ST_PAUSE:
        power = "PAUSE"
    elif state in [ST_STATIC, ST_WAVE, ST_PULSE]:
        power = "ON"
        if state == ST_STATIC:
            mode = "STATIC"
        elif state == ST_WAVE:
            mode = "WAVE"
        elif state == ST_PULSE:
            mode = "PULSE"

    # Return current lamp status in the expected format
    data = {
        "nearInfraredStatus": {
            "power": power,
            "mode": mode,
            "brightness": pwm,
            "speed": wave_speed,
            "timer": timer_sw,
            "elapsedTime": 0  # You can implement elapsed time tracking if needed
        },
        "redLightStatus": {
            "power": "OFF",
            "mode": "STATIC",
            "brightness": 0,
            "speed": 20,
            "timer": 10,
            "elapsedTime": 0
        }
    }

    response = HTTPResponse(200, "application/json", close=True)
    await response.send(writer)
    writer.write(json.dumps(data))
    await writer.drain()

@app.route("POST", "/api/lamp")
async def api_set_lamp(reader, writer, request):
    """Set lamp configuration"""
    global pwm, timer_sw, wave_speed, state, timer_sw_buf

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

        # Validate that the request contains nearInfraredStatus
        if not request_data or "nearInfraredStatus" not in request_data:
            print("ERROR: Missing nearInfraredStatus in request body")
            response = HTTPResponse(400, "application/json", close=True)
            await response.send(writer)
            writer.write(json.dumps({"error": "Missing nearInfraredStatus in request body"}))
            await writer.drain()
            return

        # Extract nearInfraredStatus object
        near_ir_st = request_data["nearInfraredStatus"]
        print("nearInfraredStatus:", near_ir_st)

        # Validate required fields
        if not isinstance(near_ir_st, dict):
            print("Error: nearInfraredStatus must be an object")
            response = HTTPResponse(400, "application/json", close=True)
            await response.send(writer)
            writer.write(json.dumps({"error": "nearInfraredStatus must be an object"}))
            await writer.drain()
            return

        # Extract lamp parameters with validation
        power = near_ir_st.get("power")
        mode = near_ir_st.get("mode")
        brightness = near_ir_st.get("brightness")
        speed = near_ir_st.get("speed")
        timer = near_ir_st.get("timer")
        elapsed_time = near_ir_st.get("elapsedTime", 0)

        # Normalize and validate power (case-insensitive)
        power = power.upper() if power else "OFF"
        if power not in ["ON", "OFF", "PAUSE"]:
            print(f"Error: Invalid power value: {power}")
            response = HTTPResponse(400, "application/json", close=True)
            await response.send(writer)
            writer.write(json.dumps({"error": "power must be 'ON', 'OFF', or 'PAUSE'"}))
            await writer.drain()
            return

        # Normalize and validate mode (case-insensitive)
        mode = mode.upper() if mode else "STATIC"
        if mode not in ["STATIC", "WAVE", "PULSE"]:
            print(f"Error: Invalid mode value: {mode}")
            response = HTTPResponse(400, "application/json", close=True)
            await response.send(writer)
            writer.write(json.dumps({"error": "mode must be 'STATIC', 'WAVE', or 'PULSE'"}))
            await writer.drain()
            return

        # Validate brightness (0-100)
        if not isinstance(brightness, (int, float)) or brightness < 0 or brightness > 100:
            print(f"Error: Invalid brightness value: {brightness}")
            response = HTTPResponse(400, "application/json", close=True)
            await response.send(writer)
            writer.write(json.dumps({"error": "brightness must be a number between 0-100"}))
            await writer.drain()
            return

        # Validate speed (0-100 seconds, 0 means no wave/pulse effect)
        if not isinstance(speed, (int, float)) or speed < 0 or speed > 100:
            print(f"Error: Invalid speed value: {speed}")
            response = HTTPResponse(400, "application/json", close=True)
            await response.send(writer)
            writer.write(json.dumps({"error": "speed must be a number between 0-100 seconds"}))
            await writer.drain()
            return

        # Validate timer (must be positive)
        if not isinstance(timer, (int, float)) or timer < 0:
            print(f"Error: Invalid timer value: {timer}")
            response = HTTPResponse(400, "application/json", close=True)
            await response.send(writer)
            writer.write(json.dumps({"error": "timer must be a positive number"}))
            await writer.drain()
            return

        # Update global variables
        pwm = int(brightness)
        wave_speed = int(speed)
        timer_sw = int(timer)
        timer_sw_buf = timer_sw

        print(f"Updated globals: pwm={pwm}, wave_speed={wave_speed}, timer_sw={timer_sw}")

        # Set state based on power and mode
        if power == "OFF":
            state = ST_OFF
        elif power == "PAUSE":
            state = ST_PAUSE
        elif power == "ON":
            if mode == "STATIC":
                state = ST_STATIC
            elif mode == "WAVE":
                state = ST_WAVE
            elif mode == "PULSE":
                state = ST_PULSE
            else:
                state = ST_STATIC  # fallback

        print(f"State set to: {state}")

        # Trigger state machine update
        stmachine(EV_UPDATE)

        # Return the processed values
        response_data = {
            "ok": True,
            "nearInfraredStatus": {
                "power": power,
                "mode": mode,
                "brightness": int(brightness),
                "speed": int(speed),
                "timer": int(timer),
                "elapsedTime": elapsed_time
            }
        }

        response = HTTPResponse(200, "application/json", close=True)
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
            "device_type": "MCU"
        }

        # Add WiFi specific info if using WiFi
        if USE_WIFI:
            try:
                wlan = network.WLAN(network.STA_IF)
                if wlan.active():
                    network_info["wifi_ssid"] = WIFI_SSID
                    network_info["wifi_connected"] = wlan.isconnected()
                    if wlan.isconnected():
                        network_info["wifi_signal_strength"] = "Available"  # Could add RSSI if supported
            except:
                pass

        response = HTTPResponse(200, "application/json", close=True)
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
    <title>MCU Server</title>
    <style>
        body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; }}
        .error {{ color: #f44336; }}
        .info {{ color: #2196F3; }}
    </style>
</head>
<body>
    <h1>MCU Server Running</h1>
    <p class="info">Angular application files not found on {storage_type}.</p>
    <p>Available API endpoints:</p>
    <ul style="display: inline-block; text-align: left;">
        <li><strong>GET /api/status</strong> - Get LED and button status</li>
        <li><strong>POST /api/leds</strong> - Control LEDs</li>
        <li><strong>GET /api/lamp</strong> - Get lamp status</li>
        <li><strong>POST /api/lamp</strong> - Control lamp settings</li>
        <li><strong>GET /api/network</strong> - Network configuration and status</li>
    </ul>
    <p class="info">Upload the Angular build files to {web_root}/ directory on the MCU.</p>
    <p>Hardware: 3 LEDs (P006-P008), 2 Buttons (P009-P010), 6 PWM Lamps (P111-P115, P608)</p>
</body>
</html>"""

    response = HTTPResponse(200, 'text/html', close=True)
    await response.send(writer)
    writer.write(fallback_html)
    await writer.drain()

# Custom request handler for static file serving
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
    print("Setting up MCU Async HTTP Server...")

    # Set up server configuration
    web_root = get_web_root()

    print("Server configuration:")
    print(f"  Device: MCU with 6 PWM Lamp Control")
    print(f"  Network: {'WiFi' if USE_WIFI else 'Ethernet'}")
    print(f"  IP Address: {net_cfg[0]}")
    print(f"  Port: 80")
    print(f"  Web storage: {'SD Card' if USE_SD_CARD else 'Flash Memory'}")
    print(f"  Root path: {web_root}")
    print("API endpoints:")
    print("  GET  /api/status   - LED and button status")
    print("  POST /api/leds     - Control LEDs")
    print("  GET  /api/lamp     - Get lamp status")
    print("  POST /api/lamp     - Control lamp settings")
    print("  GET  /api/network  - Network configuration and status")
    print("Static files served with async chunked streaming")
    print("Hardware: 3 LEDs (P006-P008), 2 Buttons (P009-P010), 6 PWM Lamps (P111-P115, P608)")

    # Print initial memory info
    print_memory_info()

    # Force garbage collection before starting
    gc.collect()

    try:
        # Start the async HTTP server
        print("Starting MCU Async HTTP Server...")

        # Create background tasks
        memory_task = asyncio.create_task(memory_management_task())
        server_task = asyncio.create_task(app.start())

        print(f"MCU Server running on http://{net_cfg[0]}/")
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
        try:
            await app.stop()
        except:
            pass
        print("MCU Server stopped")

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
        try:
            asyncio.new_event_loop()
        except:
            pass

if __name__ == '__main__':
    run_server()
