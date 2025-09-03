# mcu_server_g.py — v1.2.1 (СТАБИЛЕН, с подробни лога)
# ------------------------------------------------------------
# VK-RA6M5 MicroPython + Microdot (по документацията):
# - app.run() (блокиращ)
# - Стрийминг със СИНХРОНЕН генератор (def), както Microdot изисква на MicroPython
# - Малки chunk-ове (DEFAULT_STREAM_CHUNK = 1024 B)
# - Content-Length + Connection: close + Cache-Control
# - Статични файлове от /sd/web + базов REST API
# - Подробни лога: стартиране, заявка, отваряне на файл, броя chunk-ове, байтове, време, kB/s
# ------------------------------------------------------------

import os, sys, time, machine, network, ujson, gc

# ---------- Лог/телеметрия ----------
_t0 = time.ticks_ms()
def _now_ms():
    return time.ticks_diff(time.ticks_ms(), _t0)

def log(msg):
    print("[+%d ms] %s" % (_now_ms(), msg))

def log_mem(label=""):
    gc.collect()
    print("[mem] %s free=%d used=%d" % (label, gc.mem_free(), gc.mem_alloc()))

REQ_COUNTER = 0

# ---------- Ранно SD монтиране + път за /sd/lib ----------
try:
    sd = machine.SDCard()
    os.mount(sd, "/sd")
    log("[init] SD mounted")
except Exception as e:
    log("[init] No SD: %s" % e)

if "/sd/lib" not in sys.path:
    sys.path.insert(0, "/sd/lib")

# ---------- Microdot ----------
try:
    from microdot.microdot import Microdot, Response
except Exception:
    from microdot import Microdot, Response

# ---------- Конфигурация ----------
HOST = "0.0.0.0"
PORT = 80
STATIC_ROOT = "/sd/web"
DEFAULT_STREAM_CHUNK = 1024      # 512..2048 са разумни за MicroPython

# ---------- MIME ----------
def get_content_type(filename: str) -> str:
    fn = filename.lower()
    if fn.endswith(".html"): return "text/html"
    if fn.endswith(".js"):   return "application/javascript"
    if fn.endswith(".css"):  return "text/css"
    if fn.endswith(".ico"):  return "image/x-icon"
    if fn.endswith(".png"):  return "image/png"
    if fn.endswith(".jpg") or fn.endswith(".jpeg"): return "image/jpeg"
    if fn.endswith(".svg"):  return "image/svg+xml"
    if fn.endswith(".json"): return "application/json"
    return "text/plain"

# ---------- Синхронен генератор за статични файлове (с подробни лога) ----------
def file_iter_sync(path: str, chunk_size: int = DEFAULT_STREAM_CHUNK):
    """
    СИНХРОНЕН генератор (def), както изисква Microdot за MicroPython.
    Печата метрика за прехвърлянето в края (или при изключение).
    """
    t_open = time.ticks_ms()
    f = open(path, "rb")
    open_ms = time.ticks_diff(time.ticks_ms(), t_open)
    # Размерът ще се логне в serve_file_stream; тук броим какво наистина е подадено:
    chunks = 0
    sent_bytes = 0
    t0 = time.ticks_ms()
    log("[stream] open OK '%s' (open=%d ms)" % (path, open_ms))
    try:
        while True:
            b = f.read(chunk_size)
            if not b:
                break
            sent_bytes += len(b)
            chunks += 1
            # По желание: от време на време лог за прогрес (на всеки 64 chunk-а)
            if (chunks % 64) == 0:
                log("[stream] progress '%s': chunks=%d sent=%d" % (path, chunks, sent_bytes))
            yield b
    except Exception as e:
        t1 = time.ticks_ms()
        dur = time.ticks_diff(t1, t0)
        thr = (sent_bytes/1024)/(dur/1000) if dur > 0 else 0.0
        log("[stream] ABORT '%s': chunks=%d sent=%d dur=%d ms thr=%.1f kB/s err=%s" %
            (path, chunks, sent_bytes, dur, thr, e))
        raise
    finally:
        try: f.close()
        except: pass
        t1 = time.ticks_ms()
        dur = time.ticks_diff(t1, t0)
        thr = (sent_bytes/1024)/(dur/1000) if dur > 0 else 0.0
        log("[stream] DONE  '%s': chunks=%d sent=%d dur=%d ms thr=%.1f kB/s" %
            (path, chunks, sent_bytes, dur, thr))

def serve_file_stream(path: str):
    """
    Връща Response с Content-Length и синхронен генератор за тялото.
    """
    try:
        st = os.stat(path)
    except Exception as e:
        log("[static] 404 '%s' (stat err: %s)" % (path, e))
        return {"error":"file not found"}, 404
    size = st[6]
    ctype = get_content_type(path)
    log("[static] send headers for '%s' (size=%d, ctype=%s)" % (path, size, ctype))
    headers = {
        "Content-Type": ctype,
        "Content-Length": str(size),
        "Connection": "close",
        "Cache-Control": "public, max-age=3600",
    }
    return Response(body=file_iter_sync(path, DEFAULT_STREAM_CHUNK), headers=headers)

