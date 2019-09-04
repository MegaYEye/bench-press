from tb_control.testbench_control import TestBench
import time
import datetime
import cv2
import numpy as np
import sys
from scipy.io import savemat
import argparse
import yaml

with open('config_edge.yaml', 'r') as f:
    config = yaml.load(f)

HOME_POS = config['home']

'''
Command line arg format:
python collect_data.py [num_presses] [offset_radius] [images_per_press] [min_force] [max_force] [--output_dir]
Ex: python collect_data.py star 100 5 7 19

Presses at 100 uniformly randomly selected locations in a radius of 80 steps
centered at the star, taking an image at each of 5 uniformly randomly selected
force thresholds based on load cells from minimum to maximum force threshold.
'''

parser = argparse.ArgumentParser(description='Collect gelsight test data')
parser.add_argument('num_trials', metavar='N', type=int, help='number of presses to collect')
parser.add_argument('radius', metavar='radius', type=int, help='radius of circle to uniformly select press location in')
parser.add_argument('min_force', metavar='min_force', type=float, help='minimum of the range to select random threshold forces from')
parser.add_argument('max_force', metavar='max_force', type=float, help='maximum of the range to select random threshold forces from')
parser.add_argument('--out', metavar='out', type=str, default='data/', help='dir for output data')

args = parser.parse_args()

num_trials = args.num_trials
radius = args.radius
min_force_thresh = args.min_force
max_force_thresh = args.max_force

tb = TestBench('/dev/ttyACM0', 0)

while not tb.ready():
    time.sleep(0.1)
    tb.update()

tb.start()

while tb.busy():
    tb.update()

'''
Grab a quick reading, use to verify that load cells have been initialized
and tared correctly
'''

print(tb.req_data())

x = HOME_POS['x']
y = HOME_POS['y']
z = HOME_POS['z']

dx = 0
dy = 0

mX = 6000
mY = 12000
mZ = 2000

MIN_FORCE_THRESH = 7
MAX_FORCE_THRESH = 19

RESET_POS_EVERY_N = 30
data_file_num = 0

pre_press_frames = []
press_frames = []
x_pos = []
y_pos = []
z_pos = []
force_thresh = []
force_1 = []
force_2 = []
force_3 = []
force_4 = []

ctimestr = datetime.datetime.now().strftime("%Y-%m-%d:%H:%M:%S")

for i in range(num_trials):

    target_x, target_y, target_z = HOME_POS['x'], HOME_POS['y'], HOME_POS['z']
    x, y, z = target_x, target_y, target_z 
    
    tb.target_pos(target_x, target_y, target_z)
    while tb.busy():
        tb.update()
    
    for step in range(RESET_POS_EVERY_N):

        p_x = int(np.random.uniform(-radius, radius))
        p_y = int(np.random.uniform(-radius, radius))
        p_z = int(np.random.uniform(-radius, radius))

        while p_x**2 + p_y**2 + p_z**2 > radius**2:
            p_x = int(np.random.uniform(-radius, radius))
            p_y = int(np.random.uniform(-radius, radius))
            p_z = int(np.random.uniform(-radius, radius))

        dx = p_x
        dy = p_y
        dz = p_z

        target_x = x + dx
        target_y = y + dy
        target_z = z + dz

        assert target_x < mX, "Invalid X target: " + str(target_x)
        assert target_y < mY, "Invalid Y target: " + str(target_y)
        assert target_z < mZ, "Invalid Z target: " + str(target_z)

        # Grab before pressing image
        frame = tb.get_frame()
        # cv2.imwrite("cap_framebefore" + str(i) + ".png", frame)
        ppf = np.copy(frame)

        tb.target_pos(target_x, target_y, target_z)

        while tb.busy():
            tb.update()

        time.sleep(0.25)
        data = tb.req_data()
        print(data)

        force_thresh.append(force_threshold)

        x_pos.append(data['x'])
        y_pos.append(data['y'])
        z_pos.append(data['z'])
        force_1.append(data['force_1'])
        force_2.append(data['force_2'])
        force_3.append(data['force_3'])
        force_4.append(data['force_4'])

        frame = tb.get_frame()
        # cv2.imwrite("cap_frame" + str(i) + 'f=' + str(force_threshold) + ".png", frame)
        pre_press_frames.append(np.copy(ppf))
        press_frames.append(np.copy(frame))

    if i % 10 == 0: # Save progress often so we don't lose data!
        savemat(out + '/{}/'.format(ctimestr) + 'data_{}.mat'.format(data_file_num),
                {
                    "x": x_pos,
                    "y": y_pos,
                    "z": z_pos,
                    "force_thresh": force_thresh,
                    "force_1": force_1,
                    "force_2": force_2,
                    "force_3": force_3,
                    "force_4": force_4,
                    "press_frames": press_frames,
                    "pre_press_frames" : pre_press_frames
                })
        
        data_file_num+=1
        pre_press_frames = []
        press_frames = []
        x_pos = []
        y_pos = []
        z_pos = []
        force_thresh = []
        force_1 = []
        force_2 = []
        force_3 = []
        force_4 = []

savemat(out + '/{}/'.format(ctimestr) + 'data_{}.mat'.format(data_file_num),
        {
            "x": x_pos,
            "y": y_pos,
            "z": z_pos,
            "force_thresh": force_thresh,
            "force_1": force_1,
            "force_2": force_2,
            "force_3": force_3,
            "force_4": force_4,
            "press_frames": press_frames,
            "pre_press_frames" : pre_press_frames
        })

tb.reset()

while tb.busy():
    tb.update()
