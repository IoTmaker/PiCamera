import picamera
import time

while True:
    with picamera.PiCamera() as camera:
        camera.resolution = (1024, 768)
        camera.start_preview(fullscreen=True)
        time.sleep(10000)
