# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

import signal


class SignalWrapper:
    """
    Wraps a system signal, keeping track of the original signal
    handler to restore when the signal is re-enabled.

    Attributes:
        signal (signal.Signals): The signal being wrapped.
        old_handler (signal.Handlers): The original signal handler.
    """

    def __init__(self, sig: signal.Signals):
        """
        Create a new SignalWrapper instance.

        Parameters:
            sig (signal.Signals): The signal to wrap.
        """
        self.signal = sig
        self.old_handler: signal.Handlers | None = signal.SIG_DFL


class SignalHandler:
    """
    This class manages the disabling and enabling of system signals.
    When a signal is disabled, the original handler is stored by our
    handler so it can be restored when the signal becomes enabled.

    Attributes:
        signals (dict[signal.Signals, SignalWrapper]): Disabled signals
            and their handlers.
    """

    def __init__(self):
        """Create a new SignalHandler instance."""
        self.signals: dict[signal.Signals, SignalWrapper] = {}

    def disable_signal(self, sig: signal.Signals):
        """
        Disables a system signal by setting the handler to our own signal
        handler, storing the original handler in a dictionary.

        Parameters:
            sig (signal.Signals): The signal to disable.
        """
        if sig not in self.signals:
            wrapper = SignalWrapper(sig)
            wrapper.old_handler = signal.signal(sig, signal.SIG_IGN)
            self.signals[sig] = wrapper

    def enable_signal(self, sig: signal.Signals):
        """
        Enables a system signal, setting its handler to the original
        handler, or the default handler if we don't have one stored.

        Parameters:
            sig (signal.Signals): The signal to enable.
        """
        if not sig in self.signals:
            return

        wrapper = self.signals[sig]

        signal.signal(sig, wrapper.old_handler)
        del self.signals[sig]
