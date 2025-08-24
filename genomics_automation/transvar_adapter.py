"""
TransVar adapter module - wraps TransVar CLI for protein annotation and VCF generation.
"""

import re
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd

from .config import Config
from .utils import FileProcessor, retry_on_failure


@dataclass
class TransVarResult:
    """Result from TransVar annotation."""
    gene: str
    transcript: str
    protein_change: str
    original_input: str
    success: bool
    vcf_line: Optional[str] = None
    error_message: Optional[str] = None
    coordinates: Optional[Dict[str, str]] = None
    auto_recovery: bool = False


class ProteinNotationCleaner:
    """Handles cleaning and normalization of protein notation."""
    
    # Three-letter to one-letter amino acid mapping
    AA_MAP = {
        'Ala': 'A', 'Arg': 'R', 'Asn': 'N', 'Asp': 'D', 'Cys': 'C',
        'Glu': 'E', 'Gln': 'Q', 'Gly': 'G', 'His': 'H', 'Ile': 'I',
        'Leu': 'L', 'Lys': 'K', 'Met': 'M', 'Phe': 'F', 'Pro': 'P',
        'Ser': 'S', 'Thr': 'T', 'Trp': 'W', 'Tyr': 'Y', 'Val': 'V',
        'Ter': '*', 'Stop': '*', 'X': 'X'
    }
    
    @classmethod
    def clean_protein_notation(cls, protein_change: str) -> str:
        """
        Clean and normalize protein notation.
        
        Args:
            protein_change: Raw protein change notation
        
        Returns:
            Cleaned protein notation
        """
        if not protein_change:
            return protein_change
        
        # Remove parentheses and extra whitespace
        cleaned = re.sub(r'[()]', '', protein_change.strip())
        
        # Convert three-letter amino acids to one-letter
        for three_letter, one_letter in cls.AA_MAP.items():
            cleaned = re.sub(f'\\b{three_letter}\\b', one_letter, cleaned, flags=re.IGNORECASE)
        
        # Normalize frameshift notation
        cleaned = re.sub(r'fs\*?\d*', 'fs', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'frameshift', 'fs', cleaned, flags=re.IGNORECASE)
        
        # Remove extra spaces
        cleaned = re.sub(r'\s+', '', cleaned)
        
        return cleaned


class CoordinateParser:
    """Parses and validates genomic coordinates from TransVar output."""
    
    @staticmethod
    def parse_coordinates(transvar_output: str) -> Dict[str, str]:
        """
        Parse coordinates from TransVar output.
        
        Args:
            transvar_output: Raw TransVar output
        
        Returns:
            Dictionary of parsed coordinates
        """
        coordinates = {}
        
        # Parse genomic coordinates (g.)
        g_match = re.search(r'(\w+):g\.(\d+)([ATCG]+>?[ATCG]*)', transvar_output)
        if g_match:
            coordinates['chrom'] = g_match.group(1)
            coordinates['pos'] = g_match.group(2)
            coordinates['change'] = g_match.group(3)
            coordinates['type'] = 'genomic'
        
        # Parse coding coordinates (c.)
        c_match = re.search(r'c\.([+-]?\d+)([ATCG]+>?[ATCG]*)', transvar_output)
        if c_match:
            coordinates['c_pos'] = c_match.group(1)
            coordinates['c_change'] = c_match.group(2)
        
        # Parse protein coordinates (p.)
        p_match = re.search(r'p\.([A-Z]\d+[A-Z*]?)', transvar_output)
        if p_match:
            coordinates['p_change'] = p_match.group(1)
        
        return coordinates
    
    @staticmethod
    def validate_coordinates(coordinates: Dict[str, str]) -> Tuple[bool, str]:
        """
        Validate parsed coordinates.
        
        Args:
            coordinates: Dictionary of parsed coordinates
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not coordinates:
            return False, "No coordinates found"
        
        if 'chrom' not in coordinates or 'pos' not in coordinates:
            return False, "Missing chromosome or position"
        
        try:
            int(coordinates['pos'])
        except ValueError:
            return False, f"Invalid position: {coordinates.get('pos')}"
        
        return True, ""


class VCFBuilder:
    """Builds VCF lines from TransVar results."""
    
    @staticmethod
    def build_vcf_header() -> str:
        """Build VCF header."""
        header_lines = [
            "##fileformat=VCFv4.2",
            "##source=GenomicsAutomationPipeline",
            "##INFO=<ID=GENE,Number=1,Type=String,Description=\"Gene symbol\">",
            "##INFO=<ID=TRANSCRIPT,Number=1,Type=String,Description=\"Transcript ID\">",
            "##INFO=<ID=PROTEIN,Number=1,Type=String,Description=\"Protein change\">",
            "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO"
        ]
        return "\n".join(header_lines)
    
    @staticmethod
    def build_vcf_line(result: TransVarResult) -> Optional[str]:
        """
        Build VCF line from TransVar result.
        
        Args:
            result: TransVar result with coordinates
        
        Returns:
            VCF line string or None if invalid
        """
        if not result.success or not result.coordinates:
            return None
        
        coords = result.coordinates
        
        # Extract chromosome and position
        chrom = coords.get('chrom', '.')
        pos = coords.get('pos', '.')
        
        # Parse REF and ALT from change notation
        change = coords.get('change', '')
        ref, alt = VCFBuilder._parse_change_notation(change)
        
        if not ref or not alt:
            return None
        
        # Build INFO field
        info_parts = []
        if result.gene:
            info_parts.append(f"GENE={result.gene}")
        if result.transcript:
            info_parts.append(f"TRANSCRIPT={result.transcript}")
        if result.protein_change:
            info_parts.append(f"PROTEIN={result.protein_change}")
        
        info_field = ";".join(info_parts) if info_parts else "."
        
        # Build VCF line
        vcf_line = f"{chrom}\t{pos}\t.\t{ref}\t{alt}\t.\t.\t{info_field}"
        
        return vcf_line
    
    @staticmethod
    def _parse_change_notation(change: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Parse REF and ALT from change notation.
        
        Args:
            change: Change notation (e.g., "A>T", "del", "ins")
        
        Returns:
            Tuple of (REF, ALT) or (None, None) if invalid
        """
        if not change:
            return None, None
        
        # Substitution: A>T
        sub_match = re.match(r'^([ATCG]+)>([ATCG]+)$', change)
        if sub_match:
            return sub_match.group(1), sub_match.group(2)
        
        # Deletion: del or delA
        del_match = re.match(r'^del([ATCG]*)$', change)
        if del_match:
            deleted = del_match.group(1) or "N"
            return deleted, "."
        
        # Insertion: insA
        ins_match = re.match(r'^ins([ATCG]+)$', change)
        if ins_match:
            inserted = ins_match.group(1)
            return ".", inserted
        
        # Complex changes - return as-is for now
        return change, "."


