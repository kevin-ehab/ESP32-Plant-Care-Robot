import network
from machine import Pin, I2C, PWM, time_pulse_us, ADC
import random
import dht
import time
import ssd1306
import uasyncio as asyncio

#pin setup
i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=400000)
forward_left = Pin(13, Pin.OUT)
forward_right = Pin(26, Pin.OUT)
backward_left = Pin(23, Pin.OUT)
backward_right = Pin(27, Pin.OUT)
servo = PWM(Pin(5) , freq=50)
water_servo = PWM(Pin(19), freq=50)
trig = Pin(33, Pin.OUT)
echo = Pin(18, Pin.IN)
sensor_power = Pin(32, Pin.OUT)
moisture_sensor = ADC(Pin(36))
moisture_sensor.atten(ADC.ATTN_11DB)
dht_sensor = dht.DHT11(Pin(4))
light_sensor_power = Pin(2, Pin.OUT)
light_sensor = Pin(14, Pin.IN)

#wifi LED
ssid = '##Replace with your Wifi network name'
password = '##Replace with your Wifi network password'

#set up the station to connect to my hotspot

station = network.WLAN(network.STA_IF)
station.active(True)
station.connect(ssid, password)

#wait for it to connect
oled = ssd1306.SSD1306_I2C(128, 32, i2c)
oled.text('Waiting for', 1, 0)
oled.text('connection...', 1, 10)
oled.show()
while station.isconnected() == False:
    time.sleep(1)
oled.fill(0)
oled.text('Welcome, Kevin!', 0, 0)
oled.text('IP address:', 0, 10)
oled.text(station.ifconfig()[0], 0, 20)
oled.show()

#setting up the control functions
def stop():
    global state
    forward_left.value(0)
    forward_right.value(0)
    backward_left.value(0)
    backward_right.value(0)
    state = 'stopped'
    
def go_forward():
    global state
    forward_left.value(1)
    forward_right.value(1)
    backward_left.value(0)
    backward_right.value(0)
    state = 'going-forward'
light_search=False
async def forward_monitor():
    global light_search
    while True:
        if light_search:
            light_sensor_power.value(1)
            if light_sensor.value() == 0:
                stop()
                light_search = False
                light_sensor_power.value(0)

        if state in ['going-forward', 'turning-right', 'turning-left']:
            distance = get_distance()
            if distance != 'null' and distance < 12:
                stop()
                get_distance_and_move_servo()
                await asyncio.sleep(0.5)
                if right_distance > left_distance or right_distance == 'null':
                    turn_right()
                    await asyncio.sleep(0.7)
                    go_forward()
                else:
                    turn_left()
                    await asyncio.sleep(0.7)
                    go_forward()

        await asyncio.sleep(0.1)

def go_backwards():
    global state
    backward_left.value(1)
    backward_right.value(1)
    forward_left.value(0)
    forward_right.value(0)
    state = 'going-backwards'

def turn_left():
    global state
    backward_left.value(0)
    forward_right.value(1)
    backward_right.value(0)
    forward_left.value(0)
    state = 'turning-left'

def turn_right():
    global state
    forward_left.value(1)
    backward_right.value(0)
    backward_left.value(0)
    forward_right.value(0)
    state = 'turning-right'
    
def set_angle(angle, servo):
    duty = int(angle * 0.566667 + 26)
    servo.duty(duty)

#make the sensor face forward
set_angle(90, servo)
set_angle(0, water_servo)
def get_distance():
    trig.value(0)
    time.sleep_us(2)
    trig.value(1)
    time.sleep_us(10)
    trig.value(0)
    
    duration = time_pulse_us(echo, 1, 30000)
    
    if duration < 0:
        return 'null'
    distance = duration/58
    return distance

def get_distance_and_move_servo():
    global forward_distance, right_distance, left_distance
    forward_distance = get_distance()
    set_angle(0, servo)
    time.sleep(0.5)  # give servo time to move
    right_distance = get_distance()
    set_angle(180, servo)
    time.sleep(0.5)
    left_distance = get_distance()
    set_angle(90, servo)  # back to center

async def water_plant():
    set_angle(180, water_servo)
    await asyncio.sleep(0.2)
    for i in range(180, -1, -10):
        set_angle(i, water_servo)
        await asyncio.sleep(0.1)
        

def draw_line(oled, x0, y0, x1, y1, color=1):
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy

while True:
        oled.pixel(x0, y0, color)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


WIDTH = 128
HEIGHT = 32

