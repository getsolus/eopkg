# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

import signal

class SignalWrapper:
    """
    Wraps a system signal, keeping track of the original signal
    handler, whether we have pending signal calls, and if we should
    hold pending signals to emit later.

    Attributes:
        signal (signal.Signals): The signal being wrapped.
        should_hold (bool): Whether we should hold pending signals.
        old_handler (signal.Handlers): The original signal handler.
        pending (bool): Whether there are signals pending.
    """

    def __init__(self, sig: signal.Signals, should_hold: bool):
        """
        Create a new SignalWrapper instance.

        Parameters:
            sig (signal.Signals): The signal to wrap.
            should_hold (bool): Whether we should hold pending signals.
        """
        self.signal = sig
        self.should_hold: bool = should_hold
        self.old_handler: signal.Handlers | None = signal.SIG_DFL
        self.pending: bool = False

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

    def disable_signal(self, sig: signal.Signals, should_hold: bool):
        """
        Disables a system signal by setting the handler to our own signal
        handler, storing the original handler in a dictionary.

        Parameters:
            sig (signal.Signals): The signal to disable.
            should_hold (bool): Whether the signal should be emitted when
                re-enabled if the signal was received while disabled.
        """
        if sig not in self.signals:
            wrapper = SignalWrapper(sig, should_hold)
            wrapper.old_handler = signal.signal(sig, self.__handler)
            self.signals[sig] = wrapper

    def enable_signal(self, sig: signal.Signals):
        """
        Enables a system signal, setting its handler to the original
        handler, or the default handler if we don't have one stored.

        If our handler was set to hold pending signal calls, and we
        received that signal while it was disabled, we will emit the
        signal as a part of re-enabling.

        Currently, only SIGINT (Keyboard Interrupt) is supported.

        Parameters:
            sig (signal.Signals): The signal to enable.
        """
        if not sig in self.signals:
            return

        wrapper = self.signals[sig]

        signal.signal(sig, wrapper.old_handler)
        del self.signals[sig]

        if not wrapper.should_hold:
            return

        if not wrapper.pending:
            return

        if sig is signal.SIGINT:
            raise KeyboardInterrupt

    def signal_disabled(self, sig: signal.Signals) -> bool:
        """
        Check if a signal has been disabled.

        Parameters:
            sig (signal.Signals): The signal to check.

        Returns:
            bool: Whether the signal has been disabled.
        """
        return sig in self.signals

    def __handler(self, sig: int | signal.Signals, frame):
        wrapper = self.signals[sig]

        if wrapper.should_hold:
            wrapper.pending = True