class TransVarAdapter:
    """Main adapter class for TransVar operations."""
    
    def __init__(self, config):
        self.config = config
        self.transvar_config = config.transvar  # Access transvar-specific config
        self.cleaner = ProteinNotationCleaner()
        self.parser = CoordinateParser()
        self.vcf_builder = VCFBuilder()
    
    def clean_protein_notation(self, protein_change: str) -> str:
        """Clean and normalize protein notation."""
        return self.cleaner.clean_protein_notation(protein_change)
    
    def build_transvar_command(self, notation: str, transcript: Optional[str] = None) -> List[str]:
        """
        Build TransVar command for annotation.
        
        Args:
            notation: Protein notation (e.g., "p.A123T")
            transcript: Optional preferred transcript
        
        Returns:
            Command as list of strings
        """
        cmd = [self.transvar_config.executable, "panno"]
        
        # Add database flags
        cmd.extend(["-d", self.transvar_config.database])
        cmd.extend(["--reference", self.transvar_config.ref_version])
        
        if self.transvar_config.use_ccds:
            cmd.append("--ccds")
            
        if self.transvar_config.reference_file:
            cmd.extend(["--refseq", self.transvar_config.reference_file])
            
        # Add any custom flags
        cmd.extend(self.transvar_config.custom_flags)
        
        # Add the notation
        if transcript:
            cmd.append(f"{transcript}:{notation}")
        else:
            cmd.append(notation)
        
        return cmd
    
    @retry_on_failure(max_attempts=3, delay=1.0)
    def run_transvar_panno(
        self,
        gene: str,
        protein_change: str,
        transcript: Optional[str] = None
    ) -> TransVarResult:
        """
        Run TransVar panno command for a single variant.
        
        Args:
            gene: Gene symbol
            protein_change: Protein change notation
            transcript: Optional preferred transcript
        
        Returns:
            TransVar result
        """
        original_input = f"{gene}:{protein_change}"
        
        # Clean protein notation
        cleaned_notation = self.cleaner.clean_protein_notation(protein_change)
        
        # Build command
        cmd = self.build_transvar_command(cleaned_notation, transcript)
        
        try:
            # Run TransVar
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=self.config.processing.timeout_seconds
            )
            
            # Parse output
            coordinates = self.parser.parse_coordinates(result.stdout)
            is_valid, error_msg = self.parser.validate_coordinates(coordinates)
            
            if is_valid:
                # Build VCF line
                transvar_result = TransVarResult(
                    gene=gene,
                    transcript=transcript or "",
                    protein_change=protein_change,
                    original_input=original_input,
                    success=True,
                    coordinates=coordinates
                )
                
                vcf_line = self.vcf_builder.build_vcf_line(transvar_result)
                transvar_result.vcf_line = vcf_line
                
                return transvar_result
            else:
                return TransVarResult(
                    gene=gene,
                    transcript=transcript or "",
                    protein_change=protein_change,
                    original_input=original_input,
                    success=False,
                    error_message=f"Invalid coordinates: {error_msg}"
                )
        
        except subprocess.TimeoutExpired:
            return TransVarResult(
                gene=gene,
                transcript=transcript or "",
                protein_change=protein_change,
                original_input=original_input,
                success=False,
                error_message="TransVar command timed out"
            )
        
        except subprocess.CalledProcessError as e:
            return TransVarResult(
                gene=gene,
                transcript=transcript or "",
                protein_change=protein_change,
                original_input=original_input,
                success=False,
                error_message=f"TransVar error: {e.stderr}"
            )
        
        except Exception as e:
            return TransVarResult(
                gene=gene,
                transcript=transcript or "",
                protein_change=protein_change,
                original_input=original_input,
                success=False,
                error_message=f"Unexpected error: {str(e)}"
            )
    
    def process_batch(
        self,
        variants: List[Dict[str, str]],
        preferred_transcripts: Optional[Dict[str, str]] = None
    ) -> Tuple[List[TransVarResult], Dict[str, Any]]:
        """
        Process a batch of variants with parallel execution.
        
        Args:
            variants: List of variant dictionaries with 'gene' and 'protein_change' keys
            preferred_transcripts: Optional mapping of genes to preferred transcripts
        
        Returns:
            Tuple of (results, metrics)
        """
        results = []
        metrics = {
            'total': len(variants),
            'successful': 0,
            'failed': 0,
            'auto_recovered': 0,
            'start_time': None,
            'end_time': None
        }
        
        preferred_transcripts = preferred_transcripts or {}
        
        with ThreadPoolExecutor(max_workers=self.config.processing.max_workers) as executor:
            # Submit jobs
            future_to_variant = {}
            for variant in variants:
                gene = variant.get('gene', '')
                protein_change = variant.get('protein_change', '')
                transcript = preferred_transcripts.get(gene)
                
                future = executor.submit(
                    self.run_transvar_panno,
                    gene,
                    protein_change,
                    transcript
                )
                future_to_variant[future] = variant
            
            # Collect results
            for future in as_completed(future_to_variant):
                result = future.result()
                results.append(result)
                
                if result.success:
                    metrics['successful'] += 1
                    if result.auto_recovery:
                        metrics['auto_recovered'] += 1
                else:
                    metrics['failed'] += 1
        
        return results, metrics


