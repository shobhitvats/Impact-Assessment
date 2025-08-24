"""
JSON to CSV converter module - wrapper around existing converter script.
"""

import subprocess
import json
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

from .config import Config
from .utils import validate_file_exists, read_csv_with_encoding_detection, write_csv_safely


@dataclass
class ConversionResult:
    """Result from JSON to CSV conversion."""
    success: bool
    input_json: Path
    output_csv: Optional[Path] = None
    error_message: Optional[str] = None
    command_used: Optional[str] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    record_count: Optional[int] = None
    execution_time: Optional[float] = None


class JSONToCSVConverter:
    """Handles conversion of TPS JSON output to CSV format."""
    
    def __init__(self, config: Config):
        self.config = config
        self.converter_script_path = config.paths.json_to_csv_script
    
    def validate_setup(self) -> tuple[bool, str]:
        """
        Validate that the converter is properly configured.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.converter_script_path:
            return False, "JSON to CSV converter script path not configured"
        
        script_path = Path(self.converter_script_path)
        if not validate_file_exists(script_path, "JSON to CSV converter script"):
            return False, f"Converter script not found at {self.converter_script_path}"
        
        return True, ""
    
    def build_conversion_command(self, input_json: Path, output_csv: Path) -> List[str]:
        """
        Build conversion command.
        
        Args:
            input_json: Path to input JSON file
            output_csv: Path for output CSV file
        
        Returns:
            Command as list of strings
        """
        # Use positional arguments (matching mock script interface)
        cmd = [
            "python",  # Assuming it's a Python script
            str(self.converter_script_path),
            str(input_json),    # positional arg 1: input JSON file
            str(output_csv)     # positional arg 2: output CSV file
        ]
        
        return cmd
    
    def convert_json_to_csv(
        self,
        input_json: Path,
        output_dir: Optional[Path] = None,
        output_filename: Optional[str] = None
    ) -> ConversionResult:
        """
        Convert a single JSON file to CSV format.
        
        Args:
            input_json: Path to input JSON file
            output_dir: Optional output directory (defaults to config output dir)
            output_filename: Optional output filename (defaults to input name + .csv)
        
        Returns:
            ConversionResult with execution details
        """
        # Validate setup
        is_valid, error_msg = self.validate_setup()
        if not is_valid:
            return ConversionResult(
                success=False,
                input_json=input_json,
                error_message=error_msg
            )
        
        # Validate input file
        if not validate_file_exists(input_json, "Input JSON"):
            return ConversionResult(
                success=False,
                input_json=input_json,
                error_message=f"Input JSON file not found: {input_json}"
            )
        
        # Validate JSON format
        try:
            with open(input_json, 'r') as f:
                json_data = json.load(f)
                record_count = len(json_data) if isinstance(json_data, list) else 1
        except json.JSONDecodeError as e:
            return ConversionResult(
                success=False,
                input_json=input_json,
                error_message=f"Invalid JSON format: {str(e)}"
            )
        except Exception as e:
            return ConversionResult(
                success=False,
                input_json=input_json,
                error_message=f"Error reading JSON file: {str(e)}"
            )
        
        # Determine output path
        if not output_dir:
            output_dir = self.config.get_output_dir() / "csv_output"
        
        if not output_filename:
            output_filename = input_json.stem + ".csv"
        
        output_csv = output_dir / output_filename
        
        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Build command
        cmd = self.build_conversion_command(input_json, output_csv)
        
        try:
            import time
            start_time = time.time()
            
            # Run conversion command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=self.config.processing.timeout_seconds
            )
            
            execution_time = time.time() - start_time
            
            # Verify output file was created
            if not output_csv.exists():
                return ConversionResult(
                    success=False,
                    input_json=input_json,
                    error_message="CSV output file was not created despite successful command execution",
                    command_used=" ".join(cmd),
                    stdout=result.stdout,
                    stderr=result.stderr,
                    execution_time=execution_time
                )
            
            return ConversionResult(
                success=True,
                input_json=input_json,
                output_csv=output_csv,
                command_used=" ".join(cmd),
                stdout=result.stdout,
                stderr=result.stderr,
                record_count=record_count,
                execution_time=execution_time
            )
        
        except subprocess.TimeoutExpired:
            return ConversionResult(
                success=False,
                input_json=input_json,
                error_message=f"JSON to CSV conversion timed out after {self.config.processing.timeout_seconds} seconds",
                command_used=" ".join(cmd)
            )
        
        except subprocess.CalledProcessError as e:
            return ConversionResult(
                success=False,
                input_json=input_json,
                error_message=f"JSON to CSV conversion failed with exit code {e.returncode}",
                command_used=" ".join(cmd),
                stdout=e.stdout,
                stderr=e.stderr
            )
        
        except Exception as e:
            return ConversionResult(
                success=False,
                input_json=input_json,
                error_message=f"Unexpected error during JSON to CSV conversion: {str(e)}",
                command_used=" ".join(cmd)
            )
    
    def convert_batch_json_to_csv(
        self,
        json_files: List[Path],
        output_dir: Optional[Path] = None
    ) -> List[ConversionResult]:
        """
        Convert multiple JSON files to CSV format.
        
        Args:
            json_files: List of JSON file paths
            output_dir: Optional output directory
        
        Returns:
            List of ConversionResult objects
        """
        results = []
        
        for json_file in json_files:
            result = self.convert_json_to_csv(json_file, output_dir)
            results.append(result)
        
        return results
    
    def get_conversion_summary(self, results: List[ConversionResult]) -> Dict[str, Any]:
        """
        Generate summary statistics for batch conversion.
        
        Args:
            results: List of conversion results
        
        Returns:
            Dictionary with summary statistics
        """
        successful_results = [r for r in results if r.success]
        failed_results = [r for r in results if not r.success]
        
        total_records = sum(r.record_count for r in successful_results if r.record_count)
        total_execution_time = sum(r.execution_time for r in results if r.execution_time)
        
        successful_files = []
        failed_files = []
        
        for result in successful_results:
            file_info = {
                'input_file': str(result.input_json),
                'output_file': str(result.output_csv),
                'record_count': result.record_count,
                'execution_time': result.execution_time
            }
            if result.output_csv and result.output_csv.exists():
                file_info['output_size'] = result.output_csv.stat().st_size
            successful_files.append(file_info)
        
        for result in failed_results:
            failed_files.append({
                'input_file': str(result.input_json),
                'error_message': result.error_message,
                'command_used': result.command_used
            })
        
        return {
            'total_files': len(results),
            'successful_conversions': len(successful_results),
            'failed_conversions': len(failed_results),
            'success_rate': len(successful_results) / len(results) if results else 0,
            'total_records_processed': total_records,
            'total_execution_time': total_execution_time,
            'successful_files': successful_files,
            'failed_files': failed_files
        }


class DirectJSONToCSVConverter:
    """Direct Python-based JSON to CSV converter (fallback when script not available)."""
    
    @staticmethod
    def convert_direct(
        input_json: Path,
        output_csv: Path,
        flatten_nested: bool = True
    ) -> ConversionResult:
        """
        Convert JSON to CSV directly using Python (no external script).
        
        Args:
            input_json: Path to input JSON file
            output_csv: Path for output CSV file
            flatten_nested: Whether to flatten nested JSON structures
        
        Returns:
            ConversionResult with execution details
        """
        try:
            import time
            start_time = time.time()
            
            # Read JSON data
            with open(input_json, 'r') as f:
                json_data = json.load(f)
            
            # Ensure data is a list
            if not isinstance(json_data, list):
                json_data = [json_data]
            
            if not json_data:
                return ConversionResult(
                    success=False,
                    input_json=input_json,
                    error_message="JSON file contains no data"
                )
            
            # Flatten nested structures if requested
            if flatten_nested:
                json_data = [_flatten_dict(record) for record in json_data]
            
            # Write CSV
            success = write_csv_safely(json_data, output_csv)
            execution_time = time.time() - start_time
            
            if success:
                return ConversionResult(
                    success=True,
                    input_json=input_json,
                    output_csv=output_csv,
                    record_count=len(json_data),
                    execution_time=execution_time
                )
            else:
                return ConversionResult(
                    success=False,
                    input_json=input_json,
                    error_message="Failed to write CSV file"
                )
        
        except Exception as e:
            return ConversionResult(
                success=False,
                input_json=input_json,
                error_message=f"Direct conversion error: {str(e)}"
            )


def _flatten_dict(d: Dict, parent_key: str = '', sep: str = '_') -> Dict:
    """
    Flatten nested dictionary structures.
    
    Args:
        d: Dictionary to flatten
        parent_key: Parent key for nested structures
        sep: Separator for nested keys
    
    Returns:
        Flattened dictionary
    """
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten_dict(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            # Convert list to string representation
            items.append((new_key, json.dumps(v)))
        else:
            items.append((new_key, v))
    return dict(items)


# Example configuration for different converter scripts
CONVERTER_SCRIPT_EXAMPLES = {
    "tesseract_script": {
        "description": "Tesseract JSON to CSV converter script",
        "command_template": "python {script_path} --input {input_json} --output {output_csv}",
        "required_params": ["script_path", "input_json", "output_csv"]
    },
    "custom_converter": {
        "description": "Custom JSON to CSV converter",
        "command_template": "{script_path} -i {input_json} -o {output_csv} --format csv",
        "required_params": ["script_path", "input_json", "output_csv"]
    },
    "direct_python": {
        "description": "Direct Python conversion (no external script)",
        "command_template": "Built-in Python conversion",
        "required_params": []
    }
}
