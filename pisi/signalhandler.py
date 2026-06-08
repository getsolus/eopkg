# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

import signal
import threading
from threading import Event


class SignalWrapper:
    """
    Wraps a system signal, keeping track of the original signal
    handler to restore when the signal is re-enabled.

    Attributes:
        signal (signal.Signals): The signal being wrapped.
        old_handler (signal.Handlers): The original signal handler.
        ref_count (int): The number of times this signal has been
            disabled or caught.
    """

    def __init__(self, sig: signal.Signals):
        """
        Create a new SignalWrapper instance.

        Parameters:
            sig (signal.Signals): The signal to wrap.
        """
        self.signal = sig
        self.old_handler: signal.Handlers | None = signal.SIG_DFL
        self.ref_count = 0


class SignalHandler:
    """
    This class manages the disabling and enabling of system signals.
    When a signal is disabled, the original handler is stored by our
    handler so it can be restored when the signal becomes enabled.

    Attributes:
        signals (dict[signal.Signals, SignalWrapper]): Disabled signals
            and their handlers.
        done_event (Event): An event that is set when a caught signal
            is received.
    """

    def __init__(self):
        """Create a new SignalHandler instance."""
        self.signals: dict[signal.Signals, SignalWrapper] = {}
        self.done_event = Event()

    def handle_signal(self, signum, frame):
        """
        Internal signal handler that sets the done_event.
        """
        self.done_event.set()
        if threading.current_thread() is threading.main_thread():
            raise KeyboardInterrupt

    def clear_event(self):
        """
        Clears the done_event.
        """
        self.done_event.clear()

    def check_signals(self):
        """
        Checks if a signal was caught and raises KeyboardInterrupt if so.
        """
        if self.done_event.is_set():
            self.clear_event()
            raise KeyboardInterrupt

    def catch_signal(self, sig: signal.Signals):
        """
        Catches a system signal by setting the handler to our own signal
        handler, which sets the done_event.

        Parameters:
            sig (signal.Signals): The signal to catch.
        """
        if threading.current_thread() is not threading.main_thread():
            return

        if sig not in self.signals:
            wrapper = SignalWrapper(sig)
            wrapper.old_handler = signal.signal(sig, self.handle_signal)
            self.signals[sig] = wrapper
        self.signals[sig].ref_count += 1

    def disable_signal(self, sig: signal.Signals):
        """
        Disables a system signal by setting the handler to our own signal
        handler, storing the original handler in a dictionary.

        Parameters:
            sig (signal.Signals): The signal to disable.
        """
        if threading.current_thread() is not threading.main_thread():
            return

        if sig not in self.signals:
            wrapper = SignalWrapper(sig)
            wrapper.old_handler = signal.signal(sig, signal.SIG_IGN)
            self.signals[sig] = wrapper
        self.signals[sig].ref_count += 1

    def enable_signal(self, sig: signal.Signals):
        """
        Enables a system signal, setting its handler to the original
        handler, or the default handler if we don't have one stored.

        Parameters:
            sig (signal.Signals): The signal to enable.
        """
        if threading.current_thread() is not threading.main_thread():
            return

        if sig not in self.signals:
            return

        wrapper = self.signals[sig]
        wrapper.ref_count -= 1

        if wrapper.ref_count <= 0:
            signal.signal(sig, wrapper.old_handler)
            del self.signals[sig]
