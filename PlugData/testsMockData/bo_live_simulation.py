import sys
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer
from pythonosc import udp_client

class OSCBridge(QThread):
    # We'll use a simple shared state instead of signals for every packet
    # to avoid overwhelming the message queue.
    def __init__(self, state_dict):
        super().__init__()
        self.state = state_dict
        self.forwarder = udp_client.SimpleUDPClient("127.0.0.1", 12001)

    def run(self):
        dispatcher = Dispatcher()
        dispatcher.map("/tipA", self.handle_tip_a)
        dispatcher.map("/tipB", self.handle_tip_b)
        server = BlockingOSCUDPServer(("127.0.0.1", 12000), dispatcher)
        server.serve_forever()

    def handle_tip_a(self, address, *args):
        self.forwarder.send_message(address, args)
        # Update shared state
        self.state['yaw'] = args[0]
        self.state['pitch'] = args[1]
        self.state['acc'] = args[2]

    def handle_tip_b(self, address, *args):
        self.forwarder.send_message(address, args)

class LiveBoSimulator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NIME Bô - High Performance Sync")
        self.staff_length = 4.0

        # Shared thread-safe-ish state
        self.data_state = {'yaw': 0.0, 'pitch': 0.0, 'acc': 0.0}

        # UI Setup
        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        self.layout = QVBoxLayout(self.main_widget)

        # Plot Setup - Turning off interactive mode for speed
        plt.style.use('dark_background')
        self.figure = plt.figure(figsize=(6, 6))
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111, projection='3d')
        self.layout.addWidget(self.canvas)

        # Background OSC Thread
        self.osc_thread = OSCBridge(self.data_state)
        self.osc_thread.start()

        # UI REFRESH TIMER (The Secret Sauce)
        # 30ms = ~33 FPS. This prevents the "Not Responding" freeze.
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(30)

    def get_rotation_matrix(self, p, y):
        p, y = np.radians([p, y])
        Ry = np.array([[np.cos(p), 0, np.sin(p)], [0, 1, 0], [-np.sin(p), 0, np.cos(p)]])
        Rz = np.array([[np.cos(y), -np.sin(y), 0], [np.sin(y), np.cos(y), 0], [0, 0, 1]])
        return Rz @ Ry

    def update_plot(self):
        # 1. Grab latest data from the state dictionary
        p = self.data_state['pitch']
        y = self.data_state['yaw']

        # 2. Clear and Redraw
        self.ax.clear()

        rot_matrix = self.get_rotation_matrix(p, y)
        end_a = rot_matrix @ np.array([self.staff_length / 2, 0, 0])
        end_b = rot_matrix @ np.array([-self.staff_length / 2, 0, 0])

        # Draw Staff
        self.ax.plot([end_b[0], end_a[0]], [end_b[1], end_a[1]], [end_b[2], end_a[2]],
                     color='white', lw=4)
        self.ax.scatter(end_a[0], end_a[1], end_a[2], color='red', s=100)
        self.ax.scatter(end_b[0], end_b[1], end_b[2], color='cyan', s=100)

        # Static Axis limits (prevents jumping)
        limit = 3
        self.ax.set_xlim([-limit, limit])
        self.ax.set_ylim([-limit, limit])
        self.ax.set_zlim([-limit, limit])
        # self.ax.set_axis_off() # Massive speed boost by not drawing grids/labels

        self.canvas.draw_idle() # Optimized draw call

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LiveBoSimulator()
    window.show()
    sys.exit(app.exec_())