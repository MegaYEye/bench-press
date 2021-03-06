import time

import numpy as np
from bench_press.run.env.base_env import BaseEnv
from bench_press.tb_control.dynamixel_interface import Dynamixel
from bench_press.tb_control.testbench_control import TestBench
from bench_press.utils.camera import CameraThread, Camera
from bench_press.utils.optoforce import OptoforceThread

try:
    from src.optoforce.optoforce import *
except ImportError:
    print('No optoforce drivers installed! Be careful')


class TBEnv(BaseEnv):

    def __init__(self, env_config, logger):
        super(TBEnv, self).__init__(env_config, logger)
        self.cameras = self._setup_cameras()
        if self.config.dynamixel:
            self.dynamixel_bounds = np.array(self.config.dynamixel.bounds)
            self._setup_dynamixel()
            assert len(self.dynamixel_bounds) == 2, 'Dynamixel bounds should be [lower, upper]'
            assert self.dynamixel_bounds[0] < self.dynamixel_bounds[1], 'Dynamixel lower bound bigger than upper?'
        if self.config.optoforce:
            self.optoforce = self._setup_optoforce()
        self.tb = self._setup_tb()
        self.min_bounds = np.array(self.config.min_bounds)
        self.max_bounds = np.array(self.config.max_bounds)
        self.home_pos = np.array(self.config.home_pos)

    def clean_up(self):
        for camera_thread in self.cameras:
            camera_thread.stop()
            camera_thread.join()
        if self.config.optoforce:
            self.optoforce.stop()
            self.optoforce.join()

    def _setup_optoforce(self):
        opto = OptoforceDriver(self.config.optoforce.name, self.config.optoforce.sensor_type,
                               [self.config.optoforce.scale])
        print(f'Building optoforce object...')
        opto_thread = OptoforceThread(opto)
        opto_thread.start()
        return opto_thread

    def reset(self):
        home_pos_x = np.copy(self.home_pos)
        tb_state = self.tb.req_data()
        home_pos_x[1] = tb_state['y']
        self.move_to(home_pos_x)
        self.move_to(self.home_pos)
        self.move_dyna_to_angle(0)

    def _setup_tb(self):
        self.logger.log_text('------------- Setting up TB -----------------')

        tb = TestBench(self.config.serial_name)
        while not tb.ready():
            time.sleep(0.1)
            tb.update()
        tb.flip_x_reset()
        time.sleep(0.2)
        tb.start()
        while tb.busy():
            tb.update()

        self.logger.log_text('----------------- Done ----------------------')
        self.logger.log_text(tb.req_data())
        return tb

    def _setup_dynamixel(self):
        self.dynamixel = Dynamixel(self.config.dynamixel.name, self.config.dynamixel.home_pos)
        if self.config.dynamixel.reset_on_start:
            self.move_dyna_to_angle(0)

    def _setup_cameras(self):
        cameras = []
        if not self.config.cameras:
            return cameras
        for camera_name, camera_conf in self.config.cameras.items():
            camera = Camera(camera_name, camera_conf.index, camera_conf.goal_height,
                            camera_conf.goal_width)
            camera_thread = CameraThread(camera, camera_conf.thread_rate)
            camera_thread.start()
            cameras.append(camera_thread)
        return cameras

    # Take a step in the environment, by having the action apply itself
    def step(self, action):
        action.apply(self)

    def move_to(self, position):
        position = np.array(position)
        position = np.clip(position, self.min_bounds, self.max_bounds)
        if np.any(position < self.min_bounds):
            self.logger.log_text(f'Position target {position} must be at least min bounds')
            return
        if np.any(position > self.max_bounds):
            self.logger.log_text(f'Position target {position} must be at most max bounds')
            return
        self.tb.target_pos(*position)
        while self.tb.busy():
            self.tb.update()
        self.logger.log_text(self.tb.req_data())

    def move_delta(self, position):
        tb_state = self.tb.req_data()
        x, y, z = tb_state['x'], tb_state['y'], tb_state['z']
        target = np.array(position) + np.array((x, y, z))
        self.move_to(target)

    def move_dyna_to_angle(self, angle):
        if self.dynamixel_bounds[0] <= angle <= self.dynamixel_bounds[1]:
            self.dynamixel.move_to_angle(angle)
        else:
            self.logger.log_text(f'Dynamixel cannot move to OOB pos {angle}')

    def get_current_image_obs(self):
        return {c_thread.get_name(): c_thread.get_frame() for c_thread in self.cameras}

    def get_current_raw_image_obs(self):
        return {c_thread.get_name(): c_thread.get_raw_frame() for c_thread in self.cameras}

    def get_tb_obs(self):
        return self.tb.req_data()

    def get_obs(self):
        obs = {'tb_state': self.get_tb_obs(),
               'images': self.get_current_image_obs(),
               'raw_images': self.get_current_raw_image_obs()}
        if self.config.dynamixel:
            obs['dynamixel_state'] = self.dynamixel.get_current_angle()
        if self.config.optoforce:
            obs['optoforce'] = self.optoforce.get_force()

        return obs
