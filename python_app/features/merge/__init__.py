"""Merge feature — public facade.

Other features should import from this module rather than reaching
into internal submodules.
"""
from .worker import MergeWorker

__all__ = ["MergeWorker"]
