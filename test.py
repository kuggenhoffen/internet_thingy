import unittest
import socket
import logging
import struct
import errno
from Queue import Queue
from thingy import UDPClient
from thingy import UDPReceiver

class UDPClientTestCase(unittest.TestCase):
    def setUp(self):
        self.udpclient = UDPClient()

    def tearDown(self):
        self.udpclient.close()
        self.udpclient = None
    
    def test_port_setting(self):
        self.udpclient.set_listen_port()
        self.assertEqual(10000, self.udpclient.listen_port)
        self.udpclient.set_listen_port(1234)
        self.assertEqual(1234, self.udpclient.listen_port)
        
    def test_socket_init_unbound_port(self):
        self.udpclient.set_listen_port(10000)
        self.assertTrue(self.udpclient.init_socket())
    
    def test_socket_init_bound_port(self):
        # Bind socket to port and use same port for client
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('localhost', 10000))
        
        # Try to connect the udp client to the already bound port
        self.udpclient.set_listen_port(10000)
        self.assertFalse(self.udpclient.init_socket())
    
    def test_socket_double_init(self):
        self.udpclient.set_listen_port(10000)
        self.assertTrue(self.udpclient.init_socket())
        self.assertFalse(self.udpclient.init_socket())
        
    def test_socket_send_raw(self):
        msg = 'TEST'
        localhost = '127.0.0.1'
        listenport = 10000
        
        # Create socket for receiving from client
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((localhost, 10001))
        
        
        # Init client socket and send message
        self.udpclient.set_listen_port(listenport)
        self.udpclient.init_socket()
        self.udpclient.send_raw((localhost, 10001), msg)
        
        (data, addr) = sock.recvfrom(64)
        self.assertEqual(addr, (localhost, listenport))
        self.assertEqual(data, msg)
    
    def test_socket_send_protocol(self):
        msg = 'TEST'
        localhost = '127.0.0.1'
        listenport = 10000
        
        # Create socket for receiving from client
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((localhost, 10001))
        
        
        # Init client socket and send message
        self.udpclient.set_listen_port(listenport)
        self.udpclient.init_socket()
        self.assertTrue(self.udpclient.send_raw((localhost, 10001), msg))
        
        (data, addr) = sock.recvfrom(64)
        self.assertEqual(addr, (localhost, listenport))
        self.assertEqual(data, msg)
        
    def test_protocol_packing_short(self):
        eom = False
        ack = True
        data = 'A'
        packed = struct.pack('!??HH64s', eom, ack, len(data), 0, data.ljust(64, chr(0)))
        packets = self.udpclient.packetise(False, True, 'A')
        self.assertListEqual(packets, [packed])
    
    def test_protocol_packing_many(self):
        eom = False
        ack = True
        data = 'A'*70
        packed = []
        packed.append(struct.pack('!??HH64s', eom, ack, 64, 6, data[:64]))
        packed.append(struct.pack('!??HH64s', eom, ack, 6, 0, data[64:].ljust(64, chr(0))))
        packets = self.udpclient.packetise(eom, ack, data)
        self.assertListEqual(packed, packets)
    
    def test_protocol_unpack_short(self):
        eom = False
        ack = True
        data = 'Abc'
        packed = struct.pack('!??HH64s', eom, ack, len(data), 0, data.ljust(64, chr(0)))
        unpacked = self.udpclient.unpack(packed)
        self.assertTupleEqual(unpacked, (eom, ack, len(data), 0, data))
        
    def test_protocol_pack_unpack(self):
        eom = False
        ack = True
        data = 'AbcD'*30
        datalen = len(data)
        udata = ''
        packets = self.udpclient.packetise(eom, ack, data)
        self.assertEqual(len(packets), 2)
        ue, ua, ul, ur, uc  = self.udpclient.unpack(packets[0])
        self.assertEqual(ue, eom)
        self.assertEqual(ua, ack)
        self.assertEqual(ul, 64)
        self.assertEqual(ur, datalen-64)
        self.assertEqual(uc, data[:64])
        ue, ua, ul, ur, uc  = self.udpclient.unpack(packets[1])
        self.assertEqual(ue, eom)
        self.assertEqual(ua, ack)
        self.assertEqual(ul, datalen-64)
        self.assertEqual(ur, 0)
        self.assertEqual(uc, data[64:])
    
    def test_socket_send_before_init(self):
        self.assertFalse(self.udpclient.send_raw(('127.0.0.1', 10001), 'TEST'))
    
    def test_client_receive_queue_short(self):
        localhost = '127.0.0.1'
        listenport = 10000
        testerport = 10100
        
        # Create socket for sending to client
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)   
        sock.bind((localhost, testerport))     
        
        # Init client socket and start listening thread
        self.udpclient.set_listen_port(listenport)
        self.udpclient.set_server_info(localhost, testerport)
        self.udpclient.init_socket()
        
        # Generate message in correct format for sending to client
        eom = False
        ack = True
        data = 'TEST MESSAGE'
        packed = struct.pack('!??HH64s', eom, ack, len(data), 0, data.ljust(64, chr(0)))
        sock.sendto(packed, (localhost, listenport))
        msg, addr = self.udpclient.get_next_message()
        self.assertEqual(msg, data)
        
    def test_client_receive_queue_multi(self):
        localhost = '127.0.0.1'
        listenport = 10000
        testerport = 10100
        
        # Create socket for sending to client
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)        
        sock.bind((localhost, testerport))
        
        # Init client socket and start listening thread
        self.udpclient.set_listen_port(listenport)
        self.udpclient.set_server_info(localhost, testerport)
        self.udpclient.init_socket()
        
        # Generate message in correct format for sending to client
        data = 'TEST MESSAGE'*7
        packets = self.udpclient.packetise(False, True, data)
        for p in packets:
            sock.sendto(p, (localhost, listenport))
        msg, addr = self.udpclient.get_next_message()
        self.assertEqual(msg, data)

    def test_client_integrity_check_header_length(self):
        localhost = '127.0.0.1'
        clientport = 10000
        testerport = 10100
        
        # Create socket for sending and receiving
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((localhost, testerport))
        
        # Init client socket and start listening thread
        self.udpclient.set_listen_port(clientport)
        self.udpclient.set_server_info(localhost, testerport)
        self.udpclient.init_socket()
        
        # Generate message in correct format for sending to client
        data = 'TEST MESSAGE'
        # Pack a packet with invalid content length field, 9 instead of 12
        packed = struct.pack('!??HH64s', False, True, len(data)-3, 0, data.ljust(64, chr(0)))
        # Send packet
        sock.sendto(packed, (localhost, clientport))
        
        # Try reading message from client
        self.udpclient.get_next_message()
        
        sock.settimeout(2)
        try:
            bytes, addr = sock.recvfrom(128)
            eom, ack, l, rem, msg = self.udpclient.unpack(bytes)
            self.assertEqual(msg, 'Send again.')
            self.assertFalse(ack)
        except socket.error as serr:
            self.fail('Nack receive timedout')
        sock.close()
        
    def test_client_send(self):
        localhost = '127.0.0.1'
        clientport = 10000
        testerport = 10100
        
        # Create socket for sending and receiving
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((localhost, testerport))
        
        # Init client
        self.udpclient.set_server_info(localhost, testerport)
        self.udpclient.set_listen_port(clientport)
        self.udpclient.init_socket()
        
        # Send test message
        self.udpclient.send("TESTMESSAGE", False, True)
        
        # Read test message with socket
        d = sock.recv(128)
    
        self.assertEqual(d, self.udpclient.packetise(False, True, "TESTMESSAGE")[0])

