#!/usr/bin/env python3
"""
ESP32 CYD Basic Server using MicroWebSrv2
Simple "Hello World" server with WiFi connection

Features:
- WiFi connection
- Single GET endpoint returning "Hello World"
- Minimal implementation for testing MicroWebSrv2

Author: Generated for ESP32 CYD basic testing
"""

import time
import network
import gc

# Import MicroWebSrv2 from local folder
from MicroWebSrv2.MicroWebSrv2 import *

# ============================================================================
# ===( Configuration )=======================================================
# ============================================================================

# Network Configuration  
USE_WIFI = True                # Always use WiFi for this basic test
WIFI_SSID = "Test"             # WiFi network name
WIFI_PASSWORD = "Test"         # WiFi password

# ============================================================================
# ===( Network Setup )=======================================================
# ============================================================================

def setup_wifi():
    """Setup WiFi connection"""
    try:
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        
        if not wlan.isconnected():
            print(f"Connecting to WiFi: {WIFI_SSID}")
            wlan.connect(WIFI_SSID, WIFI_PASSWORD)
            
            # Wait for connection with timeout
            timeout = 20
            while not wlan.isconnected() and timeout > 0:
                time.sleep(1)
                timeout -= 1
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

# Setup network connection
print("ESP32 CYD Basic Server - MicroWebSrv2")
print("Setting up WiFi connection...")

net_cfg = setup_wifi()
if not net_cfg:
    print("ERROR: WiFi connection failed!")
    print("Please check WIFI_SSID and WIFI_PASSWORD")
else:
    print(f"WiFi connected successfully: {net_cfg[0]}")

# ============================================================================
# ===( API Endpoints using MicroWebSrv2 )====================================
# ============================================================================

@WebRoute(GET, '/')
def hello_world(microWebSrv2, request):
    """Simple Hello World endpoint"""
    html_response = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>ESP32 CYD Basic Server</title>
        <style>
            body { 
                font-family: Arial, sans-serif; 
                text-align: center; 
                padding: 50px;
                background-color: #f0f0f0;
            }
            .container {
                background-color: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                display: inline-block;
            }
            h1 { color: #4CAF50; }
            .info { color: #666; margin-top: 20px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Hello World!</h1>
            <p>ESP32 CYD Basic Server is running</p>
            <p><strong>Server:</strong> MicroWebSrv2</p>
            <p><strong>Device:</strong> ESP32 Cheap Yellow Display</p>
            <div class="info">
                <p>This is a minimal test server with just one endpoint.</p>
                <p>If you can see this page, the server is working correctly!</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    request.Response.ContentType = 'text/html'
    request.Response.Return(200, html_response)

@WebRoute(GET, '/api/hello')
def api_hello(microWebSrv2, request):
    """Simple JSON Hello World API endpoint"""
    data = {
        "message": "Hello World!",
        "server": "MicroWebSrv2",
        "device": "ESP32 CYD",
        "status": "running",
        "ip": net_cfg[0] if net_cfg else "unknown"
    }
    request.Response.ReturnOkJSON(data)

# ============================================================================
# ===( Server Startup )=======================================================
# ============================================================================

def main():
    if not net_cfg:
        print("Cannot start server - no network connection")
        return
        
    print("Setting up MicroWebSrv2...")

    # Create MicroWebSrv2 instance
    mws2 = MicroWebSrv2()

    # Configure for embedded use
    mws2.SetEmbeddedConfig()

    # Allow all origins for CORS
    mws2.AllowAllOrigins = True

    print("Server configuration:")
    print(f"  Device: ESP32 Cheap Yellow Display (CYD)")
    print(f"  Network: WiFi")
    print(f"  IP Address: {net_cfg[0]}")
    print(f"  Port: 80")
    print("Endpoints:")
    print("  GET  /          - Hello World HTML page")
    print("  GET  /api/hello - Hello World JSON API")

    # Force garbage collection before starting
    gc.collect()

    try:
        # Start the server
        print("Starting ESP32 CYD Basic MicroWebSrv2...")
        mws2.StartManaged()

        print(f"Server running on http://{net_cfg[0]}/")
        print("Press Ctrl+C to stop the server")

        # Main program loop
        try:
            while mws2.IsRunning:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Keyboard interrupt received")

    except Exception as e:
        print(f"Server error: {e}")
    finally:
        print("Stopping server...")
        try:
            mws2.Stop()
        except:
            pass
        print("ESP32 CYD Basic Server stopped")

if __name__ == '__main__':
    main()
