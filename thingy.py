import sys
import argparse
import socket
import logging
import re
import struct
import errno
from Queue import Queue, Empty
from threading import Thread
from questions import answer

class UDPReceiver(Thread):
    sock = None
    stop_flag = False
    que = None
    
    def __init__(self, sock, que):
        Thread.__init__(self)
        self.sock = sock
        self.sock.settimeout(0)
        self.stop_flag = False
        self.que = que
        
    def run(self):
        # No socket so stop right away
        if not self.sock:
            return
        
        # Execute until stop flag gets set
        while not self.stop_flag:
            try:
                recv = self.sock.recvfrom(1024)
                self.que.put(recv)
                if not recv:
                    break
            except socket.error as err:
                if err.errno == errno.EAGAIN:
                    # Timeout reached, continue
                    continue
                break

    def stop(self):
        self.stop_flag = True

class UDPClient():
    PROTOCOL_FORMAT = '!??HH64s'
    
    listen_port = None
    sock = None
    stop_flag = False
    rq = None
    msg_list = []
    receiver = None
    eom_received = False
    server_info = None
    
    def __init__(self):
        self.logger = logging.getLogger('UDPClient')
        self.logger.info('Initialized')
        self.rq = Queue(0)
        
    """ Setup the UDP socket and start accepting incoming connections. Returns True on successful
        socket creation and binding. False otherwise
    """
    def init_socket(self):
        if self.listen_port and not self.sock:
            try:
                # Initialize socket
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                # Bind to local port
                self.sock.bind(('', self.listen_port))
                # Create receiving thread and start it
                self.receiver = UDPReceiver(self.sock, self.rq)
                self.receiver.start()
                return True
            except socket.error as exc:
                self.logger.error("Socket error: %s" % exc)
        else:
            self.logger.debug("Connection parameters not set!")
        return False
    
    def close(self):
        try:
            # Stop receiving thread and wait until it stops
            if self.receiver:
                self.receiver.stop()
                self.receiver.join()
            if self.sock:
                self.sock.close()
                self.sock = None
        except Exception as ex:
            self.logger.error('Exception on socket closing %s' % ex)

    def set_listen_port(self, port = 10000):
        self.listen_port = port

    def send_raw(self, address, data):
        if self.sock and address and data:
            self.sock.sendto(data, address)
            return True
        return False
    
    def send(self, data, eom=False, ack=True):
        # Generate packets from data
        self.logger.debug('Sending \'%s\'' % data)
        packets = self.packetise(eom, ack, data)
        if packets:
            for packet in packets:
                self.send_raw(self.server_info, packet)
    
    def send_nack(self):
        self.send('Send again.', False, False)
    
    """ Returns a tuple containing packet data, source address and port: (data, (address, port))
        Or None in case there is a problem with socket or queue
    """
    def get_next_message(self):
        if not self.rq:
            return None
        
        # Last received packet remaining field
        last_remaining = None        
        msg = ''
        chunks = 0
        # Read packets until queue is empty
        while True:
            try:
                data, addr = self.rq.get()
                eom, ack, chunk_len, last_remaining, msg_chunk = self.unpack(data)
                msg_chunk = msg_chunk.rstrip(chr(0))
                # Check source address and port, if they don't match the configured ones, NACK the message
                # and request resend
                if not addr == self.server_info:
                    self.logger.debug('Different source address in received packet: %s != %s' % (addr, self.server_info))
                    self.send_nack() 
                # Compare header length to stripped chunk length, if chunk length is 
                # greater than length in header field, then we have invalid packet and
                # need to nack to request new transmission
                clen = len(msg_chunk)
                if chunk_len < clen:
                    self.logger.debug('Invalid chunk length expected %d got %d' % (chunk_len, clen))
                    self.send_nack()
                    return None
                 
                msg = msg + msg_chunk
                chunks += 1
                if eom:
                    self.eom_received = True
                if last_remaining == 0:
                    break
            except Empty:
                if last_remaining is None:
                    # No packets in queue? return None
                    return None
                pass
        self.logger.debug('Received %d chunks' % chunks)
        return msg, addr
        
    
    """ Packetises given eom, ack and content into a list of packets with content length of 64
        each, left justified with null character padding if content is shorter than 64 bytes.
        Packet format is [EOM:bool][ACK:bool][LEN:short][REMAINING:short][DATA:char*64]
        Returns the list of packed packets or None if no valid packets can be created
    """
    def packetise(self, eom, ack, content):
        if not (isinstance(eom, bool) and isinstance(ack, bool) and isinstance(content, str)) and len(content) > 0:
            return None
        
        remaining = content
        
        packets = []
        d = remaining[:64]
        while d:
            # Slice new remaining bytes from end
            remaining = remaining[64:]
            
            # Packetise d left justified with null characters if necessary to get 64 bytes.
            packets.append(struct.pack(self.PROTOCOL_FORMAT, eom, ack, len(d), len(remaining), d.ljust(64, chr(0))))
            
            self.logger.debug('Packed eom=%r, ack=%r, len=%d, remaining=%d' % (eom, ack, len(d), len(remaining)))
            
            # Get new packet data from remaining bytes, if any left
            d = remaining[:64]
        
        return packets
    
    """ Unpacks given data and returns a tuple (EOM, ACK, len, remaining, content), where
        content will be set to len length if data matches protocol format. None is returned
        if data has no packet matching protocol format.
    """
    def unpack(self, data):
        if not data:
            return None
        
        # Take only amount of bytes that matches protocol format length
        data = data[:struct.calcsize(self.PROTOCOL_FORMAT)]
        
        packet = None
        try:
            eom, ack, length, rem, content = struct.unpack(self.PROTOCOL_FORMAT, data)
            self.logger.debug('Unpacked eom=%r, ack=%r, len=%d, remaining=%d' % (eom, ack, length, rem))
        except:
            self.logger.error('Invalid data length!')
        
        return (eom, ack, length, rem, content.rstrip(chr(0)))
    
    def set_server_info(self, addr, port):
        if isinstance(port, str):
            try:
                port = int(port)
            except:
                self.logger.error('Invalid port format')
        self.server_info = (addr, port)

