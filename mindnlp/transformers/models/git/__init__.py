"""
This module defines the configuration class for the GIT model.
"""

# ... other code ...
from . import configuration_git, modeling_git,processing_git
from .modeling_git import *
from .configuration_git import *
from .processing_git import *

__all__ = []
__all__.extend(processing_git.__all__)
__all__.extend(modeling_git.__all__)
__all__.extend(configuration_git.__all__)