# ---------- Microdot app ----------
app = Microdot()
Response.default_content_type = "application/json"

# ---------- Мрежа ----------
def net_up():
    lan = network.LAN()
    lan.active(True)
    tout = 10
    while tout > 0:
        ip = lan.ifconfig()[0]
        if ip and ip != "0.0.0.0":
            break
        time.sleep(1)
        tout -= 1
    return lan.ifconfig()

net_cfg = net_up()
log("[net] LAN IP: %s" % net_cfg[0])

# ---------- GPIO демо / REST ----------
LED1 = machine.Pin("P006", machine.Pin.OUT)
LED2 = machine.Pin("P007", machine.Pin.OUT)
LED3 = machine.Pin("P008", machine.Pin.OUT)
BTN1 = machine.Pin("P009", machine.Pin.IN, machine.Pin.PULL_UP)
BTN2 = machine.Pin("P010", machine.Pin.IN, machine.Pin.PULL_UP)

# Лампа (опростено)
PWM_FREQ_HZ     = 1000
WAVE_CHANNELS   = ('P111','P112','P113','P114','P115','P608')
from machine import PWM, Pin, Timer

ST_OFF, ST_STATIC, ST_WAVE, ST_PAUSE, ST_PULSE = 0,1,2,3,4
state        = ST_OFF
pwm_percent  = 10
wave_speed_s = 20
timer_sw     = 10
timer_sw_buf = timer_sw

CHANNELS = []
for pname in WAVE_CHANNELS:
    ch = PWM(Pin(pname, Pin.OUT))
    ch.freq(PWM_FREQ_HZ)
    ch.duty(0)
    CHANNELS.append(ch)

def clamp01pct(x): 
    return 0 if x < 0 else (100 if x > 100 else int(x))

def set_all(pct):
    pct = clamp01pct(pct)
    for ch in CHANNELS: ch.duty(pct)

def stop_all():
    for ch in CHANNELS: ch.duty(0)

def enable_only(idx, pct):
    pct = clamp01pct(pct)
    for i, ch in enumerate(CHANNELS): ch.duty(pct if i == idx else 0)

_wave_tick_ms = 0
_wave_step_ms = max(100, int((wave_speed_s * 1000) / max(1, len(CHANNELS))))
_wave_index   = 0
_tick_100ms   = 0

