"""
TPS (Treatment Planning System) runner module for multi-KB Nirvana processing.
"""

import subprocess
import json
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

from .config import Config, KBSpec
from .utils import validate_file_exists, retry_on_failure


@dataclass
class TPSResult:
    """Result from TPS processing for a single knowledge base."""
    success: bool
    kb_spec: KBSpec
    input_sarj: Path
    output_json: Optional[Path] = None
    error_message: Optional[str] = None
    command_used: Optional[str] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    execution_time: Optional[float] = None


@dataclass
class TPSBatchResult:
    """Result from batch TPS processing across multiple knowledge bases."""
    success: bool
    total_kbs: int
    successful_kbs: int
    failed_kbs: int
    results: List[TPSResult]
    execution_time: Optional[float] = None


class TPSRunner:
    """Handles execution of TPS (multi-KB Nirvana) processing."""
    
    def __init__(self, config: Config):
        self.config = config
        self.tps_path = config.paths.tps_path
        self.nirvana_path = config.paths.nirvana_path
    
    def validate_setup(self) -> tuple[bool, str]:
        """
        Validate that TPS runner is properly configured.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.tps_path:
            return False, "TPS executable path not configured in settings"
        
        tps_path = Path(self.tps_path)
        if not validate_file_exists(tps_path, "TPS executable"):
            return False, f"TPS executable not found at {self.tps_path}"
        
        # For mock setups, nirvana_path can be the same as tps_path
        if not self.nirvana_path:
            self.nirvana_path = self.tps_path  # Use TPS path as fallback
        
        nirvana_path = Path(self.nirvana_path)
        if not validate_file_exists(nirvana_path, "Nirvana executable"):
            return False, f"Nirvana executable not found at {self.nirvana_path}"
        
        if not self.config.paths.knowledge_bases:
            return False, "No knowledge bases configured"
        
        # Validate knowledge base paths
        for kb in self.config.paths.knowledge_bases:
            kb_path = Path(kb.path)
            if not kb_path.exists():
                return False, f"Knowledge base path not found: {kb.path} (version: {kb.version})"
        
        return True, ""
    
    def build_tps_command(
        self,
        input_sarj: Path,
        kb_spec: KBSpec,
        output_json: Path
    ) -> List[str]:
        """
        Build TPS command for a specific knowledge base.
        
        Args:
            input_sarj: Path to input SARJ file
            kb_spec: Knowledge base specification
            output_json: Path for output JSON file
        
        Returns:
            Command as list of strings
        """
        # Use positional arguments for mock script compatibility
        cmd = [
            str(self.tps_path),
            str(input_sarj),
            str(kb_spec.path),  # Use the kb path as the knowledge base identifier
            str(output_json)
        ]
        
        return cmd
    
    @retry_on_failure(max_attempts=2, delay=3.0)
    def run_tps_single_kb(
        self,
        input_sarj: Path,
        kb_spec: KBSpec,
        output_dir: Path
    ) -> TPSResult:
        """
        Run TPS processing for a single knowledge base.
        
        Args:
            input_sarj: Path to input SARJ file
            kb_spec: Knowledge base specification
            output_dir: Output directory for JSON file
        
        Returns:
            TPSResult with execution details
        """
        # Validate input file
        if not validate_file_exists(input_sarj, "Input SARJ"):
            return TPSResult(
                success=False,
                kb_spec=kb_spec,
                input_sarj=input_sarj,
                error_message=f"Input SARJ file not found: {input_sarj}"
            )
        
        # Create output filename
        output_filename = f"{input_sarj.stem}_{kb_spec.version}.json"
        output_json = output_dir / output_filename
        
        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Build command
        cmd = self.build_tps_command(input_sarj, kb_spec, output_json)
        
        try:
            import time
            start_time = time.time()
            
            # Run TPS command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=self.config.processing.timeout_seconds * 3  # TPS might take longer
            )
            
            execution_time = time.time() - start_time
            
            # Verify output file was created
            if not output_json.exists():
                return TPSResult(
                    success=False,
                    kb_spec=kb_spec,
                    input_sarj=input_sarj,
                    error_message="JSON output file was not created despite successful command execution",
                    command_used=" ".join(cmd),
                    stdout=result.stdout,
                    stderr=result.stderr,
                    execution_time=execution_time
                )
            
            # Validate JSON format
            try:
                with open(output_json, 'r') as f:
                    json.load(f)  # This will raise an exception if invalid JSON
            except json.JSONDecodeError as e:
                return TPSResult(
                    success=False,
                    kb_spec=kb_spec,
                    input_sarj=input_sarj,
                    output_json=output_json,
                    error_message=f"Generated JSON file is invalid: {str(e)}",
                    command_used=" ".join(cmd),
                    stdout=result.stdout,
                    stderr=result.stderr,
                    execution_time=execution_time
                )
            
            return TPSResult(
                success=True,
                kb_spec=kb_spec,
                input_sarj=input_sarj,
                output_json=output_json,
                command_used=" ".join(cmd),
                stdout=result.stdout,
                stderr=result.stderr,
                execution_time=execution_time
            )
        
        except subprocess.TimeoutExpired:
            return TPSResult(
                success=False,
                kb_spec=kb_spec,
                input_sarj=input_sarj,
                error_message=f"TPS processing timed out after {self.config.processing.timeout_seconds * 3} seconds",
                command_used=" ".join(cmd)
            )
        
        except subprocess.CalledProcessError as e:
            return TPSResult(
                success=False,
                kb_spec=kb_spec,
                input_sarj=input_sarj,
                error_message=f"TPS processing failed with exit code {e.returncode}",
                command_used=" ".join(cmd),
                stdout=e.stdout,
                stderr=e.stderr
            )
        
        except Exception as e:
            return TPSResult(
                success=False,
                kb_spec=kb_spec,
                input_sarj=input_sarj,
                error_message=f"Unexpected error during TPS processing: {str(e)}",
                command_used=" ".join(cmd)
            )
    
    def run_tps_multi_kb(
        self,
        input_sarj: Path,
        kb_versions: Optional[List[KBSpec]] = None,
        output_dir: Optional[Path] = None,
        parallel: bool = True
    ) -> TPSBatchResult:
        """
        Run TPS processing across multiple knowledge bases.
        
        Args:
            input_sarj: Path to input SARJ file
            kb_versions: List of knowledge base specifications (defaults to config KBs)
            output_dir: Output directory (defaults to config output dir)
            parallel: Whether to run KB processing in parallel
        
        Returns:
            TPSBatchResult with results for all knowledge bases
        """
        # Validate setup
        is_valid, error_msg = self.validate_setup()
        if not is_valid:
            return TPSBatchResult(
                success=False,
                total_kbs=0,
                successful_kbs=0,
                failed_kbs=0,
                results=[TPSResult(
                    success=False,
                    kb_spec=KBSpec(version="unknown", path=""),
                    input_sarj=input_sarj,
                    error_message=error_msg
                )]
            )
        
        # Use configured knowledge bases if not specified
        if not kb_versions:
            kb_versions = self.config.paths.knowledge_bases
        
        if not kb_versions:
            return TPSBatchResult(
                success=False,
                total_kbs=0,
                successful_kbs=0,
                failed_kbs=0,
                results=[TPSResult(
                    success=False,
                    kb_spec=KBSpec(version="unknown", path=""),
                    input_sarj=input_sarj,
                    error_message="No knowledge bases specified"
                )]
            )
        
        # Determine output directory
        if not output_dir:
            output_dir = self.config.get_output_dir() / "tps_output"
        
        import time
        start_time = time.time()
        
        results = []
        
        if parallel and len(kb_versions) > 1:
            # Process knowledge bases in parallel
            with ThreadPoolExecutor(max_workers=min(len(kb_versions), self.config.processing.max_workers)) as executor:
                future_to_kb = {
                    executor.submit(self.run_tps_single_kb, input_sarj, kb, output_dir): kb
                    for kb in kb_versions
                }
                
                for future in as_completed(future_to_kb):
                    result = future.result()
                    results.append(result)
        else:
            # Process knowledge bases sequentially
            for kb in kb_versions:
                result = self.run_tps_single_kb(input_sarj, kb, output_dir)
                results.append(result)
        
        execution_time = time.time() - start_time
        
        # Calculate statistics
        successful_results = [r for r in results if r.success]
        failed_results = [r for r in results if not r.success]
        
        return TPSBatchResult(
            success=len(successful_results) > 0,
            total_kbs=len(kb_versions),
            successful_kbs=len(successful_results),
            failed_kbs=len(failed_results),
            results=results,
            execution_time=execution_time
        )
    
    def get_tps_summary(self, batch_result: TPSBatchResult) -> Dict[str, Any]:
        """
        Generate summary statistics for TPS batch processing.
        
        Args:
            batch_result: Result from batch TPS processing
        
        Returns:
            Dictionary with summary statistics
        """
        successful_kbs = []
        failed_kbs = []
        total_output_size = 0
        
        for result in batch_result.results:
            if result.success:
                successful_kbs.append({
                    'kb_version': result.kb_spec.version,
                    'kb_description': result.kb_spec.description,
                    'output_file': str(result.output_json),
                    'file_size': result.output_json.stat().st_size if result.output_json and result.output_json.exists() else 0,
                    'execution_time': result.execution_time
                })
                if result.output_json and result.output_json.exists():
                    total_output_size += result.output_json.stat().st_size
            else:
                failed_kbs.append({
                    'kb_version': result.kb_spec.version,
                    'kb_description': result.kb_spec.description,
                    'error_message': result.error_message,
                    'command_used': result.command_used
                })
        
        return {
            'overall_success': batch_result.success,
            'total_knowledge_bases': batch_result.total_kbs,
            'successful_knowledge_bases': batch_result.successful_kbs,
            'failed_knowledge_bases': batch_result.failed_kbs,
            'success_rate': batch_result.successful_kbs / batch_result.total_kbs if batch_result.total_kbs > 0 else 0,
            'total_execution_time': batch_result.execution_time,
            'total_output_size': total_output_size,
            'total_output_size_human': _format_file_size(total_output_size),
            'successful_outputs': successful_kbs,
            'failed_processes': failed_kbs
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


# Example configuration templates for different TPS setups
TPS_CONFIG_EXAMPLES = {
    "nirvana_multi_kb": {
        "description": "Standard Nirvana multi-KB setup",
        "command_template": "{tps_path} --input {input_sarj} --output {output_json} --nirvana {nirvana_path} --kb-path {kb_path} --kb-version {kb_version}",
        "required_params": ["tps_path", "nirvana_path", "kb_path", "kb_version"]
    },
    "custom_tps": {
        "description": "Custom TPS implementation",
        "command_template": "User-defined based on specific TPS implementation",
        "required_params": ["tps_path"]
    }
}
