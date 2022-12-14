import logging
import time
import tkinter as tk
from tkinter import scrolledtext as tkst
from tkinter import ttk
import signal
import queue
import threading
from datetime import datetime
logger = logging.getLogger(__name__)


class TextHandler(logging.Handler):

    def __init__(self, text):
        logging.Handler.__init__(self)

        # Store a reference to the Text it will log to.
        self.text = text

    def emit(self, record):
        msg = self.format(record)

        def append():
            self.text.configure(state='normal')
            self.text.insert(tk.END, msg + '\n')
            self.text.configure(state='disabled')

            # Auto scroll to the bottom
            self.text.yview(tk.END)

        # this is necessary because we can't modify the Text from other threads
        self.text.after(0, append)


class QueueHandler(logging.Handler):
    """
    Class to send logging records to a queue
    It can be used from different threads.
    """
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        # The handler only puts the message in a queue
        self.log_queue.put(record)


class ConsoleUi:
    """Poll messages from a logging queue, and display them in a scrolled text widget"""

    def __init__(self, frame):
        self.frame = frame

        self.scrolled_text = tkst.ScrolledText(frame, state='disabled', height=12)
        self.scrolled_text.grid(row=0, column=0, sticky='nesw')
        self.scrolled_text.configure(font='TkFixedFont')
        self.scrolled_text.tag_config('INFO', foreground='black')
        self.scrolled_text.tag_config('DEBUG', foreground='grey')
        self.scrolled_text.tag_config('WARNING', foreground='orange')
        self.scrolled_text.tag_config('ERROR', foreground='red')
        self.scrolled_text.tag_config('CRITICAL', foreground='red', underline=True)

        self.log_queue = queue.Queue()
        self.queue_handler = QueueHandler(self.log_queue)
        formatter = logging.Formatter('%(asctime)s: %(message)s')
        self.queue_handler.setFormatter(formatter)
        logger.addHandler(self.queue_handler)

        # start polling messages from the queue
        self.frame.after(100, self.poll_log_queue)

    def display(self, record):
        msg = self.queue_handler.format(record)
        self.scrolled_text.configure(state='normal')
        self.scrolled_text.insert(tk.END, msg + '\n', record.levelname)
        self.scrolled_text.configure(state='disabled')
        self.scrolled_text.yview(tk.END)

    def poll_log_queue(self):
        # Check every 100ms if there's a new message in the queue to display
        while True:
            try:
                record = self.log_queue.get(block=False)
            except queue.Empty:
                break
            else:
                self.display(record)
        self.frame.after(100, self.poll_log_queue)


class Clock(threading.Thread):
    """Class to display the time every seconds
    Every five seconds, the time is displayed using the logging.ERROR level
    to show that different colors are associated to the log levels.
    """

    def __init__(self):
        super().__init__()
        self._stop_event = threading.Event()

    def run(self):
        logger.debug('Clock started')
        previous = -1

        while not self._stop_event.is_set():
            now = datetime.now()
            if previous != now.second:
                previous = now.second
                if now.second % 5 == 0:
                    level = logging.ERROR
                else:
                    level = logging.INFO
                logger.log(level, now)
            time.sleep(0.2)

    def stop(self):
        self._stop_event.set()


class App:
    def __init__(self, root):
        self.root = root
        root.title('Logging handler')
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)

        # Create the panes and frames
        vertical_pane = ttk.PanedWindow(self.root, orient=tk.VERTICAL)
        vertical_pane.grid(row=0, column=0, sticky="nsew")

        horizontal_pane = ttk.PanedWindow(vertical_pane, orient=tk.HORIZONTAL)
        vertical_pane.add(horizontal_pane)

        # horizontal pane has two frames: form and console (both are of Labelframe type)
        form_frame = ttk.Labelframe(horizontal_pane, text="MyForm")
        form_frame.columnconfigure(1, weight=1)
        horizontal_pane.add(form_frame, weight=1)

        console_frame = ttk.Labelframe(horizontal_pane, text="Console")
        console_frame.columnconfigure(0, weight=1)
        console_frame.rowconfigure(0, weight=1)
        horizontal_pane.add(console_frame, weight=1)

        # vertical pane has third frame
        third_frame = ttk.Labelframe(vertical_pane, text="Third Frame")
        vertical_pane.add(third_frame, weight=1)

        # Initialize all frames
        self.form = FormUi(form_frame)
        self.console = ConsoleUi(console_frame)
        self.third = ThirdUi(third_frame)

        self.clock = Clock()
        self.clock.start()
        self.root.protocol('WM_DELETE_WINDOW', self.quit)
        self.root.bind('<Control-q>', self.quit)

        # signal.signal SIGINT -> (ctrl + z)?
        signal.signal(signal.SIGINT, self.quit)

    def quit(self, *args):
        self.clock.stop()
        self.root.destroy()


class FormUi:

    def __init__(self, frame):
        self.frame = frame
        # Create a combobbox to select the logging level
        values = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        self.level = tk.StringVar()
        ttk.Label(self.frame, text='Level:').grid(column=0, row=0, sticky='w')
        self.combobox = ttk.Combobox(
            self.frame,
            textvariable=self.level,
            width=25,
            state='readonly',
            values=values
        )
        self.combobox.current(0)
        self.combobox.grid(column=1, row=0, sticky='we')
        # Create a text field to enter a message
        self.message = tk.StringVar()
        ttk.Label(self.frame, text='Message:').grid(column=0, row=1, sticky='w')
        ttk.Entry(self.frame, textvariable=self.message, width=25).grid(column=1, row=1, sticky='we')
        # Add a button to log the message
        self.button = ttk.Button(self.frame, text='Submit', command=self.submit_message)
        self.button.grid(column=1, row=2, sticky='w')

    def submit_message(self):
        # Get the logging level numeric value
        lvl = getattr(logging, self.level.get())
        logger.log(lvl, self.message.get())


class ThirdUi:

    def __init__(self, frame):
        self.frame = frame
        ttk.Label(self.frame, text='This is just an example of a third frame').grid(column=0, row=1, sticky='w')
        ttk.Label(self.frame, text='With another line here!').grid(column=0, row=4, sticky='w')


def main():
    logging.basicConfig(level=logging.DEBUG)
    root = tk.Tk()
    app = App(root)
    app.root.mainloop()


if __name__ == '__main__':
    main()
