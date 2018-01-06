from gpiozero import MotionSensor

pir = MotionSensor(4)

counter = 0
while True:
    pir.wait_for_motion()
    counter += 1
    print("Motion detected")
    print("counter: ", counter)