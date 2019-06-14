import tensorflow as tf
import numpy as np
from tqdm import tqdm
import glob
import pickle
import os
import cv2
import argparse

'''
Script to convert data stored in .mat files (collect_data.py) to .tfrecord
'''

def _int64_feature(value):
    return tf.train.Feature(int64_list=tf.train.Int64List(value=value))

def _bytes_feature(value):
    return tf.train.Feature(bytes_list=tf.train.BytesList(value = [value]))

def _float_feature(value):
    return tf.train.Feature(float_list=tf.train.FloatList(value=value))

parser = argparse.ArgumentParser(description='Convert full trajectory folders to .tfrecord')
parser.add_argument('inp_path', metavar='inp_path', type=str, help='directory containing trajectory subdirectories')
parser.add_argument('out_path', metavar='out_path', type=str, help='directory to output .tfrecord files to. If it does not exist, it wil be created.')
parser.add_argument('-n', '--num', metavar='record_size', type=int, default=1, help='number of examples to store in each .tfrecord file')
parser.add_argument('-p_train', metavar='p_train', type=float, default=0.75, help='proportion of examples, on average, to put in training set')
parser.add_argument('-p_test', metavar='p_test', type=float, default=0.2, help='proportion of examples, on average, to put in test set')
parser.add_argument('-p_val', metavar='p_val', type=float, default=0.05, help='proportion of examples, on average, to put into validation set')

args = parser.parse_args()

data_path = args.inp_path
record_size = args.num

output_dir = args.out_path

# Make dirs if they don't already exist.
dirs = ['', 'train', 'test', 'val']

for d in dirs:
    if not os.path.exists(output_dir + d):
        os.makedirs(output_dir + d)

traj_paths = glob.glob('{}/2018*/traj*/'.format(data_path))

split = (args.p_train, args.p_test, args.p_val)

assert sum(split) == 1, "Proportions for example distribution don't sum to one."

train = []
test = []
val = []

train_ind = 0
test_ind = 0
val_ind = 0
"""
force_1: mean: 5.548266944444444 std: 8.618291543401973
z: mean: 1115.4815277777777 std: 34.865522493962516
x_act: mean: -0.36525 std: 40.55583610822862
force_4: mean: 5.346665555555556 std: 5.871973470396116
y_act: mean: 0.3839166666666667 std: 40.9047147811397
y: mean: 6045.260583333334 std: 212.2458477847846
force_3: mean: 6.150440555555555 std: 7.239953607917641
force_2: mean: 6.4838152777777776 std: 4.568602618451527
z_act: mean: 0.06966666666666667 std: 6.070706704238715
x: mean: 2644.52925 std: 209.59929224857643
"""
mean = {
        'force_1': 5.548266944444444,
        'z': 1115.4815277777777,
        'x_act': 0,
        'force_4': 5.346665555555556,
        'y_act': 0,
        'y': 6045.260583333334,
        'force_3': 6.150440555555555,
        'force_2': 6.4838152777777776,
        'z_act': 0,
        'x': 2644.52925
    }
std = {
        'force_1': 8.618291543401973,
        'z': 34.865522493962516,
        'x_act': 40.55583610822862,
        'force_4': 5.871973470396116,
        'y_act': 40.9047147811397,
        'y': 212.2458477847846,
        'force_3': 7.239953607917641,
        'force_2': 4.568602618451527,
        'z_act': 6.070706704238715,
        'x': 209.59929224857643

    }


f = {
    'force_1': [],
    'force_2':[],
    'force_3':[],
    'force_4':[],
    'x': [],
    'y': [],
    'z': [],
    'x_act': [],
    'y_act': [],
    'z_act': []
}

for fname in []:
    data = pickle.load(open(glob.glob(fname + '*.pkl')[0], 'rb'))

    for step_data in data[1:]:
        for item in step_data:
            if item != 'slip':
                f[item].append(step_data[item])
for item in []:
    if item != 'slip':
        print(item + ': mean: ' + str(np.mean(f[item])) + ' std: ' + str(np.std(f[item])))
slip = 0
for fname in tqdm(traj_paths):
    feature = {}
    data = pickle.load(open(glob.glob(fname + '*.pkl')[0], 'rb'))
    if data[1]['slip'] == 1:
        slip += 1 

    for i in range(1, len(data)):
        step_data = data[i]
        img = cv2.imread(glob.glob(fname + 'traj*_{}.jpg'.format(i))[0])
        img = cv2.resize(img, dsize=(64, 48))
        for feat in step_data:
            if feat != 'slip':
                step_data[feat] = (step_data[feat] - mean[feat]) / std[feat]
        act = [step_data['x_act'], step_data['y_act'], step_data['z_act']]
        state = [
            step_data['x'],
            step_data['y'],
            step_data['z'],
            step_data['slip'],
            step_data['force_1'],
            step_data['force_2'],
            step_data['force_3'],
            step_data['force_4']
        ]
        feature['%d/img' % (i-1)] = _bytes_feature(img.tostring())
        feature['%d/action' % (i-1)] = _float_feature(act)
        feature['%d/state' % (i-1)] = _float_feature(state)

    pre_img = cv2.imread(glob.glob(fname + '/traj*_0.jpg')[0])
    pre_img = cv2.resize(pre_img, dsize=(64, 48))
    feature['pre_img'] = _bytes_feature(pre_img.tostring())

    example = tf.train.Example(features=tf.train.Features(feature=feature))

    # Randomly determine which set to add to

    draw = np.random.rand()

    if draw < split[0]:
        train.append(example)
    elif draw < split[0] + split[1]:
        test.append(example)
    else:
        val.append(example)

    if len(train) == record_size:
        writer = tf.python_io.TFRecordWriter('{}train/train_{}.tfrecord'.format(output_dir, train_ind))
        for ex in train:
            writer.write(ex.SerializeToString())
        train_ind += record_size
        train = []
    if len(test) == record_size:
        writer = tf.python_io.TFRecordWriter('{}test/test_{}.tfrecord'.format(output_dir, test_ind))
        for ex in test:
            writer.write(ex.SerializeToString())
        test_ind += record_size
        test = []
    if len(val) == record_size:
        writer = tf.python_io.TFRecordWriter('{}val/val_{}.tfrecord'.format(output_dir, val_ind))
        for ex in val:
            writer.write(ex.SerializeToString())
        val_ind += record_size
        val = []

# Clear out data in 'incomplete' files

if len(train) > 0:
    writer = tf.python_io.TFRecordWriter('{}train/train_{}.tfrecord'.format(output_dir, train_ind, train_ind + len(train) - 1))
    for ex in train:
        writer.write(ex.SerializeToString())

if len(test) > 0:
    writer = tf.python_io.TFRecordWriter('{}test/test_{}.tfrecord'.format(output_dir, test_ind, test_ind + len(test) - 1))
    for ex in test:
        writer.write(ex.SerializeToString())

if len(val) > 0:
    writer = tf.python_io.TFRecordWriter('{}val/val_{}.tfrecord'.format(output_dir, val_ind, val_ind + len(val) - 1))
    for ex in val:
        writer.write(ex.SerializeToString())

print('Done converting {} tfrec files.'.format(len(traj_paths)))
print(slip)