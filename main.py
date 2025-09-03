import os, sys, time, network, machine, ujson
import gc

from machine import Pin, PWM, Timer

# Import MicroWebSrv2 from local folder
from MicroWebSrv2.MicroWebSrv2 import *

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
WIFI_SSID = "YourWiFiNetwork"   # WiFi network name
WIFI_PASSWORD = "YourPassword"  # WiFi password

#export interface LampStatus {
#  power: string; "ON","OFF","PAUSE"
#  mode: string; "STATIC","WAVE", "PULSE"
#  brightness: number; 0-100
#  speed: number; sec 1-100sec - олко време вълната начало / край.
#  timer: number; sec
#  elapsedTime: number; sec
#}

#export interface LampStatusRequest {
#  redLightStatus: LampStatus;
#  nearInfraredStatus: LampStatus;
#  }

# ============================================================================
# ===( Hardware Control Logic - copied from mcu_server_m.py )===============
# ============================================================================

#STRUCT...
power = "OFF"   # "ON","OFF","PAUSE"
state = 0   # Will be set to ST_OFF after constants are defined
pwm = 10    #the pwm is between int 1-100%
wave_speed = 20
timer_sw = 10   # SEC
timer_sw_buf = timer_sw

# PWM Pin Setup
a= machine.Pin(Pin('P111'),Pin.OUT)
a = machine.PWM(machine.Pin('P111'))

b= machine.Pin(Pin('P112'),Pin.OUT)
b = machine.PWM(machine.Pin('P112'))

c= machine.Pin(Pin('P113'),Pin.OUT)
c = machine.PWM(machine.Pin('P113'))

d= machine.Pin(Pin('P114'),Pin.OUT)
d = machine.PWM(machine.Pin('P114'))

e = machine.Pin(Pin('P115'),Pin.OUT)
e = machine.PWM(machine.Pin('P115'))

f = machine.Pin(Pin('P608'),Pin.OUT)
f = machine.PWM(machine.Pin('P608'))

#STATES
ST_OFF = 0
ST_STATIC = 1
ST_WAVE = 2
ST_PAUSE = 3
ST_PULSE = 4

# Initialize state properly now that constants are defined
state = ST_OFF

#EVENTS
EV_ON_OFF = 0
EV_PAUSE = 1
EV_TOGGLE_MODE = 2
EV_EX = 3
EV_UPDATE = 4

wave_tim_buf = 1

def zatim (timer):
    global timer_sw_buf
    global wave_tim_buf

    if timer_sw_buf != 0 :
        timer_sw_buf = timer_sw_buf - 1
        if timer_sw_buf == 0 :
            stmachine(EV_EX)
    wave_tim()

tim = Timer(-1)
tim.init(period=1000 , mode=Timer.PERIODIC, callback=zatim)

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

def stmachine (event) :
    global state
    global mode
    global timer_sw_buf
    global timer_sw
    global wave_speed
    global pwm

    if state == ST_OFF :
       stop_pwm()

    elif state == ST_STATIC :
        if event == EV_UPDATE:
            timer_sw_buf = timer_sw
            start_pwm()

        elif event == EV_EX:
            state = ST_OFF
            stop_pwm()


    elif state == ST_WAVE :
        if event == EV_UPDATE:
            timer_sw_buf = timer_sw
            start_pwm()

        elif event == EV_EX:
            state = ST_OFF
            stop_pwm()

    elif state == EV_PAUSE :
            stop_pwm()

def wave_tim():
    global wave_tim_buf
    global state

    if state != ST_WAVE:
        return

    if 	wave_tim_buf == 0 :
        a.freq(1000)
        a.duty(pwm)
        b.freq(0)
        c.freq(0)
        d.freq(0)
        e.freq(0)
        f.freq(0)
        print("wave 0")

    elif wave_tim_buf==1:
        a.freq(0)
        b.freq(1000)
        b.duty(pwm)
        c.freq(0)
        d.freq(0)
        e.freq(0)
        f.freq(0)
        print("wave 1")

    elif wave_tim_buf==2:
        a.freq(0)
        b.freq(0)
        c.freq(1000)
        c.duty(pwm)
        d.freq(0)
        e.freq(0)
        f.freq(0)
        print("wave 2")

    elif wave_tim_buf==3:
        a.freq(0)
        b.freq(0)
        c.freq(0)
        d.freq(1000)
        d.duty(pwm)
        e.freq(0)
        f.freq(0)
        print("wave 3")

    elif wave_tim_buf==4:
        a.freq(0)
        b.freq(0)
        c.freq(0)
        d.freq(0)
        e.freq(1000)
        e.duty(pwm)
        f.freq(0)
        print("wave 4")

    elif wave_tim_buf==5:
        a.freq(0)
        b.freq(0)
        c.freq(0)
        d.freq(0)
        e.freq(0)
        f.freq(1000)
        f.duty(pwm)
        print("wave 5")

    wave_tim_buf=wave_tim_buf+1
    if wave_tim_buf>5:
        wave_tim_buf=0

