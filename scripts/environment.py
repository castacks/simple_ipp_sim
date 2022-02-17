import math
import random
from turtle import heading
import numpy as np
from vehicle import *
from target import *
from sensor import *
from geographic_msgs.msg import GeoPose


class Environment:
    def __init__(self, targets=[], max_omega=5, max_zvel = 5,
                init_x=0, init_y=0, init_z=0, init_psi=0, 
                K_p=0.01, K_p_z=0.01,
                vehicle_l=3, hvel=5, vvel=2, n_rand_targets=-1, del_t=1, waypt_threshold=5,
                sensor_focal_length=5, sensor_width=10, sensor_height=10, sensor_a=1, 
                sensor_b=1, sensor_d=1, sensor_g=1, sensor_h=1, sensor_pitch=20):
        '''
        Setup simulation environment
        '''
        # if initial position not specified, randomly spawn vehicle between (50, 1000)
        if init_x is 0 and init_y is 0 and init_z is 0:
            init_x = random.randrange(50, 1000)
            init_y = random.randrange(50, 1000)
            init_z = random.randrange(20, 120, 20) # discretized by step-size 20
            init_psi = random.uniform(0, np.pi)
        
        # vehicle pose
        self.init_x = init_x
        self.init_y = init_y
        self.init_z = init_z
        self.init_psi = init_psi 

        self.del_t = del_t
        
        self.vehicle_l = vehicle_l  # vehicle length
        self.hvel = hvel  # horizontal velocity
        self.vvel = vvel  # vertical velocity
        self.max_omega = max_omega  # max angular velocity
        self.max_zvel = max_zvel  # max vertical velocity

        self.sensor_focal_length = sensor_focal_length
        self.sensor_width = sensor_width
        self.sensor_height = sensor_height
        self.sensor_a = sensor_a
        self.sensor_b = sensor_b
        self.sensor_d = sensor_d
        self.sensor_g = sensor_g
        self.sensor_h = sensor_h
        self.sensor_pitch = sensor_pitch

        self.targets = targets

        self.global_waypt_list = []

        self.n_rand_targets = n_rand_targets

        if self.targets == []:
            # if targets not specified, randomly generate between 1-10 targets
            if n_rand_targets == -1:
                self.n_rand_targets = random.randrange(1, 10)                
        
        self.waypt_threshold = waypt_threshold

        self.K_p = K_p  # x-y proportionality constant for PID controller
        self.K_p_z = K_p_z  # z-axis proportionality constant for PID controller

        self.generate_targets()
        self.vehicle = self.init_vehicle()
        self.sensor = self.init_sensor()

        self.curr_waypt_num = 0
    
    def generate_targets(self):
        '''
        Generates ships with initial positions
        '''

        # when no targets specified
        if self.targets == [] and self.n_rand_targets != -1:
            for i in range(self.n_rand_targets):
                # creating list of random target objects
                self.targets.append(
                    Target(
                        init_x = random.randrange(50, 1000),
                        init_y = random.randrnge(50, 1000),
                        vel = [random.uniform(0, 3), random.uniform(0, 3)],
                        phi = random.uniform(0, np.pi),
                    )
                )
        # when targets are specified
        else:
            t_tuples = self.targets
            self.targets = []
            for target in t_tuples:
                self.targets.append(
                    Target(
                        init_x=target[0],
                        init_y=target[1],
                        vel=target[2],
                        phi=target[3]
                    )
                )
    
    def init_vehicle(self):
        return Vehicle(init_x=self.init_x,
                        init_y=self.init_y,
                        init_z=self.init_z,
                        init_psi=self.init_psi,
                        vehicle_l=self.vehicle_l,
                        hvel=self.hvel,
                        vvel=self.vvel)
    
    def init_sensor(self):
        return SensorModel(self.sensor_a, 
                            self.sensor_b, 
                            self.sensor_d,
                            self.sensor_g,
                            self.sensor_h,
                            self.sensor_width,
                            self.sensor_height,
                            self.sensor_focal_length)
    
    def get_ground_intersect(self, vehicle_pos, pitch, yaw):
        return self.sensor.reqd_plane_intercept(vehicle_pos, 
                    self.sensor.rotated_camera_fov(phi=pitch, psi=yaw))


    def get_sensor_measurements(self):
        '''
        Get sensor measurements from camera sensor
        '''
        camera_projection = self.get_ground_intersect([self.vehicle.x, self.vehicle.y, self.vehicle.z], self.sensor_pitch, self.vehicle.psi)
        detected_targets = []
        for target in self.targets:
            if self.sensor.is_point_inside_camera_projection([target.x, target.y], camera_projection):
                range_to_target = np.linalg.norm(np.array([target.x, target.y, 0]) - np.array([self.vehicle.x, self.vehicle.y, self.vehicle.z]))
                # is_detected = self.sensor.get_detection(range_to_target)
                detection_prob = np.random.random()
                sensor_tpr = self.sensor.tpr(range_to_target)
                if detection_prob < sensor_tpr:
                    target.is_detected = True
                    detected_targets.append(target)
        return detected_targets, camera_projection

    def traverse(self):
        '''
        Waypoint manager and vehicle state update- moves vehicle towards waypoints as long as waypoints exist in global_waypt_list
        '''
        self.get_sensor_measurements()
        if not self.global_waypt_list or len(self.global_waypt_list.plan) == 0:
            return
        else:
            next_position = np.array([self.global_waypt_list.plan[0].position.position.x,
                                        self.global_waypt_list.plan[0].position.position.y,
                                        self.global_waypt_list.plan[0].position.position.z])
            dist_to_waypt = np.linalg.norm([self.vehicle.x, self.vehicle.y, self.vehicle.z] - next_position)
            
            # update waypoint list if reached waypoint
            if dist_to_waypt < self.waypt_threshold:
                print ("Reached waypoint -> ", next_position)
                self.curr_waypt_num += 1
                self.global_waypt_list.plan.pop(0)
            
            # else keep trying to navigate to next waypoint
            else:
                omega, z_d = self.vehicle.go_to_goal(self.max_omega, self.max_zvel, next_position, self.K_p, self.K_p_z)
                self.vehicle.psi += self.del_t*omega
                self.vehicle.x += self.del_t*self.hvel*math.cos(self.vehicle.psi)
                self.vehicle.y += self.del_t*self.hvel*math.sin(self.vehicle.psi)
                self.vehicle.z += self.del_t*z_d 
                
    
    def update_waypts(self, new_wpts):
        '''
        Receive new waypoints and send them to waypoint manager
        '''
        # self.global_waypt_list.append(new_wpts)
        self.global_waypt_list = new_wpts
        self.curr_waypt_num = 0
        
    
    def update_states(self):
        '''
        Updates the environment states
        '''
        self.traverse()

        # update the states for all ships in the environment
        for target in self.targets:
            target.propagate(self.del_t)
    
    def get_vehicle_uncertainty(self):
        return self.vehicle.position_uncertainty()
    
    # function that gets target heading and return heading with gaussian noise
    def get_target_heading_noise(self, heading):
        # gaussian noise model for now
        return heading + np.random.normal(0, 0.05)
        