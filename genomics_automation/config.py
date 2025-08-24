"""
Configuration management using Pydantic models with environment overrides.
"""

import os
from pathlib import Path
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from enum import Enum


class DatabaseType(str, Enum):
    REFSEQ = "refseq"
    UCSC = "ucsc"
    ENSEMBL = "ensembl"


class ReferenceVersion(str, Enum):
    HG19 = "hg19"
    HG38 = "hg38"


class KBSpec(BaseModel):
    """Knowledge Base specification for TPS processing."""
    version: str = Field(..., description="Knowledge base version identifier")
    path: str = Field(..., description="Path to knowledge base files")
    description: Optional[str] = Field(None, description="Human-readable description")


class TransVarConfig(BaseModel):
    """TransVar-specific configuration."""
    database: DatabaseType = Field(
        default_factory=lambda: DatabaseType(os.getenv("GENOMICS_TRANSVAR_DATABASE", "refseq")),
        description="Annotation database"
    )
    ref_version: ReferenceVersion = Field(
        default_factory=lambda: ReferenceVersion(os.getenv("GENOMICS_TRANSVAR_REF_VERSION", "hg38")),
        description="Reference genome version"
    )
    use_ccds: bool = Field(
        default_factory=lambda: os.getenv("GENOMICS_TRANSVAR_USE_CCDS", "true").lower() == "true",
        description="Use CCDS annotations"
    )
    reference_file: Optional[str] = Field(
        default_factory=lambda: os.getenv("GENOMICS_TRANSVAR_REFERENCE_FILE"),
        description="Path to reference FASTA file"
    )
    executable: str = Field(
        default_factory=lambda: os.getenv("GENOMICS_TRANSVAR_EXECUTABLE", "transvar"),
        description="TransVar executable path or command"
    )
    custom_flags: List[str] = Field(default_factory=list, description="Additional TransVar flags")


class ProcessingConfig(BaseModel):
    """Processing and performance configuration."""
    max_workers: int = Field(
        default_factory=lambda: int(os.getenv("GENOMICS_MAX_WORKERS", "4")),
        ge=1, le=32, description="Maximum number of worker threads"
    )
    timeout_seconds: int = Field(
        default_factory=lambda: int(os.getenv("GENOMICS_TIMEOUT_SECONDS", "300")),
        ge=30, description="Timeout for individual operations"
    )
    retry_attempts: int = Field(
        default_factory=lambda: int(os.getenv("GENOMICS_RETRY_ATTEMPTS", "3")),
        ge=1, description="Number of retry attempts for failed operations"
    )
    chunk_size: int = Field(100, ge=1, description="Batch processing chunk size")


class PathConfig(BaseModel):
    """External tool and file paths."""
    junior_script_path: Optional[str] = Field(
        default_factory=lambda: os.getenv("GENOMICS_SARJ_SCRIPT"),
        description="Path to Nirvana Junior (SARJ) script"
    )
    tps_path: Optional[str] = Field(
        default_factory=lambda: os.getenv("GENOMICS_TPS_EXECUTABLE"),
        description="Path to TPS executable"
    )
    nirvana_path: Optional[str] = Field(
        default_factory=lambda: os.getenv("GENOMICS_NIRVANA_EXECUTABLE"),
        description="Path to Nirvana executable"
    )
    json_to_csv_script: Optional[str] = Field(
        default_factory=lambda: os.getenv("GENOMICS_JSON_TO_CSV_SCRIPT"),
        description="Path to JSON to CSV converter script"
    )
    knowledge_bases: List[KBSpec] = Field(
        default_factory=lambda: [
            KBSpec(
                version="cosmic_v97", 
                path=os.getenv("GENOMICS_KB_COSMIC", "cosmic"), 
                description="COSMIC Cancer Gene Census"
            ),
            KBSpec(
                version="clinvar_20230801", 
                path=os.getenv("GENOMICS_KB_CLINVAR", "clinvar"), 
                description="ClinVar Clinical Variants"
            )
        ], 
        description="Available knowledge bases"
    )
    temp_dir: Optional[str] = Field(
        default_factory=lambda: os.getenv("GENOMICS_TEMP_DIR", "temp"),
        description="Temporary directory for processing"
    )
    output_dir: Optional[str] = Field(
        default_factory=lambda: os.getenv("GENOMICS_OUTPUT_DIR", "output"),
        description="Output directory for results"
    )


class PipelineStages(BaseModel):
    """Toggle pipeline stages on/off."""
    run_transvar: bool = Field(True, description="Run TransVar annotation")
    run_sarj: bool = Field(True, description="Run SARJ generation")
    run_tps: bool = Field(True, description="Run TPS processing")
    run_json_conversion: bool = Field(True, description="Run JSON to CSV conversion")
    run_report_extraction: bool = Field(True, description="Generate final report")


class Config(BaseModel):
    """Main configuration class for the genomics automation pipeline."""
    
    # Component configurations
    transvar: TransVarConfig = Field(default_factory=TransVarConfig)
    processing: ProcessingConfig = Field(default_factory=ProcessingConfig)
    paths: PathConfig = Field(default_factory=PathConfig)
    stages: PipelineStages = Field(default_factory=PipelineStages)
    
    # Global settings
    debug_mode: bool = Field(False, description="Enable debug logging and intermediate file retention")
    preserve_intermediates: bool = Field(True, description="Keep intermediate files after processing")
    
    class Config:
        env_prefix = "GENOMICS_"
        case_sensitive = False
    
    @validator('paths')
    def validate_paths(cls, v):
        """Validate that required paths exist if provided."""
        path_fields = ['junior_script_path', 'tps_path', 'nirvana_path', 'json_to_csv_script']
        
        for field in path_fields:
            path_value = getattr(v, field)
            if path_value and not Path(path_value).exists():
                # Don't fail validation, just log a warning
                print(f"Warning: Path {field}={path_value} does not exist")
        
        return v
    
    @classmethod
    def from_env(cls) -> "Config":
        """Create configuration with environment variable overrides."""
        return cls()
    
    def get_transvar_flags(self) -> List[str]:
        """Get complete TransVar command flags."""
        flags = []
        
        # Database selection
        flags.extend([f"--{self.transvar.database.value}"])
        
        # Reference version
        flags.extend(["--refversion", self.transvar.ref_version.value])
        
        # CCDS
        if self.transvar.use_ccds:
            flags.append("--ccds")
        
        # Reference file
        if self.transvar.reference_file:
            flags.extend(["--reference", self.transvar.reference_file])
        
        # Custom flags
        flags.extend(self.transvar.custom_flags)
        
        return flags
    
    def get_temp_dir(self) -> Path:
        """Get temporary directory path, creating if necessary."""
        if self.paths.temp_dir:
            temp_path = Path(self.paths.temp_dir)
        else:
            temp_path = Path.cwd() / "temp"
        
        temp_path.mkdir(parents=True, exist_ok=True)
        return temp_path
    
    def get_output_dir(self) -> Path:
        """Get output directory path, creating if necessary."""
        if self.paths.output_dir:
            output_path = Path(self.paths.output_dir)
        else:
            output_path = Path.cwd() / "output"
        
        output_path.mkdir(parents=True, exist_ok=True)
        return output_path


# Default configuration instance
default_config = Config()
