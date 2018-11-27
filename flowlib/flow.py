# -*- coding: utf-8 -*-
#
# !/usr/bin/env python3
#
# flow Copyright(c) 2018 Félix Molina.
#
# Many thanks to Télécom SudParis (http://www.telecom-sudparis.eu)
#
# MIT License
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#

from flowlib.consts import Direction
from flowlib.consts import Flag
from flowlib.consts import ConnectionState

from flowlib.consts import CONNECTION_FLAGS

from flowlib.packet import Packet

import time
import threading
import json


def get_current_milli():
    return int(round(time.time() * 1000))


class FlowInitException(Exception):
    pass


class Flow(object):

    def __init__(self, flow_id: int, source_ip: str, destination_ip: str, source_port: int, destination_port: int,
                 transport_protocol: int, app_protocol: int = None):
        super().__init__()

        try:
            self.__id = flow_id

            self.__source_ip = source_ip
            self.__destination_ip = destination_ip
            self.__source_port = source_port
            self.__destination_port = destination_port
            self.__transport_protocol = transport_protocol
            self.__app_protocol = app_protocol

            self.__flow_start_time = get_current_milli()
            self.__flow_end_time = 0
            self.__flow_duration_milliseconds = 0
            self.__last_received_packet_time = get_current_milli()
            self.__delta_time_between_packets = []

            self.__min_size = 0
            self.__max_size = 0
            self.__packet_sizes = []
            self.__delta_size_bytes = 0
            self.__sum_size_bytes = 0

            self.__min_ttl = 0
            self.__max_ttl = 0

            self.__direction = Direction.SourceToDestination
            self.__packet_list = []

            self.__hash_src_to_dst, self.__hash_dst_to_src = self.__hash()

            self.__timer = threading.Timer(60 * 5, self.close_flow)
            self.__closed = False
        except Exception as e:
            raise FlowInitException(str(e))

    def __compare(self, packet_hash):

        if packet_hash == self.__hash_src_to_dst:
            return 1
        elif packet_hash == self.__hash_dst_to_src:
            return 2
        else:
            return 0

    def __size_actualisation(self, size):
        self.__min_size = self.__min_size if size >= self.__min_size and self.__packet_list != [] else size
        self.__max_size = self.__max_size if size <= self.__max_size else size
        self.__delta_size_bytes = self.__max_size - self.__min_size
        self.__sum_size_bytes += size
        self.__packet_sizes += [size]

    def __ttl_actualisation(self, ttl):
        self.__min_ttl = self.__min_ttl if ttl >= self.__min_ttl and self.__packet_list != [] else ttl
        self.__max_ttl = self.__max_ttl if ttl <= self.__max_ttl else ttl

    def __flow_duration(self) -> None:
        """
        Private method.
        Achieve calculation of the flow duration.
        :rtype: None
        """
        self.__flow_end_time = get_current_milli()
        self.__flow_duration_microseconds = self.__flow_end_time - self.__flow_start_time

    def __add_packet(self, packet: Packet) -> None:
        """
        Private method.
        Use to append a new packet in the packet list of the flow object.
        :rtype: None
        :param packet: flowlib.packet.Packet
        """
        self.__packet_list += [packet]

    def __hash(self) -> (int, int):
        """
        Private personalized hashing method.
        It hashs the source and the destination IP and port, and the transport protocol number.
        :rtype: (int, int)
        :return: 2-tuple - hash of the Source to Destination direction, hash of the Destination to Source.
        """
        string1 = self.__source_ip + self.__destination_ip + str(self.__source_port) + str(self.__destination_port) +\
                 str(self.__transport_protocol)
        string2 = self.__destination_ip + self.__source_ip + str(self.__destination_port) + str(self.__source_port) +\
                 str(self.__transport_protocol)

        return hash(string1), hash(string2)

    def to_dict_format(self):
        return {
            "flowId": self.__id,
            "sourceIp": self.__source_ip,
            "destinationIp": self.__destination_ip,
            "sourcePort": self.__source_port,
            "destinationPort": self.__destination_port,
            "transportProtocol": self.__transport_protocol,
            "flowStartTime": self.__flow_start_time,
            "flowEndTime": self.__flow_end_time,
            "flowDurationMicrosenconds": self.__flow_duration_microseconds,
            "detlaTimeBetweenPackets": self.__delta_time_between_packets,
            "minSize": self.__min_size,
            "maxSize": self.__max_size,
            "packetSizes": self.__packet_sizes,
            "delatSizeBytes": self.__delta_size_bytes,
            "sumSizeBytes": self.__sum_size_bytes,
            "minTTL": self.__min_ttl,
            "maxTTL": self.__max_ttl,
            "direction": self.__direction.value
        }

    def to_json_format(self):
        return json.dumps(self.to_dict_format(), ensure_ascii=True)

    def close_flow(self, by_timer: bool = True):
        self.__closed = True

        if by_timer is not True:
            self.__timer.cancel()

    def aggregate(self, packet):
        if self.__closed is not True:
            if self.__compare(packet.get_hash()) == 2:
                self.__direction = Direction.BiDirectional
            elif self.__compare(packet.get_hash()) == 0:
                return False

            self.__size_actualisation(packet.get_length())
            self.__ttl_actualisation(packet.get_ttl())
            self.__flow_duration()

            if len(self.__packet_list) != 0:
                self.__delta_time_between_packets += [get_current_milli() - self.__last_received_packet_time]
                self.__last_received_packet_time = get_current_milli()

            self.__add_packet(packet)

            return True

        return False

    def is_closed(self):
        return self.__closed

    def packet_direction(self, packet):
        if self.__compare(packet.get_hash()) == 1:
            return Direction.SourceToDestination
        elif self.__compare(packet.get_hash()) == 2:
            return Direction.DestinationToSource

    def get_flow_id(self):
        return self.__id


