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
class SelectBlock:
    pass

class SelectPacket:
    pass
# Your solution should include block selection and bandwidth estimator.
# We recommend you to achieve it by inherit the objects we provided and overwritten necessary method.
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
        
        #????block????
        # the average RTT RTT = pacing_delay + latency
        #????????????
        self.RTT_average = 0
        self.RTT_queue = []
        #cur_time????
        self.cur_time_max = 0
        self.cur_time_block = 0
        #????????????????
        self.arrivaltime_last = 0
        self.arrivalslot_average = 0
        self.arrivalslot_queue = []
        #????????pacing_delay
        self.pacingdelay_average = 0
        self.pacingdelay_queue = []
        #??????????
        self.ack_queue = [1]
        self.ack_ratio = 1
        
        # for bbr
        self.curr_state = "STARTUP"
        #??????????
        self.states = ["STARTUP","DRAIN","PROBE_BW","PROBE_RTT"]
        #????????
        self.bw =10 
        #??????????????????????
        self.btl_bw =10
        #????????????
        self.min_rtt =10000
        #??????rtt
        self.pacing_gain = 1
        #pacing_rate??????
        self.cwnd_gain = 1
        #cwnd????
        self.rtt_time =0
        #??????????????rtt
        self.last_time =0
        #rtt??????????????
        self.rtt_begin_time =0
        #????rtt??????????????
        self.rtt_duration =0
        #rtt??????????????
        self.probebw_index =0
        #probe_bw??????????index
        self.pacing_gain_cycle = [1.25, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
        #probe_bw??????????pacing_rate????????
        self.startup_num = 0
        #????start_up??????????????????
        self.BDP = 0
        #??????BDP??
        self.print_num =0
        #??????????????????????
        self.ack_num =0
        #????????ACK??????
        self.inflight_num =0
        #??????????????????????
        self.packet_queue = []
        #??????????packet????
        self.bw_queue =[]
        #??????????????bw????????????????10
        self.last_bw = 0
        #????????????????
        self.last_cur_time = 0
        #??????cur_time
        self.ack_slot = 0.015
        #ACK????
        
        
        
    def select_block(self, cur_time, block_queue):
        '''
        The alogrithm to select the block which will be sended in next.
        The following example is selecting block by the create time firstly, and radio of rest life time to deadline secondly.
        :param cur_time: float
        :param block_queue: the list of Block.You can get more detail about Block in objects/block.py
        :return: int
        '''
        
        
        #????????????
        def construct_send_queue(cur_time, best_block):
            select_packet = SelectPacket()
            select_packet.packet_id = best_block.packet_id
            select_packet.select_time = cur_time
            self.send_queue.append(select_packet)
            
            
        # ????block????????
        def construct_block_queue(sendtime_estimated, block_queue):
            self.ack_ratio = sum(self.ack_queue)/len(self.ack_queue)
            select_block_queue = []

            
            for idx, item in enumerate(block_queue): 

                block_qoe = float(tmp[int(item.block_info["Priority"])] / 3) #qoe
                tolerate_weight = (1 - 0.3 * math.log(block_qoe/(item.block_info["Split_nums"] - item.offset),10)) * 1.02
                block_idx = idx
                block_offset = item.offset
                block_left_time = item.block_info["Deadline"] - (sendtime_estimated - item.block_info["Create_time"]) #left time
                if item.retrans:
                    block_estimated_latency = self.RTT_average
                    block_used_time = self.arrivalslot_average
                else:
                    block_estimated_latency = tolerate_weight * ((item.block_info["Split_nums"] - item.offset - 1) * self.arrivalslot_average + 1.1 * self.RTT_average + self.pacingdelay_average) #bloak_latency
                    block_used_time = self.arrivalslot_average*(item.block_info["Split_nums"] - item.offset - 1)
                select_block = SelectBlock()
                select_block.split_nums = item.block_info["Split_nums"]
                select_block.idx = block_idx 
                select_block.offset = block_offset
                select_block.left_time = block_left_time
                select_block.estimated_latency = block_estimated_latency  
                select_block.qoe = block_qoe 
                select_block.used_time = block_used_time
                select_block.option = False                     
                select_block_queue.append(select_block)
            return select_block_queue
            
        # ????left_time????
        def get_left_time(item):
            keyValue = item.left_time*(item.split_nums - item.offset)/item.qoe
            return keyValue
        
        # ????latency????
        def get_latency(item):
            keyValue = float(item.left_time-item.estimated_latency)
            return keyValue
        
        
        # ????score????
        def get_score(item):
            keyValue = float(item.left_time - item.estimated_latency)
            return keyValue
            
        # ????????????block
        def find_bestblock(select_block_queue, used_time):
            if select_block_queue == []:
                return 0       
            else:
                for idx, item in enumerate(select_block_queue):
                    if item.left_time - used_time < item.estimated_latency:
                        return - item.qoe + find_bestblock(select_block_queue[1:], used_time)
                    else:
                        temp1 = - item.qoe + find_bestblock(select_block_queue[1:], used_time)                
                        temp2 = item.qoe - item.used_time + find_bestblock(select_block_queue[1:], used_time + item.used_time)
                        if temp1 > temp2:
                            item.option = False
                            return temp1
                        else:
                            item.option = True
                            return temp2                   
        #????????block
        def return_bestblock(select_block_queue):
            for idx, item in enumerate(select_block_queue): 
                if item.option:
                    return item
                    

        
        
        #????????cur_time
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
        else:
            sendtime_estimated = cur_time
            select_block_queue = construct_block_queue(sendtime_estimated, block_queue) 
            #????miss deadline??block

            select_block_queue.sort(key=get_latency)
            will_miss_block = []
            for idx, item in enumerate(select_block_queue):
                if item.left_time < item.estimated_latency:
                    will_miss_block.append(item)        
            for idx_miss, item_miss in enumerate(will_miss_block): 
                if len(select_block_queue)>1:
                    select_block_queue.remove(item_miss)
            
            if len(select_block_queue) == 1:#??????????????blcok
                select_best_block = select_block_queue[0]
            else:
                #????score????
                select_block_queue.sort(key=get_score)
                select_best_block = select_block_queue[0]
            
            best_block_idx = select_best_block.idx
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
        # for block ????
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
        
        # ??????RTT
        def mean_RTT(RTT, num):
            if len(self.RTT_queue) < num:
                self.RTT_queue.append(RTT)
            else:
                self.RTT_queue.pop(0)
                self.RTT_queue.append(RTT)
            return mean(self.RTT_queue)
            
        # ??????pacing delay
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
        
           
        #????????????
        event_type = event_info["event_type"]
        event_time = cur_time                
        event_latency = event_info["packet_information_dict"]["Latency"]
        event_pacing_delay = event_info["packet_information_dict"]["Pacing_delay"]
        event_packet_sendtime = event_time - event_latency
        event_in_flight = event_info["packet_information_dict"]["Extra"]["inflight"] 
        
        #??????????
        if event_type == EVENT_TYPE_DROP:
            if len(self.ack_queue) < num:
                self.ack_queue.append(0)
            else: 
                self.ack_queue.pop(0)
                self.ack_queue.append(0)
        elif event_type == EVENT_TYPE_FINISHED:
            #ack????????????block????????
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
        
        
        
        #????ACK????
        if(event_type != EVENT_TYPE_FINISHED):
           return 
        
        #???????????????? 
        self.last_bw = self.bw
        #????????
        if(self.ack_slot != 0):
          #self.bw = 1.048576/self.ack_slot
          self.bw = 1/self.ack_slot
        def top1(lst):
          return max(lst, default='', key=lambda v: lst.count(v))
               
        #????????????
        if(len(self.bw_queue) >= 7):
          self.bw_queue.pop(0)            
        self.bw_queue.append(self.bw)
              #self.btl_bw = max(self.bw_queue)
        self.btl_bw = top1(self.bw_queue)

        #  ????????rtt
        rtt = event_latency
        if (self.min_rtt >=rtt):
            self.min_rtt = rtt
            
        #????????????
        if self.curr_state == self.states[0]:    
           self.pacing_gain = 2.0
           self.cwnd_gain =  1.40 
           
           if(math.floor(self.bw)==math.floor(self.btl_bw)):
                self.startup_num = self.startup_num +1
           else:
                self.startup_num = 0
           if(self.startup_num >1):
                self.curr_state = self.states[1]
                self.startup_num  =0  
               
        if self.curr_state == self.states[1]:
           self.pacing_gain = 0.5
           self.cwnd_gain = 1.3
           if(self.cwnd >= event_in_flight ): 
              self.curr_state = self.states[2]
                    
        if self.curr_state == self.states[2]:
           self.pacing_gain = self.pacing_gain_cycle[self.probebw_index]
           self.cwnd_gain = 1.0
           self.probebw_index = self.probebw_index +1
           if(self.probebw_index ==8):
               self.probebw_index =0
           if(event_latency == 1.00*self.min_rtt ):
               self.curr_state = self.states[0]
           if(event_latency >=self.min_rtt * 1.25):
               self.curr_state = self.states[3]
               
        if self.curr_state == self.states[3]:
           self.pacing_gain = 1
           self.cwnd = 1.0
           if(event_latency == self.min_rtt ):
                self.curr_state = self.states[0]
              
        #????pcing_rate??cwnd
        self.pacing_rate = self.pacing_gain*self.btl_bw
        self.cwnd = max(math.floor(self.cwnd_gain * self.btl_bw *self.min_rtt),4)

        return {
            "cwnd" : self.cwnd,
             "send_rate" : self.send_rate,
            "pacing_rate" : self.pacing_rate
        }