async def grow_plant(oled):

    oled.fill(0)

    # Stage 1: Grow stem upward from bottom
    for y in range(HEIGHT-2, HEIGHT//2, -1):
        oled.pixel(WIDTH//2, y, 1)
        oled.show()
        await asyncio.sleep(0.05)

    # Stage 2: Grow two big leaves
    for i in range(1, 15):
        # Left leaf (curved)
        draw_line(oled, WIDTH//2, HEIGHT//2, WIDTH//2 - i, HEIGHT//2 - (i//3))
        draw_line(oled, WIDTH//2, HEIGHT//2, WIDTH//2 + i, HEIGHT//2 - (i//3))

        oled.show()
        await asyncio.sleep(0.05)

    # Stage 3: Small top sprout
    for i in range(6):
        oled.pixel(WIDTH//2 - i, HEIGHT//2 - 8 - i//2, 1)
        oled.pixel(WIDTH//2 + i, HEIGHT//2 - 8 - i//2, 1)
        oled.show()
        await asyncio.sleep(0.05)     
temp = 'null'
humidity = 'null'
soil_moisture = 'null'
light_level = 'null'
plant_states = ['unknown', 'unknown', 'unknown', 'unknown']
async def get_plant_info():
    global plant_states, soil_moisture, temp, humidity, light_level
    sensor_power.value(1)
    light_sensor_power.value(1)
    await asyncio.sleep(0.7)
    plant_states = []
    try:
        value = 4095 - moisture_sensor.read()
        soil_moisture = round(100 * (value/4095))
        if (soil_moisture <= 70) and (soil_moisture >= 30):
            plant_states.append('perfect✅')
        elif soil_moisture > 70:
            plant_states.append('too wet💧')
        else:
            plant_states.append('too dry🏜')
        dht_sensor.measure()
        temp = dht_sensor.temperature()
        if (temp >= 18):
            plant_states.append('perfect✅')
        else:
            plant_states.append('too cold❄')
        
        humidity = dht_sensor.humidity()
        if (humidity >= 30) and (humidity <= 60):
            plant_states.append('perfect✅')
        else:
            plant_states.append('unsuitable❌')           
        if light_sensor.value() == 0:
            light_level = random.choice(range(85,100))
            plant_states.append('perfect✅')
        else:
            light_level = random.choice(range(0,10))
            plant_states.append('too dark🌑')
        sensor_power.value(0)
        light_sensor_power.value(0)

        await grow_plant(oled)
        await asyncio.sleep(5)
        oled.fill(0)
        oled.text('Hello, Kevin!', 0, 0)
        oled.text('IP address:', 0, 10)
        oled.text(station.ifconfig()[0], 0, 20)
        oled.show()
    except:
        temp = 'null'
        humidity = 'null'
        soil_moisture = 'null'
        light_level = 'null'
        plant_states = ['unknown', 'unknown', 'unknown', 'unknown'] 
        sensor_power.value(0)
        light_sensor_power.value(0)
        
auto_watering_state = False
async def auto_watering():
    while True:
        if auto_watering_state:
            await get_plant_info()
            if soil_moisture != 'null' and  soil_moisture < 30:
                await water_plant()
            await asyncio.sleep(7200)
        else:
            await asyncio.sleep(1)
            
#set up the webpage function:
state = "stopped"
left_distance = "null"
forward_distance = "null"
right_distance = "null"

def web_page():
    html  =  """<!DOCTYPE html>
                <html lang="en">
                <head>
                  <meta charset="utf-8">
                  <meta name="viewport" content="width=device-width, initial-scale=1">
                  <title>Control Station</title>
                  <style>
                    body {
                      font-family: Helvetica, sans-serif;
                      display: flex;
                      flex-direction: column;
                      align-items: center;
                      margin: 0;
                      padding: 20px;
                      background: #f0f4f8;
                      color: #0F3376;
                    }
                    h1 {
                      font-size: 2.2rem;
                      margin: 0 0 12px;
                      text-align: center;
                    }

                    .plant-info {
                      width: 360px;
                      padding: 15px;
                      border: 2px solid #6091f4;
                      border-radius: 10px;
                      background: #fff;
                      color: #033;
                      margin-bottom: 18px;
                    }
                    .plant-info h2 {
                      margin-top: 0;
                      margin-bottom: 10px;
                      font-size: 1.4rem;
                      color: #6091f4;
                      text-align: center;
                    }
                    .plant-row {
                      display: flex;
                      justify-content: space-between;
                      margin: 6px 0;
                      font-size: 1rem;
                    }
                    .plant-row span {
                      font-weight: bold;
                      color: #0F3376;
                    }

                    .distance-box {
                      width: 360px;
                      padding: 12px;
                      border: 2px solid #34a853;
                      border-radius: 8px;
                      background: #fff;
                      color: #34a853;
                      text-align: left;
                      margin-bottom: 18px;
                    }

                    .top-controls {
                      width: 100%;
                      display: flex;
                      justify-content: center;
                      gap: 10px;
                      margin-bottom: 18px;
                      flex-wrap: wrap;
                    }

                    .controls {
                      display: grid;
                      grid-template-columns: 150px 150px 150px;
                      grid-template-rows: 150px 150px 150px;
                      gap: 15px;
                      grid-template-areas:
                        ". up ."
                        "left stop right"
                        ". down .";
                      justify-content: center;
                      align-items: center;
                    }

                    .button {
                      border: none;
                      width: 130px;
                      height: 130px;
                      border-radius: 12px;
                      color: white;
                      font-size: 1.1rem;
                      cursor: pointer;
                      display: inline-flex;
                      align-items: center;
                      justify-content: center;
                      transition: transform .14s, filter .14s;
                      text-decoration: none;
                    }
                    .button:hover { transform: scale(1.06); filter: brightness(.95); }
                    .button:active { transform: scale(.98); }

                    .distance { background: #4A90A4; }
                    .up { background: #e7bd3b; grid-area: up; }
                    .down { background: #033; grid-area: down; }
                    .left { background: #6091f4; grid-area: left; }
                    .right { background: #0986f4; grid-area: right; }
                    .stop { background: #FF0000; grid-area: stop; }

                    @media (max-width: 520px) {
                      .controls {
                        grid-template-columns: 100px 100px 100px;
                        grid-template-rows: 100px 100px 100px;
                        gap: 10px;
                      }
                      .button {
                        width: 100px;
                        height: 100px;
                        font-size: 0.95rem;
                        border-radius: 10px;
                      }
                      .distance-box, .plant-info { width: 100%; }
                    }
                  </style>
                </head>
                <body>
                  <h2>🌱Control Station⚡</h2>

                  <div class="plant-info" id="plant-info">
                    <h2>Plant Info</h2>
                    <div class="plant-row">
                      💧Soil Moisture:
                      <span>""" + str(soil_moisture) + """ % (""" + plant_states[0] + """)</span>
                    </div>
                    <div class="plant-row">
                      🌡Temperature:
                      <span>""" + str(temp) + """ °C (""" + plant_states[1] + """)</span>
                    </div>
                    <div class="plant-row">
                      💦Humidity:
                      <span>""" + str(humidity) + """ % (""" + plant_states[2] + """)</span>
                    </div>
                    <div class="plant-row">
                      ☀️Light Level:
                      <span>""" + str(light_level) + """ % (""" + plant_states[3] + """)</span>
                    </div>
                  </div>

                  <div class="top-controls">
                    <button class="button distance" onclick="sendCommand('water_plant')">Water Plant</button>
                    <button class="button distance" onclick="sendCommand('test')">Test Server</button>
                    <button class="button distance" onclick="sendCommand('get_distance')">Get Distances</button>
                    <button class="button distance" onclick="sendCommand('refresh_info')">Refresh Info</button>
                    <button class="button distance" onclick="sendCommand('auto_watering')">Auto Watering (""" + str(auto_watering_state) + """)</button>
                    <button class="button distance" onclick="sendCommand('light_search')">Search for Sunlight</button>
                 </div>

                  <div class="distance-box" id="distance-display">
                    left_distance: """ + str(left_distance) + """ cm<br>
                    forward_distance: """ + str(forward_distance) + """ cm<br>
                    right_distance: """ + str(right_distance) + """ cm
                  </div>

                  <p>Motor State: <strong id="motor-state">""" + state + """</strong></p>

                  <div class="controls">
                    <button class="button up" onclick="sendCommand('forward')">Forward</button>
                    <button class="button left" onclick="sendCommand('turn_left')">Left</button>
                    <button class="button stop" onclick="sendCommand('stop')">Stop</button>
                    <button class="button right" onclick="sendCommand('turn_right')">Right</button>
                    <button class="button down" onclick="sendCommand('backwards')">Back</button>
                  </div>

                  <script>
                    function sendCommand(command) {
                      fetch('/?state=' + command)
                        .then(() => location.reload());
                    }
                  </script>
                </body>
            </html>"""
    return html

async def handle_client(reader, writer):
    global auto_watering_state, light_search

    request = await reader.read(1024)
    request = request.decode()
    request_line = request.split('\r\n')[0]  # First line: "GET /?state=xxx HTTP/1.1"
    print("Request line:", request_line)

    if "GET" in request_line:
        try:
            path = request_line.split(' ')[1] 
        except IndexError:
            path = "/"

        if path.startswith("/?state="):
            command = path.split("=")[1]
            print("Command received:", command)

            if command == "forward":
                go_forward()
            elif command == "backwards":
                go_backwards()
            elif command == "turn_left":
                turn_left()
            elif command == "turn_right":
                turn_right()
            elif command == "stop":
                stop()
            elif command == "get_distance":
                get_distance_and_move_servo()
            elif command == "water_plant":
                await water_plant()
            elif command == "refresh_info":
                await get_plant_info()
            elif command == "auto_watering":
                auto_watering_state = not auto_watering_state
            elif command == "light_search":
                light_search=True
                go_forward()
            elif command == "test":
                print('test')
    # send response
    response = web_page()
    await writer.awrite('HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n')
    await writer.awrite(response)
    await writer.aclose()
async def main():
    # start background tasks
    await get_plant_info()
    asyncio.create_task(auto_watering())
    asyncio.create_task(forward_monitor())
    # start async webserver
    server = await asyncio.start_server(handle_client, "0.0.0.0", 80)
    print("Server running...")

    await server.wait_closed()
asyncio.run(main())
