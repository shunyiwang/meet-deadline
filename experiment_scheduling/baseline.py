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
        
        #����block����
        # the average RTT RTT = pacing_delay + latency
        #����ƽ��ʱ��
        self.RTT_average = 0
        self.RTT_queue = []
        #cur_time����
        self.cur_time_max = 0
        self.cur_time_block = 0
        #����ƽ������ʱ��
        self.arrivaltime_last = 0
        self.arrivalslot_average = 0
        self.arrivalslot_queue = []
        #����ƽ��pacing_delay
        self.pacingdelay_average = 0
        self.pacingdelay_queue = []
        #���㶪����
        self.ack_queue = [1]
        self.ack_ratio = 1
        

        # for bbr
        self.curr_state = "STARTUP"
        #���ڵ�״̬
        self.states = ["STARTUP","DRAIN","PROBE_BW","PROBE_RTT"]
        #״̬�б�
        self.bw =10 
        #��¼ÿ�β�����ʵ�ʴ���
        self.btl_bw =10
        #��¼ƿ������
        self.min_rtt =10000
        #��С��rtt
        self.pacing_gain = 1
        #pacing_rate������
        self.cwnd_gain = 1
        #cwnd����
        self.rtt_time =0
        #��¼���û����rtt
        self.last_time =0
        #rtt�ϴθ��µ�ʱ��
        self.rtt_begin_time =0
        #����rtt�׶εĿ�ʼʱ��
        self.rtt_duration =0
        #rtt�׶εĳ���ʱ��
        self.probebw_index =0
        #probe_bw�׶�ѭ����index
        self.pacing_gain_cycle = [1.25, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
        #probe_bw�׶�ѭ����pacing_rate�����б�
        self.startup_num = 0
        #��¼start_up�׶�������ȵĴ���
        self.BDP = 0
        #��ǰ��BDPֵ
        self.print_num =0
        #���ڳ��δ�ӡ��Ϣ�ļ���
        self.ack_num =0
        #��ǰ�յ�ACK����Ŀ
        self.inflight_num =0
        #��¼�����е����ݰ�����
        self.packet_queue = []
        #��������packet����
        self.bw_queue =[]
        #�����������bw���У���󳤶�Ϊ7
        self.last_bw = 0
        #��һ�β����Ĵ���
        self.last_cur_time = 0
        #�ϴε�cur_time
        self.ack_slot = 0.015
        #ACK���
        


    def select_block(self, cur_time, block_queue):
        '''
        The alogrithm to select the block which will be sended in next.
        The following example is selecting block by the create time firstly, and radio of rest life time to deadline secondly.
        :param cur_time: float
        :param block_queue: the list of Block.You can get more detail about Block in objects/block.py
        :return: int
        '''
        
        def is_better(block):
            best_block_create_time = best_block.block_info["Create_time"]
            cur_block_create_time = block.block_info["Create_time"]
            best_block_split_nums = best_block.block_info["Split_nums"]
            cur_block_split_nums = block.block_info["Split_nums"]
            best_block_deadline = best_block.block_info["Deadline"]
            cur_block_deadline = block.block_info["Deadline"]            
            best_block_priority = float(tmp[int(best_block.block_info["Priority"])] / 3)
            cur_block_priority = float(tmp[int(block.block_info["Priority"])] / 3) 
            best_block_offset =  best_block.offset
            cur_block_offset = block.offset

            
            # if block is miss ddl
            if (cur_time - cur_block_create_time) >= block.block_info["Deadline"]:
                return False
            if (cur_time - best_block_create_time) >= best_block.block_info["Deadline"]:
                return True
            if best_block_create_time != cur_block_create_time:
                return (best_block_priority/(best_block_split_nums - best_block_offset)) < (cur_block_priority/(cur_block_split_nums - cur_block_offset))
            return (cur_time - best_block_create_time) * best_block.block_info["Deadline"] > \
                   (cur_time - cur_block_create_time) * block.block_info["Deadline"]

        best_block_idx = -1
        best_block= None
        for idx, item in enumerate(block_queue):
            if best_block is None or is_better(item) :
                best_block_idx = idx
                best_block = item
               
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
        # for block ����
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
        
        # ��ƽ��RTT
        def mean_RTT(RTT, num):
            if len(self.RTT_queue) < num:
                self.RTT_queue.append(RTT)
            else:
                self.RTT_queue.pop(0)
                self.RTT_queue.append(RTT)
            return mean(self.RTT_queue)
            
        # ��ƽ��pacing delay
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
        
           
        #��ȡ������Ϣ
        event_type = event_info["event_type"]
        event_time = cur_time                
        event_latency = event_info["packet_information_dict"]["Latency"]
        event_pacing_delay = event_info["packet_information_dict"]["Pacing_delay"]
        event_packet_sendtime = event_time - event_latency
        event_in_flight = event_info["packet_information_dict"]["Extra"]["inflight"]

        
        #���㶪����
        if event_type == EVENT_TYPE_DROP:
            if len(self.ack_queue) < num:
                self.ack_queue.append(0)
            else: 
                self.ack_queue.pop(0)
                self.ack_queue.append(0)
        elif event_type == EVENT_TYPE_FINISHED:
            #ack���յ������block������Ϣ
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
        
        
        
        #��¼ACK����
        if(event_type != EVENT_TYPE_FINISHED):
           return 
        
        #��¼�ϴβ������� 
        self.last_bw = self.bw
        #�������
        if(self.ack_slot != 0):
          #self.bw = 1.048576/self.ack_slot
          self.bw = 1/self.ack_slot
        def top1(lst):
          return max(lst, default='', key=lambda v: lst.count(v))
               
        #����������
        if(len(self.bw_queue) >= 7):
          self.bw_queue.pop(0)            
        self.bw_queue.append(self.bw)
              #self.btl_bw = max(self.bw_queue)
        self.btl_bw = top1(self.bw_queue)

        #  ������Сrtt
        rtt = event_latency
        if (self.min_rtt >=rtt):
            self.min_rtt = rtt
            
        #����״̬ת��
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
           self.pacing_gain = 1.0
           self.cwnd = 1.0
           if(event_latency == self.min_rtt ):
                self.curr_state = self.states[0]
              
        #����pcing_rate��cwnd
        self.pacing_rate = self.pacing_gain*self.btl_bw
        self.cwnd = max(math.floor(self.cwnd_gain * self.btl_bw *self.min_rtt),4)

        return {
            "cwnd" : self.cwnd,
             "send_rate" : self.send_rate,
            "pacing_rate" : self.pacing_rate
        }