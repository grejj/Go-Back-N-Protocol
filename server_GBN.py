#!/usr/bin/env python3

import socket
import sys
import hashlib
import pickle
import time

class Server():

    # define and create server socket
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_address = (ip, port)
        self.client_address = ()

        # bind ip address and port to socket
        print('Starting up on {} port {}'.format(self.ip, self.port))
        self.sock.settimeout(25)
        self.sock.bind(self.server_address)
    
    # get a packet from client
    def get_packet(self):
        packet, self.client_address = self.sock.recvfrom(4096)
        return pickle.loads(packet), len(packet)

    # send a packet to the client
    def send_packet(self, data):
        packet = self.build_packet(data)
        self.sock.sendto(pickle.dumps(packet), self.client_address)

    # check checksum to make sure packet wasn't modified during transmission (don't need to check sequence number if corrupted)
    def check_checksum(self, packet):
        recv_checksum = packet[-1]
        del packet[-1]

        recv_hash = hashlib.md5()
        recv_hash.update(pickle.dumps(packet))
        return (recv_checksum == recv_hash.digest())

    # check if sequence number received equals expected sequence number
    def check_sequence(self, packet, expectedseqnum):
        return packet[0] == expectedseqnum

    # create a packet message: [data, checksum]
    def build_packet(self, data):
        ack = []
        ack.append(data)
        send_hash = hashlib.md5()
        send_hash.update(pickle.dumps(ack))
        ack.append(send_hash.digest())
        return ack

    # check to see if got message from client to close connection
    def check_connection_closed(self, packet):
        return packet[0] == "Close Connection"

def main():
    # setup socket
    srv = Server('localhost',10000)
    
    # server only needs to compare received sequence number with the expected sequence number
    expectedseqnum = 1
    done = False
    output = []

    time_last_packet_received = time.time()

    while not done:
        try:
            # get a packet
            packet, packet_length = srv.get_packet()
            # check checksum
            if (srv.check_checksum(packet)):
                # check sequence number\
                if (srv.check_sequence(packet, expectedseqnum)):

                    print("Received packet {} it has {} bytes".format(packet[0], packet_length))
                    output.append(packet[1])

                    # send back an ACK
                    print("Sending ACK for {}".format(expectedseqnum))
                    srv.send_packet(expectedseqnum)

                    # increment expectedseqnum when got good packet (correct checksum and sequence number)
                    expectedseqnum = expectedseqnum + 1

                    time_last_packet_received = time.time()

                # check if client wants to close connection
                elif (srv.check_connection_closed(packet)):
                    print("Connection closed by client")
                    done = True
                    break

                else: # sequence number wrong
                    print("Invalid sequence number. Got: {} Expected: {}".format(packet[0], expectedseqnum))
                    print("Sending ACK for last good message with seqnum: {}".format(expectedseqnum - 1))
                    srv.send_packet(expectedseqnum - 1)
                
            else: # checksum failed
                print("Invalid checksum - error in transmission")

        # timeout occured
        except Exception as e:
            # If the last packet received was more than 10 seconds ago, tell client to close connection
            if (time.time() - time_last_packet_received > 10):
                srv.send_packet("Close Connection")
                print("Connection ended, sent close to client.")
                break
            # if the last packet received was more than 50 seconds ago, just end connection
            elif (time.time() - time_last_packet_received > 50):
                print("Not receiving any transmissions, connection closed")
                break
    
    srv.sock.close()
    print("Connection closed")
    print("The Final Output is {}".format(output))

if __name__ == "__main__":
    main()