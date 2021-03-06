import copy
import math
import numpy as np
import cv2
from threading import Semaphore

import rospy
from nav_msgs.srv import GetMap
from geometry_msgs.msg import Pose
from nav_msgs.msg import OccupancyGrid

from Node import Node


class Graph:
    def __init__(self, service_map_name, occ_grid_topic):
        self.nodes = None
        self.resolution = 0
        self.width = 0
        self.height = 0
        self.occ_grid = None  # type: np.array
        self.semaphore = Semaphore()

        self.resize = rospy.get_param("/voronoi/topic_info/occ_grid_resize", 1)

        service_map = rospy.ServiceProxy(service_map_name, GetMap)
        occ_g = service_map()
        self.set_occ_grid(occ_g.map)

    def occ_grid_callback(self, msg):
        # type: (OccupancyGrid) -> None
        print()
        self.set_occ_grid(msg)

    def set_occ_grid(self, map_msg):
        # type: (OccupancyGrid) -> None
        self.semaphore.acquire()
        rospy.loginfo("Setting occupancy grid")
        self.width = map_msg.info.width/self.resize
        self.height = map_msg.info.height/self.resize
        self.resolution = map_msg.info.resolution*self.resize
        self.occ_grid = self.build_occ_grid(map_msg)
        self.build_graph()
        rospy.logwarn("Occupancy grid updated!")
        self.semaphore.release()

    def build_occ_grid(self, map_msg):
        occ_grid = np.mat(map_msg.data).reshape(map_msg.info.height, map_msg.info.width)  # type: np.array()
        return occ_grid.transpose()

    def get_node(self, pose):
        """
        Gets a node based on the pose provided as an array [x,y]
        :type pose: ?
        """
        p = copy.deepcopy(pose)
        p_arr = []

        if type(p) is Pose:   # convert
            x = p.position.x
            y = p.position.y
            p_arr = [x, y]
        elif isinstance(p, list):
            if not p or len(p) < 2:
                return None
            p_arr = p
        else:
            raise ValueError("Unrecognized type " + str(type(pose)) + " for conversion from node to pose")

        xc = int(math.floor(p_arr[0] / self.resolution))
        yc = int(math.floor(p_arr[1] / self.resolution))
        return self.nodes[xc, yc]

    def get_node_from_index(self, i, j):
        # type: (int, int) -> Node
        if 0 <= i < self.width and 0 <= j < self.height:
            return self.nodes[i, j]
        else:
            return None

    def build_graph(self):
        """
        Builds a graph based on the occupancy grid information
        :type height: int
        :type width: int
        :type resolution: float
        """

        self.nodes = np.empty((self.width, self.height), dtype=object)

        for i in range(self.width):
            for j in range(self.height):
                node = Node()
                node.indexes = [i, j]
                node.set_pose(self.get_pose(i, j))
                if 0 <= self.occ_grid[i, j] <= 20:
                    node.valid = True
                else:
                    node.valid = False
                self.nodes[i][j] = node

        for i in range(self.width):
            for j in range(self.height):
                if self.nodes[i, j].valid:
                    min_i = max(0, i - 1)
                    max_i = min(self.width - 1, i + 1) + 1
                    min_j = max(0, j - 1)
                    max_j = min(self.height - 1, j + 1) + 1

                    neighbors = self.nodes[min_i:max_i, min_j:max_j].flatten()
                    for n in neighbors:
                        if n is not self.nodes[i, j]:
                            if n.valid:
                                self.nodes[i, j].neighbors.append(n)
                            else:
                                self.nodes[i, j].obstacle_neighbors.append(n)
                    if len(self.nodes[i, j].neighbors) > 8:
                        rospy.loginfo("more neighbors than it should")

    def get_pose(self, i, j):
        """
        Get the pose correspondent to the node at index i,j of the graph matrix
        :type i: int
        :type j: int
        """
        x = i * self.resolution + self.resolution/2
        y = j * self.resolution + self.resolution/2
        return [x, y]

    def clear_graph(self):
        for i in range(self.width):
            for j in range(self.height):
                self.nodes[i, j].clear()

    def occ_grid_resample(self, occ_grid, width, height, resampling):
        new_grid = np.zeros((width/resampling, height/resampling), int)
        i_new = 0
        j_new = 0
        for i in range(0, height, resampling):
            j = 0
            for j in range(0, width, resampling):
                block = occ_grid[j:j+resampling, i:i+resampling].flatten()  # type: np.array
                avg = np.sum(block) / block.shape[0]
                new_grid[j_new, i_new] = avg
                j_new += 1
            i_new += 1
        return new_grid

