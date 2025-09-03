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
USE_SD_CARD = False              # True = use SD card (/sd/www), False = use flash memory (/www)
WEB_ROOT_SD = "/sd/www"         # Path for web files on SD card
WEB_ROOT_FLASH = "/www"         # Path for web files on flash memory

# Network connection configuration
USE_WIFI = True                # True = use WiFi, False = use Ethernet (LAN)
WIFI_SSID = "Test"   # WiFi network name
WIFI_PASSWORD = "Test"  # WiFi password

# ============================================================================
# ===( ESP32 CYD Hardware Control - 3 RGB LEDs )============================
# ============================================================================

# ESP32 CYD RGB LED pins (from cydr.py reference)
# Pin 4  = Red LED
# Pin 16 = Green LED  
# Pin 17 = Blue LED

# LED Control Variables
led_states = [False, False, False]  # State of each LED (Red, Green, Blue)
led_brightness = [0, 0, 0]         # Brightness of each LED (0-100)

# Initialize RGB LEDs as PWM for brightness control
led_red = PWM(Pin(4), freq=1000, duty=0)      # Red LED on pin 4
led_green = PWM(Pin(16), freq=1000, duty=0)   # Green LED on pin 16
led_blue = PWM(Pin(17), freq=1000, duty=0)    # Blue LED on pin 17

# LED objects array for easy access
leds = [led_red, led_green, led_blue]
led_names = ["Red", "Green", "Blue"]

def set_led_brightness(led_index, brightness):
    """
    Set LED brightness using PWM
    
    Args:
        led_index (int): LED index (0=Red, 1=Green, 2=Blue)
        brightness (int): Brightness 0-100
    """
    if 0 <= led_index < len(leds):
        # Convert brightness (0-100) to duty cycle (0-1023)
        # Note: LEDs are active LOW on ESP32 CYD, so invert the duty cycle
        duty_value = int((100 - brightness) * 1023 / 100)
        duty_value = max(0, min(1023, duty_value))
        
        leds[led_index].duty(duty_value)
        led_brightness[led_index] = brightness
        led_states[led_index] = brightness > 0
        
        print(f"LED {led_names[led_index]} set to {brightness}% brightness (duty: {duty_value})")

def set_led_state(led_index, state):
    """
    Set LED on/off state
    
    Args:
        led_index (int): LED index (0=Red, 1=Green, 2=Blue)
        state (bool): True = on, False = off
    """
    if 0 <= led_index < len(leds):
        if state:
            # Turn on with current brightness or default to 50%
            brightness = led_brightness[led_index] if led_brightness[led_index] > 0 else 50
            set_led_brightness(led_index, brightness)
        else:
            # Turn off
            set_led_brightness(led_index, 0)

def get_led_state(led_index):
    """Get LED state"""
    if 0 <= led_index < len(leds):
        return led_states[led_index]
    return False

def get_led_brightness(led_index):
    """Get LED brightness"""
    if 0 <= led_index < len(leds):
        return led_brightness[led_index]
    return 0

def cleanup_leds():
    """Turn off all LEDs and cleanup"""
    for i in range(len(leds)):
        set_led_brightness(i, 0)
    print("All LEDs turned off")

# Initialize LEDs (turn them off)
cleanup_leds()
print(f"ESP32 CYD RGB LEDs initialized: {led_names}")

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

# Boot button on ESP32 CYD (Pin 0)
BTN_BOOT = machine.Pin(0, machine.Pin.IN, machine.Pin.PULL_UP)

print("ESP32 CYD hardware initialized:")
print(f"  RGB LEDs: {led_names} on pins 4, 16, 17")
print(f"  Boot button: Pin 0")

# ============================================================================
# ===( API Endpoints using MicroWebSrv2 )====================================
# ============================================================================

@WebRoute(GET, '/api/status')
def api_status(microWebSrv2, request):
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
        value = body.get("value", False)
        brightness = int(body.get("brightness", 50))  # Default 50% brightness
        
        # Validate LED index (1-3 for Red, Green, Blue)
        if led < 1 or led > 3:
            request.Response.ReturnJSON(400, {"error": "invalid led, must be 1-3"})
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
        request.Response.ReturnJSON(400, {"error": "bad request"})
        return

    request.Response.ReturnOkJSON({
        "ok": True,
        "led": led,
        "value": get_led_state(led_index),
        "brightness": get_led_brightness(led_index)
    })

@WebRoute(GET, '/api/lamp')
def api_get_lamp_status(microWebSrv2, request):
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
    request.Response.ReturnOkJSON(data)

@WebRoute(POST, '/api/lamp')
def api_set_lamp(microWebSrv2, request):
    """Set lamp configuration - adapted for ESP32 CYD RGB LEDs"""
    try:
        # Parse the request body - expecting LampStatusRequest format
        body = request.GetPostedJSONObject()
        if not body:
            request.Response.ReturnJSON(400, {"error": "Missing request body"})
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
                <li><strong>POST /api/leds</strong> - Control RGB LEDs (JSON: {{"led": 1-3, "value": true/false, "brightness": 0-100}})</li>
                <li><strong>GET /api/lamp</strong> - Get lamp status</li>
                <li><strong>POST /api/lamp</strong> - Control lamp settings</li>
                <li><strong>GET /api/network</strong> - Network configuration and status</li>
            </ul>
            <p class="info">Upload the Angular build files to {web_root}/ directory on the ESP32.</p>
            <p class="device">RGB LEDs: Red (Pin 4), Green (Pin 16), Blue (Pin 17)</p>
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
    print("Setting up ESP32 CYD MicroWebSrv2...")

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
    print("Static files served with chunked streaming for memory efficiency")
    print("RGB LEDs: Red (Pin 4), Green (Pin 16), Blue (Pin 17)")

    # Print initial memory info
    print_memory_info()

    # Force garbage collection before starting
    gc.collect()

    try:
        # Start the server
        print("Starting ESP32 CYD MicroWebSrv2...")
        mws2.StartManaged()

        print(f"ESP32 CYD Server running on http://{net_cfg[0]}/")

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
        cleanup_leds()  # Turn off all LEDs
        try:
            mws2.Stop()
        except:
            pass
        print("ESP32 CYD Server stopped")

if __name__ == '__main__':
    main()
