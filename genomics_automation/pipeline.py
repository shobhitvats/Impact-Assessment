"""
Main pipeline orchestrator for the genomics automation workflow.
"""

import time
from pathlib import Path
from typing import List, Dict, Optional, Any, Union
from dataclasses import dataclass
from enum import Enum

from .config import Config
from .transvar_adapter import TransVarAdapter
from .vcf_builder import BatchVCFProcessor
from .sarj_runner import SARJRunner
from .tps_runner import TPSRunner
from .json_to_csv import JSONToCSVConverter
from .report_extractor import ReportExtractor
from .utils import generate_run_id, create_run_directory, FileProcessor


class PipelineStage(Enum):
    """Pipeline processing stages."""
    INPUT_VALIDATION = "input_validation"
    TRANSVAR_ANNOTATION = "transvar_annotation"
    VCF_GENERATION = "vcf_generation"
    SARJ_GENERATION = "sarj_generation"
    TPS_PROCESSING = "tps_processing"
    JSON_TO_CSV = "json_to_csv"
    REPORT_EXTRACTION = "report_extraction"
    COMPLETE = "complete"


@dataclass
class PipelineStatus:
    """Status update from pipeline processing."""
    stage: PipelineStage
    progress: float  # 0.0 to 1.0
    message: str
    details: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@dataclass
class PipelineInput:
    """Input specification for the pipeline."""
    mode: str  # "variants", "csv", "vcf"
    data: Any  # List of variants, CSV file path, or VCF file path
    preferred_transcripts: Optional[Dict[str, str]] = None
    output_dir: Optional[Path] = None


@dataclass
class PipelineResult:
    """Complete result from pipeline execution."""
    success: bool
    run_id: str
    run_directory: Path
    execution_time: float
    stages_completed: List[PipelineStage]
    artifacts: Dict[str, Path]
    errors: List[str]
    final_report: Optional[Path] = None
    metrics: Optional[Dict[str, Any]] = None