# Initialize state machine
stmachine(EV_UPDATE)

# ============================================================================
# ===( Web Files Storage Configuration )=====================================
# ============================================================================

def list_sd_card_contents(path="/sd", level=0, max_level=10):
    """Recursively list all contents of SD card including directories and files"""
    if level > max_level:
        return

    try:
        items = os.listdir(path)
        for item in sorted(items):
            item_path = f"{path}/{item}" if path != "/" else f"/{item}"
            indent = "  " * level

            try:
                stat_info = os.stat(item_path)
                if stat_info[0] & 0x4000:  # Directory
                    print(f"{indent}[DIR]  {item}/")
                    list_sd_card_contents(item_path, level + 1, max_level)
                else:  # File
                    file_size = stat_info[6]
                    print(f"{indent}[FILE] {item} ({file_size} bytes)")
            except Exception as e:
                print(f"{indent}[ERR]  {item} (error: {e})")

    except Exception as e:
        print(f"Error listing {path}: {e}")

def print_sd_card_contents():
    """Print complete SD card contents if SD card is available"""
    print("\n" + "="*60)
    print("SD CARD CONTENTS")
    print("="*60)

    try:
        # Check if SD card is mounted
        os.stat("/sd")
        print("SD card is mounted at /sd")
        list_sd_card_contents("/sd")
    except:
        print("SD card not mounted or not available")

    print("="*60 + "\n")

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

# ============================================================================
# ===( API Endpoints using MicroWebSrv2 )====================================
# ============================================================================

@WebRoute(GET, '/api/status')
def api_status(microWebSrv2, request):
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
    request.Response.ReturnOkJSON(data)

@WebRoute(POST, '/api/leds')
def api_set_led(microWebSrv2, request):
    """Control LEDs"""
    try:
        body = request.GetPostedJSONObject()
        if not body:
            request.Response.ReturnJSON(400, {"error": "bad request"})
            return

        led = int(body.get("led", 0))
        val = 1 if body.get("value") else 0
    except Exception as e:
        request.Response.ReturnJSON(400, {"error": "bad request"})
        return

    if led == 1:
        LED1.value(val)
    elif led == 2:
        LED2.value(val)
    elif led == 3:
        LED3.value(val)
    else:
        request.Response.ReturnJSON(400, {"error": "invalid led"})
        return

    request.Response.ReturnOkJSON({"ok": True, "led": led, "value": val})

@WebRoute(GET, '/api/lamp')
def api_get_lamp_status(microWebSrv2, request):
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
    request.Response.ReturnOkJSON(data)

