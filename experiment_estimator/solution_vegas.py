"""
This demo aims to help player running system quickly by using the pypi library simple-emualtor https://pypi.org/project/simple-emulator/.
"""
from simple_emulator import CongestionControl

# We provided a simple algorithms about block selection to help you being familiar with this competition.
# In this example, it will select the block according to block's created time first and radio of rest life time to deadline secondly.
from simple_emulator import BlockSelection

# We provided some simple algorithms about congestion control to help you being familiar with this competition.
# Like Reno and an example about reinforcement learning implemented by tensorflow
from simple_emulator import Reno

import json, random, os, inspect
import numpy as np
from simple_emulator import CongestionControl
from objects.block import Block
from objects.packet import Packet
import pandas as pd
from utils import debug_print
from numpy import *
import csv
import math

EVENT_TYPE_FINISHED='F'
EVENT_TYPE_DROP='D'
EVENT_TYPE_TEMP='T'

tmp = [3, 2, 1]
# Your solution should include block selection and bandwidth estimator.
# We recommend you to achieve it by inherit the objects we provided and overwritten necessary method.


class SelectBlock:
    pass

class SelectPacket:
    pass


class MySolution(BlockSelection, Reno):

    def __init__(self):
        super().__init__()
        # base parameters in CongestionControl

        # the value of congestion window
        self.cwnd = 1
        # the value of sending rate
        self.send_rate = float("inf")
        # the value of pacing rate
        self.pacing_rate = float("inf")
        # use cwnd
        self.USE_CWND=True

        # for reno
        self.ssthresh = float("inf")
        # the number of lost packets
        self.drop_nums = 0
        # the number of acknowledgement packets
        self.ack_nums = 0

        # current time
        self.cur_time = 0
        # the value of cwnd at last packet event
        self.last_cwnd = 0
        # the number of lost packets received at the current moment
        self.instant_drop_nums = 0
        
        #用于block调度
        # the average RTT RTT = pacing_delay + latency
        #计算平均时延
        self.RTT_average = 0
        self.RTT_queue = []
        #cur_time更新
        self.cur_time_max = 0
        self.cur_time_block = 0
        #计算平均到达时间
        self.arrivaltime_last = 0
        self.arrivalslot_average = 0
        self.arrivalslot_queue = []
        #计算平均pacing_delay
        self.pacingdelay_average = 0
        self.pacingdelay_queue = []
        #计算丢包率
        self.ack_queue = [1]
        self.ack_ratio = 1
        

        # for vegas
        self.min_rtt =10000
        

    def select_block(self, cur_time, block_queue):
        '''
        The alogrithm to select the block which will be sended in next.
        The following example is selecting block by the create time firstly, and radio of rest life time to deadline secondly.
        :param cur_time: float
        :param block_queue: the list of Block.You can get more detail about Block in objects/block.py
        :return: int
        '''
        def is_better(block, cur_time, best_block):
            best_block_priority = float(tmp[int(best_block.block_info["Priority"])] / 3)
            cur_block_priority = float(tmp[int(block.block_info["Priority"])] / 3) 
            cur_left_time = block.block_info["Deadline"] - (cur_time - block.block_info["Create_time"])
            best_left_time = best_block.block_info["Deadline"] - (cur_time - best_block.block_info["Create_time"])
            if best_block.retrans:
                best_block_size = 1
            else: best_block_size = best_block.block_info["Split_nums"] - best_block.offset
            if block.retrans:
                cur_block_size = 1
            else: cur_block_size = block.block_info["Split_nums"] - block.offset
            
            
            # if block is miss ddl
            if block.block_info["Deadline"] - (cur_time - block.block_info["Create_time"]) < self.RTT_average:
                return False
            if best_block.block_info["Deadline"] - (cur_time - best_block.block_info["Create_time"]) < self.RTT_average:
                return True
            if block.block_info["Create_time"] != best_block.block_info["Create_time"]:
                
                return (best_block_priority/best_block_size) < (cur_block_priority/cur_block_size)
            return (cur_time - best_block.block_info["Create_time"]) * best_block.block_info["Deadline"] > \
                   (cur_time - block.block_info["Create_time"]) * block.block_info["Deadline"]
            
        def retrun_score(item, cur_time):
            left_time = item.block_info["Deadline"] - (cur_time - item.block_info["Create_time"])
            qoe = float(tmp[int(item.block_info["Priority"])] / 3)
            size = item.block_info["Split_nums"] - item.offset
            score = (qoe/size)*math.log(1+left_time, 10)
            return score

        #更新异常cur_time
        createtime_queue = [] 
        createtime_queue.append(self.cur_time_max)
        createtime_queue.append(self.cur_time_block)
        createtime_queue.append(cur_time)
        for idx, item in enumerate(block_queue):
            createtime_queue.append(item.block_info["Create_time"])
        cur_time = max(createtime_queue)
        self.cur_time_max = cur_time

        if block_queue == []:
            return None
        elif len(block_queue) == 1:
            best_block = block_queue[0]
            best_block_idx = 0
        else:

            select_best_block_queue = []
            best_block = None
            for idx, item in enumerate(block_queue):
                if best_block is None or is_better(item, cur_time, best_block):
                    best_block = item
            select_best_block_queue.append(best_block)
            select_block_queue = []
            for idx, item in enumerate(block_queue):
                if item != best_block:
                    select_block_queue.append(item)
            
            
            best_block = None
            for idx, item in enumerate(select_block_queue):
                if best_block is None or is_better(item, cur_time, best_block):
                    best_block = item
            select_best_block_queue.append(best_block)
            
            
            if select_best_block_queue == []:
                return None
            elif len(select_best_block_queue) == 1:
                best_block = select_best_block_queue[0]
            else:
                best_block_score_1 = retrun_score(select_best_block_queue[0], cur_time)
                best_block_score_2 = retrun_score(select_best_block_queue[1], cur_time)
                if best_block_score_1 > best_block_score_2:
                    best_block = select_best_block_queue[0]
                else:
                    best_block = select_best_block_queue[1]

            for idx, item in enumerate(block_queue):
                if best_block == item:
                    best_block_idx = idx
            
        return best_block_idx
        
        
        

    def on_packet_sent(self, cur_time):
        """
        The part of solution to update the states of the algorithm when sender need to send packet.
        """
        self.cur_time_block = cur_time
        return super().on_packet_sent(cur_time)



    def cc_trigger(self, cur_time, event_info):
        """
        The part of algorithm to make congestion control, which will be call when sender get an event about acknowledge or lost from reciever.
        See more at https://github.com/AItransCompetition/simple_emulator/tree/master#congestion_control_algorithmpy.
        """
        # for block 调度
        self.cur_time_block = cur_time
        num = 10
        self.last_cur_time = self.cur_time
        self.cur_time = cur_time
        self.ack_slot = self.cur_time - self.last_cur_time
        def mean_arrivalslot(cur_time, num):
            if len(self.arrivalslot_queue) < num:
                self.arrivalslot_queue.append(cur_time - self.arrivaltime_last)
            else:
                self.arrivalslot_queue.pop(0)
                self.arrivalslot_queue.append(cur_time - self.arrivaltime_last)
            self.arrivaltime_last = cur_time
            return mean(self.arrivalslot_queue)
        
        # 求平均RTT
        def mean_RTT(RTT, num):
            if len(self.RTT_queue) < num:
                self.RTT_queue.append(RTT)
            else:
                self.RTT_queue.pop(0)
                self.RTT_queue.append(RTT)
            return mean(self.RTT_queue)
            
        # 求平均pacing delay
        def mean_pacingdelay(pacingdelay, num):
            if len(self.pacingdelay_queue) < num:
                self.pacingdelay_queue.append(pacingdelay)
            else:
                self.pacingdelay_queue.pop(0)
                self.pacingdelay_queue.append(pacingdelay)
            return mean(self.pacingdelay_queue)
            
        self.arrivalslot = mean_arrivalslot(cur_time, num)             
        RTT = event_info["packet_information_dict"]["Latency"]
        self.RTT_average = mean_RTT(RTT, num) 
        pacingdelay = event_info["packet_information_dict"]["Pacing_delay"]
        self.pacingdelay_average = mean_pacingdelay(pacingdelay, num)
        
           
        #读取基本信息
        event_type = event_info["event_type"]
        event_time = cur_time                
        event_latency = event_info["packet_information_dict"]["Latency"]
        event_pacing_delay = event_info["packet_information_dict"]["Pacing_delay"]
        event_packet_sendtime = event_time - event_latency
        event_in_flight = event_info["packet_information_dict"]["Extra"]["inflight"]

        
        #计算丢包率
        if event_type == EVENT_TYPE_DROP:
            if len(self.ack_queue) < num:
                self.ack_queue.append(0)
            else: 
                self.ack_queue.pop(0)
                self.ack_queue.append(0)
        elif event_type == EVENT_TYPE_FINISHED:
            #ack包收到后跟新block调度信息
            self.arrivalslot_average = mean_arrivalslot(cur_time, num)             
            RTT = event_info["packet_information_dict"]["Latency"]
            self.RTT_average = mean_RTT(RTT, num) 
            pacingdelay = event_info["packet_information_dict"]["Pacing_delay"]
            self.pacingdelay_average = mean_pacingdelay(pacingdelay, num)
            #if event_time <= self.cur_time:
                #return
            if len(self.ack_queue) < num:
                self.ack_queue.append(1)
            else: 
                self.ack_queue.pop(0)
                self.ack_queue.append(1)
        


        #  更新最小rtt
        rtt = event_latency
        if (self.min_rtt >=rtt):
            self.min_rtt = rtt
        
        expect_bw = self.cwnd/self.min_rtt
        actual_bw = self.cwnd/rtt
        diff = (expect_bw - actual_bw)*self.min_rtt
        #上下阈值
        a = 1
        b = 3
        if(diff>b):
            self.cwnd = self.cwnd - 1
        elif(diff<a):
            self.cwnd = self.cwnd + 1
        else: 
            self.cwnd = self.cwnd 
            

        return {
            "cwnd" : self.cwnd,
             "send_rate" : self.send_rate,
        }