class GenomicsPipeline:
    """Main pipeline orchestrator for genomics automation."""
    
    def __init__(self, config: Config):
        self.config = config
        self.transvar_adapter = TransVarAdapter(config)
        self.vcf_processor = None  # Initialized with run directory
        self.sarj_runner = SARJRunner(config)
        self.tps_runner = TPSRunner(config)
        self.json_converter = JSONToCSVConverter(config)
        self.report_extractor = ReportExtractor(config)
        
        self.current_run_id = None
        self.current_run_dir = None
        self.status_callbacks = []
    
    def add_status_callback(self, callback) -> None:
        """Add a callback function for status updates."""
        self.status_callbacks.append(callback)
    
    def _emit_status(
        self,
        stage: PipelineStage,
        progress: float,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ) -> None:
        """Emit status update to all registered callbacks."""
        status = PipelineStatus(
            stage=stage,
            progress=progress,
            message=message,
            details=details,
            error=error
        )
        
        for callback in self.status_callbacks:
            try:
                callback(status)
            except Exception as e:
                print(f"Error in status callback: {e}")
    
    def _prepare_run_environment(self, output_dir: Optional[Path] = None) -> Path:
        """Prepare the run environment and directory structure."""
        self.current_run_id = generate_run_id()
        
        base_dir = output_dir or self.config.get_output_dir()
        self.current_run_dir = create_run_directory(base_dir, self.current_run_id)
        
        # Initialize VCF processor with run directory
        self.vcf_processor = BatchVCFProcessor(self.current_run_dir)
        
        return self.current_run_dir
    
    def _validate_input(self, pipeline_input: PipelineInput) -> tuple[bool, str]:
        """Validate pipeline input."""
        if not pipeline_input.mode:
            return False, "Input mode not specified"
        
        if pipeline_input.mode not in ["variants", "csv", "vcf"]:
            return False, f"Invalid input mode: {pipeline_input.mode}"
        
        if not pipeline_input.data:
            return False, "No input data provided"
        
        if pipeline_input.mode == "csv":
            csv_path = Path(pipeline_input.data)
            if not csv_path.exists():
                return False, f"CSV file not found: {csv_path}"
        
        if pipeline_input.mode == "vcf":
            vcf_path = Path(pipeline_input.data)
            if not vcf_path.exists():
                return False, f"VCF file not found: {vcf_path}"
        
        return True, ""
    
    def _process_variant_input(self, variants: List[Dict[str, str]]) -> tuple[List, Dict[str, Any]]:
        """Process variant list input through TransVar."""
        self._emit_status(
            PipelineStage.TRANSVAR_ANNOTATION,
            0.1,
            f"Starting TransVar annotation for {len(variants)} variants"
        )
        
        # Run TransVar annotation
        results, metrics = self.transvar_adapter.process_batch(
            variants,
            preferred_transcripts={}  # Could be passed from input
        )
        
        self._emit_status(
            PipelineStage.TRANSVAR_ANNOTATION,
            0.8,
            f"TransVar annotation complete: {metrics['successful']} successful, {metrics['failed']} failed"
        )
        
        return results, metrics
    
    def _process_csv_input(self, csv_path: Path) -> tuple[List, Dict[str, Any]]:
        """Process CSV input through TransVar."""
        # Read CSV and convert to variant list
        from .utils import read_csv_with_encoding_detection
        
        csv_data = read_csv_with_encoding_detection(csv_path)
        
        # Convert CSV rows to variant format
        variants = []
        for row in csv_data:
            # Look for common column names
            gene = row.get('gene', row.get('Gene', row.get('GENE', '')))
            protein_change = row.get('protein_change', row.get('Protein_Change', 
                                   row.get('variant', row.get('Variant', ''))))
            
            if gene and protein_change:
                variants.append({
                    'gene': gene,
                    'protein_change': protein_change
                })
        
        return self._process_variant_input(variants)
    
    def _generate_vcf(self, transvar_results: List) -> Path:
        """Generate VCF file from TransVar results."""
        self._emit_status(
            PipelineStage.VCF_GENERATION,
            0.1,
            "Generating VCF file from TransVar results"
        )
        
        vcf_stats = self.vcf_processor.process_transvar_results(
            transvar_results,
            "pipeline_variants.vcf"
        )
        
        vcf_path = Path(vcf_stats['vcf_file'])
        
        self._emit_status(
            PipelineStage.VCF_GENERATION,
            1.0,
            f"VCF generation complete: {vcf_stats['supported_variants']} variants processed",
            details=vcf_stats
        )
        
        return vcf_path
    
    def _run_sarj(self, vcf_path: Path) -> Path:
        """Run SARJ generation."""
        self._emit_status(
            PipelineStage.SARJ_GENERATION,
            0.1,
            "Starting SARJ generation from VCF"
        )
        
        sarj_result = self.sarj_runner.run_sarj(vcf_path, self.current_run_dir)
        
        if not sarj_result.success:
            raise RuntimeError(f"SARJ generation failed: {sarj_result.error_message}")
        
        self._emit_status(
            PipelineStage.SARJ_GENERATION,
            1.0,
            f"SARJ generation complete: {sarj_result.output_sarj}",
            details={
                'execution_time': sarj_result.execution_time,
                'command_used': sarj_result.command_used
            }
        )
        
        return sarj_result.output_sarj
    
    def _run_tps(self, sarj_path: Path) -> List[Path]:
        """Run TPS processing."""
        self._emit_status(
            PipelineStage.TPS_PROCESSING,
            0.1,
            "Starting TPS processing with multiple knowledge bases"
        )
        
        batch_result = self.tps_runner.run_tps_multi_kb(
            sarj_path,
            output_dir=self.current_run_dir / "tps_output"
        )
        
        if not batch_result.success or batch_result.successful_kbs == 0:
            failed_kbs = [r.error_message for r in batch_result.results if not r.success]
            raise RuntimeError(f"TPS processing failed: {'; '.join(failed_kbs)}")
        
        json_files = [r.output_json for r in batch_result.results if r.success and r.output_json]
        
        self._emit_status(
            PipelineStage.TPS_PROCESSING,
            1.0,
            f"TPS processing complete: {len(json_files)} knowledge bases processed",
            details={
                'successful_kbs': batch_result.successful_kbs,
                'failed_kbs': batch_result.failed_kbs,
                'execution_time': batch_result.execution_time
            }
        )
        
        return json_files
    
    def _convert_json_to_csv(self, json_files: List[Path]) -> List[Path]:
        """Convert JSON files to CSV."""
        self._emit_status(
            PipelineStage.JSON_TO_CSV,
            0.1,
            f"Converting {len(json_files)} JSON files to CSV"
        )
        
        csv_output_dir = self.current_run_dir / "csv_output"
        conversion_results = self.json_converter.convert_batch_json_to_csv(
            json_files,
            csv_output_dir
        )
        
        successful_results = [r for r in conversion_results if r.success]
        
        if not successful_results:
            raise RuntimeError("All JSON to CSV conversions failed")
        
        csv_files = [r.output_csv for r in successful_results if r.output_csv]
        
        self._emit_status(
            PipelineStage.JSON_TO_CSV,
            1.0,
            f"JSON to CSV conversion complete: {len(csv_files)} files converted",
            details={
                'successful_conversions': len(successful_results),
                'total_files': len(conversion_results)
            }
        )
        
        return csv_files
    
    def _extract_final_report(self, csv_files: List[Path]) -> Path:
        """Extract final report from CSV files."""
        self._emit_status(
            PipelineStage.REPORT_EXTRACTION,
            0.1,
            f"Extracting final report from {len(csv_files)} CSV files"
        )
        
        final_report_path = self.current_run_dir / "final_report.csv"
        extraction_result = self.report_extractor.build_final_report(
            csv_files,
            final_report_path
        )
        
        if not extraction_result.success:
            raise RuntimeError(f"Report extraction failed: {extraction_result.error_message}")
        
        self._emit_status(
            PipelineStage.REPORT_EXTRACTION,
            1.0,
            f"Final report extracted: {extraction_result.records_extracted} records",
            details=extraction_result.extraction_summary
        )
        
        return extraction_result.output_file
    
    def run_full_pipeline(self, pipeline_input: PipelineInput) -> PipelineResult:
        """
        Execute the complete genomics automation pipeline.
        
        Args:
            pipeline_input: Input specification
        
        Returns:
            Complete pipeline result
        """
        start_time = time.time()
        stages_completed = []
        artifacts = {}
        errors = []
        
        try:
            # Prepare run environment
            run_dir = self._prepare_run_environment(pipeline_input.output_dir)
            
            # Validate input
            self._emit_status(PipelineStage.INPUT_VALIDATION, 0.1, "Validating input")
            is_valid, error_msg = self._validate_input(pipeline_input)
            if not is_valid:
                raise ValueError(error_msg)
            
            stages_completed.append(PipelineStage.INPUT_VALIDATION)
            
            # Process input to get VCF
            if pipeline_input.mode == "vcf":
                # Use VCF directly
                vcf_path = Path(pipeline_input.data)
                self._emit_status(
                    PipelineStage.VCF_GENERATION,
                    1.0,
                    f"Using provided VCF file: {vcf_path}"
                )
            else:
                # Process through TransVar
                if pipeline_input.mode == "variants":
                    transvar_results, transvar_metrics = self._process_variant_input(pipeline_input.data)
                elif pipeline_input.mode == "csv":
                    transvar_results, transvar_metrics = self._process_csv_input(Path(pipeline_input.data))
                
                stages_completed.append(PipelineStage.TRANSVAR_ANNOTATION)
                artifacts['transvar_metrics'] = transvar_metrics
                
                # Generate VCF
                vcf_path = self._generate_vcf(transvar_results)
            
            stages_completed.append(PipelineStage.VCF_GENERATION)
            artifacts['vcf_file'] = vcf_path
            
            # Run SARJ if enabled
            if self.config.stages.run_sarj:
                sarj_path = self._run_sarj(vcf_path)
                stages_completed.append(PipelineStage.SARJ_GENERATION)
                artifacts['sarj_file'] = sarj_path
            else:
                raise RuntimeError("SARJ generation disabled but required for pipeline")
            
            # Run TPS if enabled
            if self.config.stages.run_tps:
                json_files = self._run_tps(sarj_path)
                stages_completed.append(PipelineStage.TPS_PROCESSING)
                artifacts['tps_json_files'] = json_files
            else:
                raise RuntimeError("TPS processing disabled but required for pipeline")
            
            # Convert JSON to CSV if enabled
            if self.config.stages.run_json_conversion:
                csv_files = self._convert_json_to_csv(json_files)
                stages_completed.append(PipelineStage.JSON_TO_CSV)
                artifacts['csv_files'] = csv_files
            else:
                raise RuntimeError("JSON to CSV conversion disabled but required for pipeline")
            
            # Extract final report if enabled
            final_report = None
            if self.config.stages.run_report_extraction:
                final_report = self._extract_final_report(csv_files)
                stages_completed.append(PipelineStage.REPORT_EXTRACTION)
                artifacts['final_report'] = final_report
            
            stages_completed.append(PipelineStage.COMPLETE)
            
            execution_time = time.time() - start_time
            
            self._emit_status(
                PipelineStage.COMPLETE,
                1.0,
                f"Pipeline completed successfully in {execution_time:.2f} seconds"
            )
            
            return PipelineResult(
                success=True,
                run_id=self.current_run_id,
                run_directory=run_dir,
                execution_time=execution_time,
                stages_completed=stages_completed,
                artifacts=artifacts,
                errors=errors,
                final_report=final_report,
                metrics={
                    'stages_completed': len(stages_completed),
                    'total_stages': len(PipelineStage),
                    'artifacts_generated': len(artifacts)
                }
            )
        
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = str(e)
            errors.append(error_msg)
            
            self._emit_status(
                stages_completed[-1] if stages_completed else PipelineStage.INPUT_VALIDATION,
                0.0,
                f"Pipeline failed: {error_msg}",
                error=error_msg
            )
            
            return PipelineResult(
                success=False,
                run_id=self.current_run_id or "unknown",
                run_directory=self.current_run_dir or Path(),
                execution_time=execution_time,
                stages_completed=stages_completed,
                artifacts=artifacts,
                errors=errors
            )


def run_full_pipeline(
    inputs: Union[List[Dict[str, str]], Path, str],
    config: Optional[Config] = None,
    output_dir: Optional[Path] = None
) -> PipelineResult:
    """
    Convenience function to run the full pipeline.
    
    Args:
        inputs: Input data (variants list, CSV path, or VCF path)
        config: Optional configuration (uses default if not provided)
        output_dir: Optional output directory
    
    Returns:
        Pipeline result
    """
    if config is None:
        from .config import default_config
        config = default_config
    
    pipeline = GenomicsPipeline(config)
    
    # Determine input mode
    if isinstance(inputs, list):
        pipeline_input = PipelineInput(
            mode="variants",
            data=inputs,
            output_dir=output_dir
        )
    elif isinstance(inputs, (Path, str)):
        input_path = Path(inputs)
        if input_path.suffix.lower() == '.vcf':
            pipeline_input = PipelineInput(
                mode="vcf",
                data=input_path,
                output_dir=output_dir
            )
        else:  # Assume CSV
            pipeline_input = PipelineInput(
                mode="csv",
                data=input_path,
                output_dir=output_dir
            )
    else:
        raise ValueError("Invalid input type. Expected list, Path, or string.")
    
    return pipeline.run_full_pipeline(pipeline_input)