@WebRoute(POST, '/api/lamp')
def api_set_lamp(microWebSrv2, request):
    """Set lamp configuration"""
    global pwm, timer_sw, wave_speed, state, timer_sw_buf

    try:
        # Parse the request body - expecting LampStatusRequest format
        body = request.GetPostedJSONObject()
        if not body:
            request.Response.ReturnJSON(400, {"error": "Missing request body"})
            return

        print("=== LAMP REQUEST DEBUG ===")
        print("Full request body:", body)
        print("Body type:", type(body))
        print("Body keys:", list(body.keys()) if isinstance(body, dict) else "Not a dict")

        # Handle the actual request structure - data is wrapped in "request" object
        if "request" in body:
            # Angular is sending: {"request": {"nearInfraredStatus": {...}}}
            request_data = body["request"]
            print("Found 'request' wrapper, extracting data:", request_data)
        else:
            # Direct format: {"nearInfraredStatus": {...}}
            request_data = body
            print("No 'request' wrapper, using body directly")

        print("Request data keys:", list(request_data.keys()) if isinstance(request_data, dict) else "Not a dict")

        # Validate that the request contains nearInfraredStatus
        if not request_data or "nearInfraredStatus" not in request_data:
            print("ERROR: Missing nearInfraredStatus in request body")
            print("Available keys:", list(request_data.keys()) if isinstance(request_data, dict) else "None")
            request.Response.ReturnJSON(400, {"error": "Missing nearInfraredStatus in request body"})
            return

        # Extract nearInfraredStatus object
        near_ir_st = request_data["nearInfraredStatus"]
        print("nearInfraredStatus:", near_ir_st)

        # Validate required fields
        if not isinstance(near_ir_st, dict):
            print("Error: nearInfraredStatus must be an object")
            request.Response.ReturnJSON(400, {"error": "nearInfraredStatus must be an object"})
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
            request.Response.ReturnJSON(400, {"error": "power must be 'ON', 'OFF', or 'PAUSE'"})
            return

        # Normalize and validate mode (case-insensitive)
        mode = mode.upper() if mode else "STATIC"
        if mode not in ["STATIC", "WAVE", "PULSE"]:
            print(f"Error: Invalid mode value: {mode}")
            request.Response.ReturnJSON(400, {"error": "mode must be 'STATIC', 'WAVE', or 'PULSE'"})
            return

        # Validate brightness (0-100)
        if not isinstance(brightness, (int, float)) or brightness < 0 or brightness > 100:
            print(f"Error: Invalid brightness value: {brightness}")
            request.Response.ReturnJSON(400, {"error": "brightness must be a number between 0-100"})
            return

        # Validate speed (0-100 seconds, 0 means no wave/pulse effect)
        if not isinstance(speed, (int, float)) or speed < 0 or speed > 100:
            print(f"Error: Invalid speed value: {speed}")
            request.Response.ReturnJSON(400, {"error": "speed must be a number between 0-100 seconds"})
            return

        # Validate timer (must be positive)
        if not isinstance(timer, (int, float)) or timer < 0:
            print(f"Error: Invalid timer value: {timer}")
            request.Response.ReturnJSON(400, {"error": "timer must be a positive number"})
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
        request.Response.ReturnOkJSON(response_data)

    except Exception as e:
        print(f"Error in set_lamp: {e}")
        request.Response.ReturnJSON(500, {"error": f"Server error: {str(e)}"})

@WebRoute(GET, '/api/network')
def api_get_network_status(microWebSrv2, request):
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
            "web_root": get_web_root()
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

        request.Response.ReturnOkJSON(network_info)

    except Exception as e:
        print(f"Error in get_network_status: {e}")
        request.Response.ReturnJSON(500, {"error": f"Server error: {str(e)}"})

# ============================================================================
# ===( Static File Serving with Chunked Delivery )===========================
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

def serve_file_chunked(request, file_path, content_type):
    """Serve files with chunked delivery for memory efficiency"""
    try:
        # Get file size
        file_size = os.stat(file_path)[6]

        # Log file access
        if file_size > LARGE_FILE_THRESHOLD:
            print(f"Loading large file {file_path} ({file_size} bytes) - reading entire file at once")

        # Read entire file at once - we tested that MCU can allocate up to 7.5MB
        try:
            with open(file_path, 'rb') as f:
                content = f.read()

            print(f"Successfully loaded {len(content)} bytes into memory")

            # Set content type and headers
            request.Response.ContentType = content_type

            # For large files, add network optimization headers
            if len(content) > HUGE_FILE_THRESHOLD:
                print(f"Large file ({len(content)} bytes) - optimizing network transmission")
                request.Response.SetHeader('Connection', 'close')  # Close connection after transfer
                request.Response.SetHeader('Accept-Ranges', 'none')  # Disable range requests to simplify

            request.Response.SetHeader('Cache-Control', 'public, max-age=3600')
            request.Response.Return(200, content)

        except MemoryError as e:
            print(f"Memory error loading {file_path}: {e}")
            print("Falling back to chunked reading...")

            # Fallback to chunked reading only if memory allocation fails
            try:
                content_parts = []
                bytes_read = 0

                with open(file_path, 'rb') as f:
                    while bytes_read < file_size:
                        remaining = min(CHUNK_SIZE, file_size - bytes_read)
                        chunk = f.read(remaining)

                        if not chunk:
                            break

                        content_parts.append(chunk)
                        bytes_read += len(chunk)

                        # Less frequent garbage collection
                        if len(content_parts) % 10 == 0:
                            gc.collect()

                    # Join all parts
                    content = b''.join(content_parts)
                    content_parts.clear()
                    gc.collect()

                request.Response.ContentType = content_type
                request.Response.SetHeader('Cache-Control', 'public, max-age=3600')
                request.Response.Return(200, content)

            except Exception as fallback_error:
                print(f"Fallback chunked reading also failed: {fallback_error}")
                gc.collect()
                request.Response.ReturnJSON(500, {"error": "file read error"})

        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
            gc.collect()
            request.Response.ReturnJSON(500, {"error": "file read error"})

    except Exception as e:
        print(f"Error serving file {file_path}: {e}")
        # Force garbage collection on error
        gc.collect()
        request.Response.ReturnJSON(500, {"error": "file access error"})

