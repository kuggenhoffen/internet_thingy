#TODO: Program can take additional arguments such as list of extra features to enable
#TODO: Program uses TCP to connect to server, exchanges port numbers, possible extra features and possible encryption keys with server
#TODO: Program uses UDP to send a "Hello" message to a server
#TODO: Server sends a question
#TODO: Program uses a module provided by assistants to find out the correct answer
#TODO: Program replies with correct answer
#TODO: Server sends a new message predefined number of times
#TODO: After all questions are answered, close the program

import sys
import argparse
import socket
import logging
import re

class UDPClient:
    server = {
              'address': None,
              'udp_port': None
              }
    listen_port = None
    
    def __init__(self, listen_port = 10000):
        self.listen_port = listen_port
    
    def 
    
    def start(self):
        
    
    def set_connection_params(self, address, port):
        self.server['address'] = address
        self.server['udp_port'] = port

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
            m = re.search('\w+ (\d+)[ ]?(\w+)', response)
            if m is None:
                self.logger.info('No valid data in response')
                return False
            else:
                (port, capab) = m.groups()
                self.server['udp_port'] = port
                self.server['capabilities'] = capab
                self.logger.info('Server UDP port is %d and capabilities [%s]' % (port, capab))
        else:
            self.logger.info('No data received')
        
        return True

    def get_server_params(self):
        return self.server

class Thingy:
    
    config = None
    logger = None
    
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

        # Instantiate UDP and TCP clients
        self.logger.info('Initializing clients...')
        self.udp_client = UDPClient()
        self.tcp_client = TCPClient(self.config.server_address, self.config.server_port)        
                
        print 'Let''s do this with %s:%s' % (self.config.server_address, self.config.server_port)
    
    def run(self):
        self.logger.info('Running...')
        self.tcp_client.connection_request(10000)
        return 0;
    
if __name__ == "__main__":
    sys.exit(Thingy().run())