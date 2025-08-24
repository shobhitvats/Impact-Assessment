"""
Genomics Automation Pipeline

A comprehensive toolkit for automating genomics impact assessment workflows,
from VCF input to final report generation.
"""

__version__ = "1.0.0"
__author__ = "Genomics Automation Team"

from .config import Config
from .pipeline import run_full_pipeline

__all__ = ["Config", "run_full_pipeline"]