def _update_wave_step_ms():
    global _wave_step_ms
    total = max(1000, int(wave_speed_s*1000))
    _wave_step_ms = max(100, total // max(1, len(CHANNELS)))

def stmachine_update():
    global timer_sw_buf
    if state == ST_OFF:
        stop_all()
    elif state == ST_STATIC:
        timer_sw_buf = timer_sw
        set_all(pwm_percent)
    elif state == ST_WAVE:
        timer_sw_buf = timer_sw
        _update_wave_step_ms()
        enable_only(_wave_index % len(CHANNELS), pwm_percent)
    elif state == ST_PAUSE:
        stop_all()
    elif state == ST_PULSE:
        timer_sw_buf = timer_sw
        set_all(pwm_percent)

def _timer_isr(t):
    global _tick_100ms, timer_sw_buf, state
    global _wave_tick_ms, _wave_step_ms, _wave_index
    _tick_100ms += 100
    _wave_tick_ms += 100
    if _tick_100ms >= 1000:
        _tick_100ms = 0
        if timer_sw_buf > 0:
            timer_sw_buf -= 1
            if timer_sw_buf == 0:
                state = ST_OFF
                stop_all()
    if state == ST_WAVE and _wave_tick_ms >= _wave_step_ms:
        _wave_tick_ms = 0
        _wave_index = (_wave_index + 1) % len(CHANNELS)
        enable_only(_wave_index, pwm_percent)

Timer(-1).init(period=100, mode=Timer.PERIODIC, callback=_timer_isr)

# ---------- Лог на заявки (минимален обвивен декоратор) ----------
def log_request(handler):
    def wrapper(req, *a, **kw):
        global REQ_COUNTER
        REQ_COUNTER += 1
        rid = REQ_COUNTER
        t0 = time.ticks_ms()
        method = getattr(req, "method", "?")
        path = getattr(req, "path", "?")
        log("[REQ#%d] %s %s start" % (rid, method, path))
        try:
            resp = handler(req, *a, **kw)
            # Microdot може да връща (body,status,headers) или dict, или Response
            if isinstance(resp, tuple) and len(resp) >= 2 and isinstance(resp[1], int):
                status = resp[1]
            else:
                status = 200
            dt = time.ticks_diff(time.ticks_ms(), t0)
            log("[REQ#%d] %s %s -> %d in %d ms" % (rid, method, path, status, dt))
            return resp
        except Exception as e:
            dt = time.ticks_diff(time.ticks_ms(), t0)
            log("[REQ#%d] %s %s FAILED in %d ms: %s" % (rid, method, path, dt, e))
            raise
    return wrapper

# ---------- REST: /api/status ----------
@app.get("/api/status")
@log_request
def api_status(req):
    return {
        "leds": {"1": LED1.value(), "2": LED2.value(), "3": LED3.value()},
        "buttons": {"1": BTN1.value(), "2": BTN2.value()}
    }

# ---------- REST: /api/leds (POST) ----------
@app.post("/api/leds")
@log_request
def api_leds(req):
    try:
        body = req.json or {}
        led = int(body.get("led", 0))
        val = 1 if body.get("value") else 0
    except Exception:
        return {"error":"bad request"}, 400

    if   led == 1: LED1.value(val)
    elif led == 2: LED2.value(val)
    elif led == 3: LED3.value(val)
    else:          return {"error":"invalid led"}, 400
    return {"ok": True, "led": led, "value": val}

# ---------- REST: /api/lamp (GET/POST) ----------
def _readable_power_and_mode():
    if state == ST_OFF:    return "OFF","STATIC"
    if state == ST_PAUSE:  return "PAUSE","STATIC"
    if state == ST_STATIC: return "ON","STATIC"
    if state == ST_WAVE:   return "ON","WAVE"
    if state == ST_PULSE:  return "ON","PULSE"
    return "OFF","STATIC"

@app.get("/api/lamp")
@log_request
def api_lamp_get(req):
    p,m = _readable_power_and_mode()
    return {
        "nearInfraredStatus": {
            "power": p, "mode": m, "brightness": pwm_percent,
            "speed": wave_speed_s, "timer": timer_sw, "elapsedTime": 0
        },
        "redLightStatus": {
            "power": "OFF", "mode": "STATIC",
            "brightness": 0, "speed": 20, "timer": 10, "elapsedTime": 0
        }
    }

@app.post("/api/lamp")
@log_request
def api_lamp_post(req):
    global pwm_percent, wave_speed_s, timer_sw, timer_sw_buf, state
    try:
        body = req.json or {}
        r = body.get("request", body)
        near = r["nearInfraredStatus"]
        power = (near.get("power") or "OFF").upper()
        mode  = (near.get("mode")  or "STATIC").upper()
        brightness = near.get("brightness", 0)
        speed      = near.get("speed", 20)
        timer_v    = near.get("timer", 0)
        if power not in ("ON","OFF","PAUSE"): raise ValueError
        if mode  not in ("STATIC","WAVE","PULSE"): raise ValueError
        if not (isinstance(brightness,(int,float)) and 0<=brightness<=100): raise ValueError
        if not (isinstance(speed,(int,float)) and 0<=speed<=100): raise ValueError
        if not (isinstance(timer_v,(int,float)) and timer_v>=0): raise ValueError
    except Exception:
        return {"error":"invalid payload"}, 400

    pwm_percent  = int(brightness)
    wave_speed_s = int(speed)
    timer_sw     = int(timer_v)
    timer_sw_buf = timer_sw

    if power == "OFF":   state = ST_OFF
    elif power == "PAUSE": state = ST_PAUSE
    else:
        if   mode == "STATIC": state = ST_STATIC
        elif mode == "WAVE":   state = ST_WAVE
        else:                  state = ST_PULSE

    stmachine_update()
    return {"ok": True, "nearInfraredStatus":{
        "power": power, "mode": mode, "brightness": pwm_percent,
        "speed": wave_speed_s, "timer": timer_sw, "elapsedTime": 0
    }}

# ---------- Static routes (с подробни лога) ----------
@app.route("/")
@log_request
def index(req):
    path = STATIC_ROOT + "/index.html"
    log("[route] / -> %s" % path)
    return serve_file_stream(path)

@app.route("/<path:filename>")
@log_request
def static_files(req, filename):
    if ".." in filename:
        log("[route] traversal BLOCKED: %s" % filename)
        return {"error":"not found"}, 404
    path = STATIC_ROOT + "/" + filename
    try:
        os.stat(path)
        log("[route] static '%s'" % path)
        return serve_file_stream(path)
    except:
        # SPA fallback към index.html
        fallback = STATIC_ROOT + "/index.html"
        log("[route] fallback '%s' -> '%s'" % (path, fallback))
        try:
            return serve_file_stream(fallback)
        except:
            return {"error":"file not found"}, 404

# ---------- Run ----------
def main():
    log_mem("startup")
    log("[run] Server on http://%s:%d/" % (net_cfg[0], PORT))
    gc.collect()
    app.run(host=HOST, port=PORT, debug=False)

if __name__ == "__main__":
    main()