class TCPClient:
    
    server = {
              'address': None,
              'tcp_port': None,
              'udp_port': None,
              'capabilities': ''
              }
    logger = None
    
    def __init__(self, server_address, server_port):
        self.server['address'] = server_address
        self.server['tcp_port'] = server_port
        self.logger = logging.getLogger('TCPClient')
        self.logger.info('Initialized')
    
    """ Used to communicate the listening UDP port and capabilities of the client
        to the server, and receive server UDP port and capabilities. Returns True on 
        receiving valid connection parameters from server. Otherwise False is returned.
    """
    def connection_request(self, udp_listen_port, capabilities=''):
        if udp_listen_port is None:
            self.logger.error('No UDP port given')
            return False
        
        try:
            # Format the hello message
            if capabilities:
                data = 'HELO %d %s\r\n' % (udp_listen_port, capabilities)
            else:
                data = 'HELO %d\r\n' % udp_listen_port
        except TypeError:
            self.logger.error('Invalid UDP port')
            return False
        
        response = None
        try:
            """ Try creating TCP socket, connecting to given address:port, sending the message
                and receiving a response finally closing the socket
            """
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((self.server['address'], self.server['tcp_port']))
            sock.sendall(data)
            response = sock.recv(1024)
            sock.close()
        except:
            self.logger.error('Socket connection error')
        
        if response:
            """ Valid response received, so let's try parsing the UDP port and possible capabilities
                from it
            """
            m = re.search('\w+ (\d+)[ ]?([MCIA]*)', response)
            if m is None:
                self.logger.info('No valid data in response')
                return False
            else:
                port, capab = m.groups()
                self.server['udp_port'] = int(port)
                self.server['capabilities'] = capab
                self.logger.info('Server UDP port is %d and capabilities [%s]' % (self.server['udp_port'], self.server['capabilities']))
        else:
            self.logger.info('No data received')
        
        return True

    def get_server_params(self):
        return self.server

class Thingy:
    
    config = None
    logger = None
    server_info = None
    
    def __init__(self, argv=None):        
        # Get command line arguments from system if none passed
        if argv is None:
            argv = sys.argv[1:]
        
        parser = argparse.ArgumentParser()
        parser.add_argument('--server', '-s', action='store', required=True, dest='server_address', type=str)
        parser.add_argument('--port', '-p', action='store', required=True, dest='server_port', type=int)
        parser.add_argument('--verbose', '-v', action='store_true', required=False, dest='verbose')
        self.config = parser.parse_args(argv)
        
        # Initialize logging
        if self.config.verbose:
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.ERROR)
        self.logger = logging.getLogger('Thingy')

        # Resolve address if it's in domain form
        addrinfo = socket.getaddrinfo(self.config.server_address, self.config.server_port, socket.AF_INET, socket.SOCK_DGRAM)
        for ai in addrinfo:
            # Select one with UDP as protocol
            if ai[2] == 17:
                self.server_info = ai[4]

        if self.server_info:
            # Instantiate UDP and TCP clients
            self.logger.info('Initializing clients...')
            self.udp_client = UDPClient()
            self.tcp_client = TCPClient(*self.server_info)
                    
            self.logger.info('Server info %s' % (self.server_info,))
    
    def run(self):
        # Continue only if we have valid server information
        if self.server_info:
            self.logger.info('Running...')
            
            if not self.tcp_client.connection_request(10000, 'MI'):
                self.logger.info('Unable to connect to server')
                return 0
            
            # Get connection parameters from TCP client
            server_params = self.tcp_client.get_server_params()
    #        server_params = {}
    #        server_params['address'] = self.config.server_address
    #        server_params['udp_port'] = self.config.server_port
            
            # Initialize UDP server parameters and start listening
            self.logger.info('Starting UDP server...')
            self.udp_client.set_server_info(server_params['address'], server_params['udp_port'])
            self.udp_client.set_listen_port(10000)
            self.udp_client.init_socket()
            self.udp_client.send('HELO')
            while True:
                msg, source = self.udp_client.get_next_message()
                self.logger.info("Received '%s'" % msg)
                if msg:
                    if self.udp_client.eom_received:
                        self.logger.debug('EOM received')
                        break
                    a = answer(msg)
                    if a:
                        self.logger.info("Sending '%s'" % a)
                        self.udp_client.send(a)
                    else:
                        self.logger.info('No answer')
                        self.udp_client.send_nack()
                else:
                    self.logger.info('Empty message')
                    self.udp_client.send_nack()
            self.udp_client.close()
            return 0
    
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    Thingy().run()