def convert_to_vcf_with_detailed_logs(
    results: List[TransVarResult],
    output_path: Path,
    log_failures: bool = True
) -> Dict[str, Any]:
    """
    Convert TransVar results to VCF format with detailed failure logging.
    
    Args:
        results: List of TransVar results
        output_path: Path for output VCF file
        log_failures: Whether to log detailed failure information
    
    Returns:
        Dictionary with conversion statistics and failure details
    """
    vcf_builder = VCFBuilder()
    
    # Separate successful and failed results
    successful_results = [r for r in results if r.success and r.vcf_line]
    failed_results = [r for r in results if not r.success or not r.vcf_line]
    
    # Write VCF file
    with open(output_path, 'w') as f:
        # Write header
        f.write(vcf_builder.build_vcf_header() + "\n")
        
        # Write successful VCF lines
        for result in successful_results:
            f.write(result.vcf_line + "\n")
    
    # Analyze failures
    failure_analysis = {}
    if log_failures:
        failure_types = {}
        coordinate_types = {}
        sample_failures = []
        
        for result in failed_results:
            error_msg = result.error_message or "Unknown error"
            failure_types[error_msg] = failure_types.get(error_msg, 0) + 1
            
            # Analyze coordinate types
            if result.coordinates:
                coord_type = result.coordinates.get('type', 'unknown')
                coordinate_types[coord_type] = coordinate_types.get(coord_type, 0) + 1
            
            # Collect sample failures
            if len(sample_failures) < 10:
                sample_failures.append({
                    'input': result.original_input,
                    'error': error_msg,
                    'gene': result.gene,
                    'protein_change': result.protein_change
                })
        
        failure_analysis = {
            'failure_types': failure_types,
            'coordinate_types': coordinate_types,
            'sample_failures': sample_failures,
            'recommendations': _generate_failure_recommendations(failure_types)
        }
    
    return {
        'total_variants': len(results),
        'successful_conversions': len(successful_results),
        'failed_conversions': len(failed_results),
        'success_rate': len(successful_results) / len(results) if results else 0,
        'output_file': str(output_path),
        'failure_analysis': failure_analysis
    }


def _generate_failure_recommendations(failure_types: Dict[str, int]) -> List[str]:
    """Generate recommendations based on failure patterns."""
    recommendations = []
    
    if any("coordinates" in error.lower() for error in failure_types.keys()):
        recommendations.append(
            "Consider checking protein notation format - ensure variants use standard HGVS notation"
        )
    
    if any("timeout" in error.lower() for error in failure_types.keys()):
        recommendations.append(
            "Some variants timed out - consider increasing timeout or checking TransVar installation"
        )
    
    if any("transcript" in error.lower() for error in failure_types.keys()):
        recommendations.append(
            "Transcript-related errors detected - verify transcript IDs are valid and current"
        )
    
    return recommendations
