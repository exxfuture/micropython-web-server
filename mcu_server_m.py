import os, sys, time, network, machine, ujson
import asyncio

from machine import Pin, PWM , Timer 

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
#STRUCT...
power = "OFF"   # "ON","OFF","PAUSE"
state = 0   # Will be set to ST_OFF after constants are defined
pwm = 10    #the pwm is between int 1-100%
wave_speed = 20
timer_sw = 10   # SEC
timer_sw_buf = timer_sw


#a = Pin(Pin.cpu.P010, Pin.IN)
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

#f = machine.PWM(machine.Pin('P408')) 
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
    #if wave_tim_buf != 0 :
        #wave_tim_buf = wave_tim_buf - 1
    wave_tim()
                
tim = Timer(-1)
tim.init(period=1000 , mode=Timer.PERIODIC, callback=zatim)

#btn_on_off = machine.Pin('P009',Pin.IN)
#btn_mode = machine.Pin('P010',Pin.IN)
#btn_pause = machine.Pin('P010',Pin.IN)

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
            #start_wave(wave_speed)
            
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




stmachine(EV_UPDATE)



# --- Mount SD and add /sd/lib ---
try:
    sd = machine.SDCard()
    os.mount(sd, "/sd")
    if "/sd/lib" not in sys.path:
        sys.path.insert(0, "/sd/lib")
    print("SD mounted.")
except Exception as e:
    print("No SD:", e)

from microdot.microdot import Microdot, Response
import gc
Response.default_content_type = 'application/json'

# --- LAN init (your style) ---
def net_up():
    lan = network.LAN()
    lan.active(True)
    timeout = 10
    while timeout > 0:
        ip = lan.ifconfig()[0]
        if ip != '0.0.0.0':
            break
        time.sleep(1)
        timeout -= 1
    return lan.ifconfig()

net_cfg = net_up()
print("LAN IP:", net_cfg[0])

# --- Hardware: 3 LEDs + 2 Buttons ---
LED1 = machine.Pin("P006", machine.Pin.OUT)
LED2 = machine.Pin("P007", machine.Pin.OUT)
LED3 = machine.Pin("P008", machine.Pin.OUT)

BTN1 = machine.Pin("P009", machine.Pin.IN, machine.Pin.PULL_UP)
BTN2 = machine.Pin("P010", machine.Pin.IN, machine.Pin.PULL_UP)

# --- Microdot app ---
app = Microdot()

@app.get('/api/status')
def status(req):
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
    return data, 200, {"Content-Type": "application/json"}

@app.post('/api/leds')
def set_led(req):
    try:
        body = req.json
        led = int(body.get("led", 0))
        val = 1 if body.get("value") else 0
    except Exception as e:
        return {"error": "bad request"}, 400

    if led == 1:
        LED1.value(val)
    elif led == 2:
        LED2.value(val)
    elif led == 3:
        LED3.value(val)
    else:
        return {"error": "invalid led"}, 400

    return {"ok": True, "led": led, "value": val}

