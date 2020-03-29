#!/usr/bin/env python3

import socket
import sys
import hashlib
import pickle
import time

class Client():

    # define and create server socket
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(10)
        self.server_address = (ip, port)
        print('Server to send data as {} on port {}'.format(self.ip, self.port))
        # create window variables, no buffer and cumulative acknowledgement
        self.base = 1
        self.windowSize = 7
        self.window = []
    
    # get a packet from client
    def get_packet(self):
        packet, self.server_address = self.sock.recvfrom(4096)
        return pickle.loads(packet)

    # build a packet to be sent as either [message, checksum] or [seqnum, message, checksum]
    def build_packet(self, data, seqnum, corrupt):
        packet = []
        if seqnum:
            packet.append(seqnum)
        packet.append(data)

        # add checksum
        send_hash = hashlib.md5()
        send_hash.update(pickle.dumps(packet))
        packet.append(send_hash.digest())

        # append packet to window
        self.window.append(packet)

        # if we want to simulate a corrupt packet, change the checksum
        if corrupt:
            corrupt_packet = packet[:]
            send_hash.update(b"This Hash will corrupt packet.")
            corrupt_packet[-1] = send_hash.digest()
            return corrupt_packet
        # else return the correct packet
        else:
            return packet

    # send a packet to the client 
    def send_packet(self, data, seqnum=None, corrupt=False):
        packet = self.build_packet(data, seqnum, corrupt)
        self.sock.sendto(pickle.dumps(packet), self.server_address)

    # check checksum to make sure packet wasn't modified during transmission (don't need to check sequence number if corrupted)
    def check_checksum(self, packet):
        recv_checksum = packet[-1]
        del packet[-1]

        recv_hash = hashlib.md5()
        recv_hash.update(pickle.dumps(packet))

        return (recv_checksum == recv_hash.digest())

    # check if we got a message from server to close the connection
    def check_connection_closed(self, packet):
        return packet[0] == "Close Connection"

    # check whether we are dont transmitting all packets
    def check_not_done_transmission(self, nextSeqnum):
        return ((nextSeqnum < (self.base + self.windowSize)) and nextSeqnum < 11)

    # slide the client side packet window
    def slide_window(self, packet):
        while packet[0] >= self.base and self.window:
            del self.window[0]
            self.base = self.base + 1

    # according to GBN protocol, resend all packets in window when ACK not received
    def resend_packets(self, nextSeqnum):
        for i in self.window:
            self.sock.sendto(pickle.dumps(i), self.server_address)
        print("Did Not Receive Acknowledgement for Packet {}".format((self.base)))
        print("Resending Packets {} through {}".format(self.base, nextSeqnum-1))
        time.sleep(5)


def main():
    # setup socket
    client = Client('localhost', 10000)

    # initialize variables
    nextSeqnum = 1
    done = False
    time_last_packet_received = time.time()

    # main loop
    while not done:
        # check if we are done transmitting
        if (client.check_not_done_transmission(nextSeqnum)):
            print("Sending sequence number: {}".format(nextSeqnum))
            
            # simulate 0.2 loss rate by making packet's 5 and 7 corrupt
            if (nextSeqnum == 5 or nextSeqnum == 7):
                client.send_packet("hello", nextSeqnum, True)    # send corrupt packet
            else:
                client.send_packet("hello", nextSeqnum, False)   # send normal packet

            nextSeqnum = nextSeqnum + 1

        # receipt of ACK from server
        try:
            packet = client.get_packet()
            # check checksum
            if (client.check_checksum(packet)):
                # check if we are done
                if (packet[0] == 10):
                    client.send_packet("Close Connection")
                    done = True
                    print("All packets have been sent")
                # close connection if requested by server
                elif (client.check_connection_closed(packet)):
                    print("Connection closed by server")
                    break
                # otherwise print status of window and update window and base
                else:
                    print("I just received: {}".format(packet[0]))
                    # if checksum is good, slide window and reset the timer
                    time_last_packet_received = time.time()
                    client.slide_window(packet)
            # if checksum wasn't right, diregard packet and timeout will handle the error    
            else:
                print("There was an error in transmission")

        # timeout occurred
        except Exception as e:
            print("Exception occurred: {}".format(str(e)))
            # if server isn't responding with any ACKs, terminate connection
            if (time.time() - time_last_packet_received > 20):
                print("Server is not responding")
                break
            # if server has not responded in 5 seconds, resend all the packets in the window
            elif (time.time() - time_last_packet_received > 5):
                print("Server didn't respond after 5 sec, resend all packets in window.")
                client.resend_packets(nextSeqnum)

    client.sock.close()
    print("Connection closed")

if __name__ == "__main__":
    main()