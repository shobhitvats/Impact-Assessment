"""
SARJ (Nirvana Junior) runner module for generating SARJ files from VCF input.
"""

import subprocess
from pathlib import Path
from typing import Dict, Optional, Any
from dataclasses import dataclass

from .config import Config
from .utils import validate_file_exists, retry_on_failure


@dataclass
class SARJResult:
    """Result from SARJ generation process."""
    success: bool
    input_vcf: Path
    output_sarj: Optional[Path] = None
    error_message: Optional[str] = None
    command_used: Optional[str] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    execution_time: Optional[float] = None


class SARJRunner:
    """Handles execution of Nirvana Junior (SARJ) script."""
    
    def __init__(self, config: Config):
        self.config = config
        self.junior_script_path = config.paths.junior_script_path
    
    def validate_setup(self) -> tuple[bool, str]:
        """
        Validate that SARJ runner is properly configured.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.junior_script_path:
            return False, "Junior script path not configured in settings"
        
        script_path = Path(self.junior_script_path)
        if not validate_file_exists(script_path, "Junior script"):
            return False, f"Junior script not found at {self.junior_script_path}"
        
        # Check if script is executable
        if not script_path.is_file():
            return False, f"Junior script at {self.junior_script_path} is not a file"
        
        return True, ""
    
    def build_sarj_command(self, input_vcf: Path, output_sarj: Path) -> list[str]:
        """
        Build SARJ generation command.
        
        Args:
            input_vcf: Path to input VCF file
            output_sarj: Path for output SARJ file
        
        Returns:
            Command as list of strings
        """
        # Use positional arguments for mock script compatibility
        cmd = [
            str(self.junior_script_path),
            str(input_vcf),
            str(output_sarj)
        ]
        
        return cmd
    
    @retry_on_failure(max_attempts=3, delay=2.0)
    def run_sarj(
        self,
        input_vcf: Path,
        output_dir: Optional[Path] = None,
        output_filename: Optional[str] = None
    ) -> SARJResult:
        """
        Run SARJ generation on a VCF file.
        
        Args:
            input_vcf: Path to input VCF file
            output_dir: Optional output directory (defaults to config output dir)
            output_filename: Optional output filename (defaults to input name + .sarj)
        
        Returns:
            SARJResult with execution details
        """
        # Validate setup
        is_valid, error_msg = self.validate_setup()
        if not is_valid:
            return SARJResult(
                success=False,
                input_vcf=input_vcf,
                error_message=error_msg
            )
        
        # Validate input file
        if not validate_file_exists(input_vcf, "Input VCF"):
            return SARJResult(
                success=False,
                input_vcf=input_vcf,
                error_message=f"Input VCF file not found: {input_vcf}"
            )
        
        # Determine output path
        if not output_dir:
            output_dir = self.config.get_output_dir()
        
        if not output_filename:
            output_filename = input_vcf.stem + ".json"
        
        output_sarj = output_dir / output_filename
        
        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Build command
        cmd = self.build_sarj_command(input_vcf, output_sarj)
        
        try:
            import time
            start_time = time.time()
            
            # Run SARJ command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=self.config.processing.timeout_seconds * 2  # SARJ might take longer
            )
            
            execution_time = time.time() - start_time
            
            # Verify output file was created
            if not output_sarj.exists():
                return SARJResult(
                    success=False,
                    input_vcf=input_vcf,
                    error_message="SARJ file was not created despite successful command execution",
                    command_used=" ".join(cmd),
                    stdout=result.stdout,
                    stderr=result.stderr,
                    execution_time=execution_time
                )
            
            return SARJResult(
                success=True,
                input_vcf=input_vcf,
                output_sarj=output_sarj,
                command_used=" ".join(cmd),
                stdout=result.stdout,
                stderr=result.stderr,
                execution_time=execution_time
            )
        
        except subprocess.TimeoutExpired:
            return SARJResult(
                success=False,
                input_vcf=input_vcf,
                error_message=f"SARJ generation timed out after {self.config.processing.timeout_seconds * 2} seconds",
                command_used=" ".join(cmd)
            )
        
        except subprocess.CalledProcessError as e:
            return SARJResult(
                success=False,
                input_vcf=input_vcf,
                error_message=f"SARJ generation failed with exit code {e.returncode}",
                command_used=" ".join(cmd),
                stdout=e.stdout,
                stderr=e.stderr
            )
        
        except Exception as e:
            return SARJResult(
                success=False,
                input_vcf=input_vcf,
                error_message=f"Unexpected error during SARJ generation: {str(e)}",
                command_used=" ".join(cmd)
            )
    
    def get_sarj_info(self, sarj_file: Path) -> Dict[str, Any]:
        """
        Get information about a SARJ file.
        
        Args:
            sarj_file: Path to SARJ file
        
        Returns:
            Dictionary with SARJ file information
        """
        if not sarj_file.exists():
            return {
                'exists': False,
                'error': 'SARJ file not found'
            }
        
        try:
            # Get basic file stats
            stats = sarj_file.stat()
            
            # Try to read first few lines to validate format
            with open(sarj_file, 'r') as f:
                first_lines = [f.readline().strip() for _ in range(5)]
            
            return {
                'exists': True,
                'file_path': str(sarj_file),
                'file_size': stats.st_size,
                'file_size_human': _format_file_size(stats.st_size),
                'modified_time': stats.st_mtime,
                'first_lines': first_lines,
                'is_valid': len(first_lines) > 0 and any(line for line in first_lines)
            }
        
        except Exception as e:
            return {
                'exists': True,
                'error': f'Error reading SARJ file: {str(e)}'
            }


def _format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB"]
    import math
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    
    return f"{s} {size_names[i]}"


# Example configuration for different Junior script interfaces
JUNIOR_SCRIPT_EXAMPLES = {
    "basic": {
        "description": "Basic Junior script with input/output parameters",
        "command_template": "{script_path} --input {input_vcf} --output {output_sarj}",
        "required_params": ["script_path", "input_vcf", "output_sarj"]
    },
    "nirvana_style": {
        "description": "Nirvana-style Junior with additional configuration",
        "command_template": "{script_path} -i {input_vcf} -o {output_sarj} --cache {cache_dir}",
        "required_params": ["script_path", "input_vcf", "output_sarj", "cache_dir"]
    },
    "custom": {
        "description": "Custom script with user-defined parameters",
        "command_template": "Defined by user configuration",
        "required_params": ["script_path"]
    }
}