@app.get('/api/lamp')
def get_lamp_status(req):
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
    return {
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

#export interface LampStatus {
#  power: string; "ON","OFF","PAUSE"
#  mode: string; "STATIC","WAVE", "PULSE"
#  brightness: number; 0-100
#  speed: number; sec 1-100sec - олко време вълната начало / край.
#  timer: number; sec
#  elapsedTime: number; sec
#}

@app.post('/api/lamp')
def set_lamp(req):
    global pwm, timer_sw, wave_speed, state, timer_sw_buf

    try:
        # Parse the request body - expecting LampStatusRequest format
        body = req.json
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
            return {"error": "Missing nearInfraredStatus in request body"}, 400

        # Extract nearInfraredStatus object
        near_ir_st = request_data["nearInfraredStatus"]
        print("nearInfraredStatus:", near_ir_st)

        # Validate required fields
        if not isinstance(near_ir_st, dict):
            print("Error: nearInfraredStatus must be an object")
            return {"error": "nearInfraredStatus must be an object"}, 400

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
            return {"error": "power must be 'ON', 'OFF', or 'PAUSE'"}, 400

        # Normalize and validate mode (case-insensitive)
        mode = mode.upper() if mode else "STATIC"
        if mode not in ["STATIC", "WAVE", "PULSE"]:
            print(f"Error: Invalid mode value: {mode}")
            return {"error": "mode must be 'STATIC', 'WAVE', or 'PULSE'"}, 400

        # Validate brightness (0-100)
        if not isinstance(brightness, (int, float)) or brightness < 0 or brightness > 100:
            print(f"Error: Invalid brightness value: {brightness}")
            return {"error": "brightness must be a number between 0-100"}, 400

        # Validate speed (0-100 seconds, 0 means no wave/pulse effect)
        if not isinstance(speed, (int, float)) or speed < 0 or speed > 100:
            print(f"Error: Invalid speed value: {speed}")
            return {"error": "speed must be a number between 0-100 seconds"}, 400

        # Validate timer (must be positive)
        if not isinstance(timer, (int, float)) or timer < 0:
            print(f"Error: Invalid timer value: {timer}")
            return {"error": "timer must be a positive number"}, 400

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
        return {
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

    except Exception as e:
        print(f"Error in set_lamp: {e}")
        return {"error": f"Server error: {str(e)}"}, 500

# -------- Static File Serving --------
@app.route('/')
def index(req):
    """Serve the main Angular application"""
    try:
        return serve_file_chunked('/sd/web/index.html', 'text/html')
    except:
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>MCU Server</title>
            <style>
                body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
                .error { color: #f44336; }
                .info { color: #2196F3; }
            </style>
        </head>
        <body>
            <h1>MCU Server Running</h1>
            <p class="info">Angular application files not found on SD card.</p>
            <p>Available API endpoints:</p>
            <ul style="display: inline-block; text-align: left;">
                <li><strong>GET /api/status</strong> - Get LED and button status</li>
                <li><strong>POST /api/leds</strong> - Control LEDs (JSON: {"led": 1-3, "value": true/false})</li>
            </ul>
            <p class="info">Upload the Angular build files to /sd/web/ directory on the MCU.</p>
        </body>
        </html>
        """, 200, {"Content-Type": "text/html"}

@app.route('/<path:filename>')
def static_files(req, filename):
    """Serve static files with chunked streaming for memory efficiency"""
    try:
        file_path = f'/sd/web/{filename}'

        # Check if file exists
        try:
            file_size = os.stat(file_path)[6]
        except:
            # If file not found, serve the main index.html for Angular routing
            try:
                return serve_file_chunked('/sd/web/index.html', 'text/html')
            except:
                return {"error": "file not found"}, 404

        # Determine content type based on file extension
        content_type = get_content_type(filename)

        # Always use chunked transfer for memory safety
        return serve_file_chunked(file_path, content_type)

    except Exception as e:
        print(f"Error serving {filename}: {e}")
        return {"error": "server error"}, 500

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

def serve_file_chunked(file_path, content_type):
    """Serve files - now optimized to read entire file at once since we have plenty of RAM"""
    try:
        # Get file size
        file_size = os.stat(file_path)[6]

        # Log file access
        if file_size > 50000:  # 50KB threshold
            print(f"Loading large file {file_path} ({file_size} bytes) - reading entire file at once")

        # Read entire file at once - we tested that MCU can allocate up to 7.5MB
        try:
            with open(file_path, 'rb') as f:
                content = f.read()

            print(f"Successfully loaded {len(content)} bytes into memory")

            # Optimize headers for large files to avoid network buffer issues
            headers = {
                'Content-Type': content_type,
                'Content-Length': str(len(content)),
                'Cache-Control': 'public, max-age=3600'
            }

            # For large files, add network optimization headers
            if len(content) > 300000:  # 300KB threshold
                print(f"Large file ({len(content)} bytes) - optimizing network transmission")
                headers['Connection'] = 'close'  # Close connection after transfer
                headers['Accept-Ranges'] = 'none'  # Disable range requests to simplify

            return content, 200, headers

        except MemoryError as e:
            print(f"Memory error loading {file_path}: {e}")
            print("Falling back to chunked reading...")

            # Fallback to chunked reading only if memory allocation fails
            try:
                content_parts = []
                chunk_size = 32768  # 32KB chunks (larger than before)
                bytes_read = 0

                with open(file_path, 'rb') as f:
                    while bytes_read < file_size:
                        remaining = min(chunk_size, file_size - bytes_read)
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

                headers = {
                    'Content-Type': content_type,
                    'Content-Length': str(len(content)),
                    'Cache-Control': 'public, max-age=3600'
                }

                return content, 200, headers

            except Exception as fallback_error:
                print(f"Fallback chunked reading also failed: {fallback_error}")
                gc.collect()
                return {"error": "file read error"}, 500

        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
            gc.collect()
            return {"error": "file read error"}, 500

    except Exception as e:
        print(f"Error serving file {file_path}: {e}")
        # Force garbage collection on error
        gc.collect()
        return {"error": "file access error"}, 500

# -------- Memory Management --------
def print_memory_info():
    """Print current memory usage for debugging"""
    try:
        import micropython
        print("Memory info:")
        micropython.mem_info()
    except:
        pass

# -------- Run --------
def main():
    print("Server running on http://%s/" % net_cfg[0])
    print("API endpoints:")
    print("  GET  /api/status")
    print("  POST /api/leds")
    print("  GET  /api/lamp")
    print("  POST /api/lamp")
    print("Static files served with chunked streaming (1KB chunks)")

    # Print initial memory info
    print_memory_info()

    # Force garbage collection before starting
    gc.collect()

    try:
        app.run(host='0.0.0.0', port=80, debug=False)
    except Exception as e:
        print(f"Server error: {e}")
        print_memory_info()

if __name__ == '__main__':
    main()


