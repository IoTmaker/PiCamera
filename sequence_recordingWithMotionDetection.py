import io
import os
import logging
import datetime as dt
import time
import pytz
from pathlib import Path
from subprocess import Popen, PIPE, DEVNULL
from multiprocessing import Process
from picamera import PiCamera
from gpiozero import MotionSensor, LED

# sudo apt-get install vlc
# reference: https://raspberrypi.stackexchange.com/questions/62523/always-on-security-camera-uploading-to-cloud-looping-video-recording-saving
DESTINATION = './video_sequences/'
STILLS_DESTINATION = './stills/'
RESOLUTION = '1920x1080'
FRAMERATE = 30  # fps
BITRATE = 1000000  # bps
QUALITY = 22
CHUNK_LENGTH = 60  # seconds
SIZE_LIMIT = 1024 * 1048576  # bytes

logging.getLogger().setLevel(logging.INFO)


class VideoFile:
    def __init__(self, dest=DESTINATION, stills_dest=STILLS_DESTINATION):
        self._filename = os.path.join(dest, dt.datetime.utcnow().strftime('CAM-%Y%m%d-%H%M%S.mp4'))
        self._filenameStills = os.path.join(stills_dest, dt.datetime.utcnow().strftime('PIC-%Y%m%d-%H%M%S.jpeg'))
        # Use a VLC sub-process to handle muxing to MP4
        self._process = Popen([
            'cvlc',
            'stream:///dev/stdin',
            '--demux', 'h264',
            '--h264-fps', str(FRAMERATE),
            '--play-and-exit',
            '--sout',
            '#standard{access=file,mux=mp4,dst=%s}' % self._filename,
            ], stdin=PIPE, stdout=DEVNULL, stderr=DEVNULL)
        logging.info('Recording to %s', self._filename)

    def write(self, buf):
        return self._process.stdin.write(buf)

    def close(self):
        self._process.stdin.close()
        self._process.wait()
        # If you want to add a cloud upload, I'd suggest starting it
        # in a background thread here; make sure it keeps an open handle
        # on the output file (self._filename) in case it gets deleted

    @property
    def name(self):
        return self._filename

    @property
    def size(self):
        return os.stat(self._filename).st_size

    def remove(self):
        logging.info('Removing %s', self._filename)
        os.unlink(self._filename)
        self._filename = None


def detectMovement(path_to_motion_log_file):
    movement_counter = 0
    current_state = False
    previous_state = False

    # Set a variable to hold the GPIO Pin identity
    pir = MotionSensor(4)

    print("Waiting for PIR to settle")
    pir.wait_for_no_motion()

    while True:
        # Read PIR state
        current_state = pir.motion_detected

        # If the PIR is triggered
        if current_state is True and previous_state is False:
            print("    Motion detected!", movement_counter)
            movement_counter += 1
            # Record previous state
            previous_state = True
            # print the time of the motion to the motion_log_file
            file = open(path_to_motion_log_file, "a")
            time_now_utc = dt.datetime.utcnow()
            tz_aware = time_now_utc.replace(tzinfo=pytz.UTC)
            est_time = tz_aware.astimezone(pytz.timezone("America/New_York"))
            file.write(est_time.strftime('%Y%m%d-%H%M%S') + "\n")

        # If the PIR has returned to ready state
        elif current_state is False and previous_state is True:
            print("    No Motion")
            previous_state = False

        # Wait for 10 milliseconds
        time.sleep(0.01)


def outputs():
    while True:
        yield VideoFile()


def record_video():
    print("recordVideo()")
    with PiCamera(resolution=RESOLUTION, framerate=FRAMERATE) as camera:
        files = []
        last_output = None
        for output in camera.record_sequence(
                outputs(),
                format='h264',
                bitrate=BITRATE,
                quality=QUALITY,
                intra_period=5 * FRAMERATE):
            if last_output is not None:
                last_output.close()
                files.append(last_output)
                total_size = sum(f.size for f in files)
                while total_size > SIZE_LIMIT:
                    f = files.pop(0)
                    total_size -= f.size
                    f.remove()
            last_output = output
            camera.wait_recording(CHUNK_LENGTH)


if __name__ == '__main__':
    log_file = Path("./motion_log_file.txt")
    path_to_log_file = str(log_file)
    # create the log file to hold list of motion detection events
    # if not already present
    if log_file.is_file() is False:
        #     create file
        print("motion_log_file.txt file did not exist.  Creating. ")
        open(str(log_file), 'w')

    try:
        while True:
            DetectMovement = Process(target=detectMovement,
                                     args=(path_to_log_file,))
            DetectMovement.start()
            record_video()
            # p.join()
    except KeyboardInterrupt:
        print("    Quit (Ctl+C)")
