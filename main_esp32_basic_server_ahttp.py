#!/usr/bin/env python3
"""
ESP32 CYD Basic Server using ahttpserver (async)
Simple "Hello World" server with WiFi connection

Features:
- WiFi connection
- Single GET endpoint returning "Hello World"
- Minimal async implementation for testing ahttpserver

Author: Generated for ESP32 CYD basic testing
"""

import time
import network
import gc
import json
import uasyncio as asyncio

# Import the async HTTP server
from ahttpserver import HTTPResponse, HTTPServer

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
print("ESP32 CYD Basic Server - ahttpserver (async)")
print("Setting up WiFi connection...")

net_cfg = setup_wifi()
if not net_cfg:
    print("ERROR: WiFi connection failed!")
    print("Please check WIFI_SSID and WIFI_PASSWORD")
else:
    print(f"WiFi connected successfully: {net_cfg[0]}")

# ============================================================================
# ===( HTTP Server Setup )===================================================
# ============================================================================

# Create async HTTP server instance
app = HTTPServer(host="0.0.0.0", port=80, timeout=30)

# ============================================================================
# ===( API Endpoints )=======================================================
# ============================================================================

@app.route("GET", "/")
async def hello_world(reader, writer, request):
    """Simple Hello World endpoint"""
    html_response = """<!DOCTYPE html>
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
        h1 { color: #2196F3; }
        .info { color: #666; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Hello World!</h1>
        <p>ESP32 CYD Basic Server is running</p>
        <p><strong>Server:</strong> ahttpserver (async)</p>
        <p><strong>Device:</strong> ESP32 Cheap Yellow Display</p>
        <div class="info">
            <p>This is a minimal async test server with just one endpoint.</p>
            <p>If you can see this page, the async server is working correctly!</p>
        </div>
    </div>
</body>
</html>"""
    
    response = HTTPResponse(200, "text/html", close=True)
    await response.send(writer)
    writer.write(html_response)
    await writer.drain()

@app.route("GET", "/api/hello")
async def api_hello(reader, writer, request):
    """Simple JSON Hello World API endpoint"""
    data = {
        "message": "Hello World!",
        "server": "ahttpserver (async)",
        "device": "ESP32 CYD",
        "status": "running",
        "ip": net_cfg[0] if net_cfg else "unknown"
    }
    
    response = HTTPResponse(200, "application/json", close=True)
    await response.send(writer)
    writer.write(json.dumps(data))
    await writer.drain()

# ============================================================================
# ===( Memory Management )====================================================
# ============================================================================

async def memory_management_task():
    """Background task for memory management"""
    while True:
        gc.collect()
        await asyncio.sleep(10)  # Run GC every 10 seconds

# ============================================================================
# ===( Server Startup )=======================================================
# ============================================================================

async def main():
    """Main server function"""
    if not net_cfg:
        print("Cannot start server - no network connection")
        return
        
    print("Setting up ESP32 CYD Basic Async HTTP Server...")

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
        # Start the async HTTP server
        print("Starting ESP32 CYD Basic Async HTTP Server...")
        
        # Create background tasks
        memory_task = asyncio.create_task(memory_management_task())
        server_task = asyncio.create_task(app.start())
        
        print(f"Server running on http://{net_cfg[0]}/")
        print("Server is using asyncio for efficient memory usage")
        print("Press Ctrl+C to stop the server")

        # Wait for tasks to complete (they run forever)
        await asyncio.gather(memory_task, server_task)

    except KeyboardInterrupt:
        print("Keyboard interrupt received")
    except Exception as e:
        print(f"Server error: {e}")
    finally:
        print("Stopping server...")
        try:
            await app.stop()
        except:
            pass
        print("ESP32 CYD Basic Server stopped")

def run_server():
    """Entry point to run the server"""
    if not net_cfg:
        print("Cannot start server - no network connection")
        return
        
    try:
        # Set up exception handler for asyncio
        def handle_exception(loop, context):
            print("Asyncio exception:", context)

        loop = asyncio.get_event_loop()
        loop.set_exception_handler(handle_exception)

        # Run the main server
        loop.run_until_complete(main())
        
    except KeyboardInterrupt:
        print("Server interrupted by user")
    except Exception as e:
        print(f"Fatal server error: {e}")
    finally:
        try:
            asyncio.new_event_loop()
        except:
            pass

if __name__ == '__main__':
    run_server()