@WebRoute(GET, '/')
def serve_index(microWebSrv2, request):
    """Serve the main Angular application"""
    try:
        web_root = get_web_root()
        serve_file_chunked(request, f'{web_root}/index.html', 'text/html')
    except:
        # Fallback HTML if Angular files not found
        web_root = get_web_root()
        storage_type = "SD card" if USE_SD_CARD else "flash memory"
        fallback_html = f"""
        <!DOCTYPE html>
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
                <li><strong>POST /api/leds</strong> - Control LEDs (JSON: {{"led": 1-3, "value": true/false}})</li>
                <li><strong>GET /api/lamp</strong> - Get lamp status</li>
                <li><strong>POST /api/lamp</strong> - Control lamp settings</li>
            </ul>
            <p class="info">Upload the Angular build files to {web_root}/ directory on the MCU.</p>
        </body>
        </html>
        """
        request.Response.ContentType = 'text/html'
        request.Response.Return(200, fallback_html)

@WebRoute(GET, '/<path:filename>')
def serve_static_files(microWebSrv2, request, filename):
    """Serve static files with chunked streaming for memory efficiency"""
    try:
        web_root = get_web_root()
        file_path = f'{web_root}/{filename}'

        # Check if file exists
        try:
            file_size = os.stat(file_path)[6]
        except:
            # If file not found, serve the main index.html for Angular routing
            try:
                web_root = get_web_root()
                serve_file_chunked(request, f'{web_root}/index.html', 'text/html')
                return
            except:
                request.Response.ReturnJSON(404, {"error": "file not found"})
                return

        # Determine content type based on file extension
        content_type = get_content_type(filename)

        # Always use chunked transfer for memory safety
        serve_file_chunked(request, file_path, content_type)

    except Exception as e:
        print(f"Error serving {filename}: {e}")
        request.Response.ReturnJSON(500, {"error": "server error"})

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

# ============================================================================
# ===( Server Startup )=======================================================
# ============================================================================

def main():
    print("Setting up MicroWebSrv2...")

    # Print SD card contents
    print_sd_card_contents()

    # Create MicroWebSrv2 instance
    mws2 = MicroWebSrv2()

    # Configure for embedded use
    mws2.SetEmbeddedConfig()

    # Set the root path for static files based on configuration
    web_root = get_web_root()
    mws2._rootPath = web_root

    # All pages not found will be redirected to the home '/'
    mws2.NotFoundURL = '/'

    # Allow all origins for CORS
    mws2.AllowAllOrigins = True

    print("Server configuration:")
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
    print("Static files served with chunked streaming for memory efficiency")

    # Print initial memory info
    print_memory_info()

    # Force garbage collection before starting
    gc.collect()

    try:
        # Start the server
        print("Starting MicroWebSrv2...")
        mws2.StartManaged()

        print(f"Server running on http://{net_cfg[0]}/")

        # Main program loop
        try:
            while mws2.IsRunning:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Keyboard interrupt received")

    except Exception as e:
        print(f"Server error: {e}")
        print_memory_info()
    finally:
        print("Stopping server...")
        try:
            mws2.Stop()
        except:
            pass
        print("Server stopped")

if __name__ == '__main__':
    main()