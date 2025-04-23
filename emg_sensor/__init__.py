"""
EMG sensor package for QuickFlexEMG application.
Provides interfaces for connecting to and reading from EMG sensor devices.
"""

from .data_reader import iFocus
from .emg_sock import sock
from .iFocusParser import Parser

__all__ = ['iFocus', 'sock', 'Parser']