class UDPReceiverTestCase(unittest.TestCase):
    def setUp(self):
        # Create test socket
        self.addr = ('127.0.0.1', 10000)
        self.testsocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.testsocket.bind(self.addr)
        
        # Create test queue
        self.queue = Queue(0)
        self.udpr = UDPReceiver(self.testsocket, self.queue)

    def tearDown(self):
        # Stop receiver
        self.udpr.stop()
        self.udpr.join()
        self.udpr = None
        
        # Close socket
        self.testsocket.close()
        self.testsocket = None
        
        self.queue = None
       
    def test_udp_receiver_thread(self):
        # Start receiving thread
        self.udpr.start()
        self.assertTrue(self.udpr.is_alive())
    
    def test_udp_receiver_queue(self):
        testmsg = "TEST MESSAGE"
        
        # Start receiving thread
        self.udpr.start()
        
        # Send message to socket
        self.testsocket.sendto(testmsg, self.addr)
        
        self.assertTupleEqual(self.queue.get(), (testmsg, self.addr))

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    suites = []
    suites.append(unittest.TestLoader().loadTestsFromTestCase(UDPReceiverTestCase))
    suites.append(unittest.TestLoader().loadTestsFromTestCase(UDPClientTestCase))
    for s in suites:
        unittest.TextTestRunner(verbosity=2).run(s)