class TCPFlow(Flow):

    def __init__(self, flow_id: int, source_ip: str, destination_ip: str, source_port: int, destination_port: int,
                 transport_protocol: int, app_protocol: int = None):
        super().__init__(flow_id=flow_id, source_ip=source_ip, destination_ip=destination_ip, source_port=source_port,
                         destination_port=destination_port, transport_protocol=transport_protocol,
                         app_protocol=app_protocol)

        self.__flags = CONNECTION_FLAGS
        self.__open = False

    def __follow_flag_flow(self, packet):
        direction = self.packet_direction(packet)
        for flag in packet.get_flags():
            if flag == Flag.SYN:
                if direction == Direction.SourceToDestination:
                    self.__flags[ConnectionState.ESTABLISHMENT][ConnectionState.SYN_SRC] = 1
                else:
                    self.__flags[ConnectionState.ESTABLISHMENT][ConnectionState.SYN_DST] = 1
            elif flag == Flag.FIN:
                if direction == Direction.SourceToDestination:
                    self.__flags[ConnectionState.TERMINATION][ConnectionState.FIN_SRC] = 1
                else:
                    self.__flags[ConnectionState.TERMINATION][ConnectionState.FIN_DST] = 1
            elif flag == Flag.ACK:
                if self.__flags[ConnectionState.ESTABLISHMENT][ConnectionState.SYN_DST] == 1 and \
                        direction == Direction.SourceToDestination and \
                        (self.__flags[ConnectionState.TERMINATION][ConnectionState.FIN_SRC] == 0 and
                         self.__flags[ConnectionState.TERMINATION][ConnectionState.FIN_DST] == 0):
                    self.__flags[ConnectionState.ESTABLISHMENT][ConnectionState.ACK_SRC] = 1
                elif self.__flags[ConnectionState.ESTABLISHMENT][ConnectionState.SYN_SRC] == 1 and \
                        direction == Direction.DestinationToSource and \
                        (self.__flags[ConnectionState.TERMINATION][ConnectionState.FIN_SRC] == 0 and
                         self.__flags[ConnectionState.TERMINATION][ConnectionState.FIN_DST] == 0):
                    self.__flags[ConnectionState.ESTABLISHMENT][ConnectionState.ACK_DST] = 1
                elif self.__flags[ConnectionState.TERMINATION][ConnectionState.FIN_DST] == 1 and \
                        direction == Direction.SourceToDestination and \
                        (self.__flags[ConnectionState.ESTABLISHMENT][ConnectionState.SYN_SRC] == 1 and
                         self.__flags[ConnectionState.TERMINATION][ConnectionState.SYN_DST] == 1):
                    self.__flags[ConnectionState.TERMINATION][ConnectionState.ACK_SRC] = 1
                elif self.__flags[ConnectionState.TERMINATION][ConnectionState.FIN_SRC] == 1 and \
                        direction == Direction.DestinationToSource and \
                        (self.__flags[ConnectionState.ESTABLISHMENT][ConnectionState.SYN_SRC] == 1 and
                         self.__flags[ConnectionState.ESTABLISHMENT][ConnectionState.SYN_DST] == 1):
                    self.__flags[ConnectionState.TERMINATION][ConnectionState.ACK_DST] = 1
                else:
                    pass

#    def aggregate(self, packet):
#        if super().aggregate(packet):
#            self.__follow_flag_flow(packet)
#            self.connection_state()
#
#            return True
#
#        return False

    def is_open(self):
        return self.__open

    def connection_state(self):
        if 0 not in self.__flags[ConnectionState.ESTABLISHMENT].values():
            self.__open = True

        if 0 not in self.__flags[ConnectionState.TERMINATION].values():
            self.__open = False
            self.close_flow(False)

        return {'open': self.is_open(), 'closed': self.is_closed()}
