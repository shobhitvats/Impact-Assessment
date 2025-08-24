"""
Report extractor module for generating final reports from CSV data.
"""

import csv
from pathlib import Path
from typing import List, Dict, Optional, Any, Set
from dataclasses import dataclass
import re

from .config import Config
from .utils import read_csv_with_encoding_detection, write_csv_safely


@dataclass
class ReportField:
    """Configuration for a field in the final report."""
    name: str
    source_columns: List[str]
    required: bool = False
    default_value: str = ""
    description: str = ""


@dataclass
class ExtractionResult:
    """Result from report extraction process."""
    success: bool
    input_files: List[Path]
    output_file: Optional[Path] = None
    records_extracted: int = 0
    error_message: Optional[str] = None
    extraction_summary: Optional[Dict[str, Any]] = None


class ReportExtractor:
    """Extracts key information from CSV files to generate final reports."""
    
    # Standard field mappings for genomics reports
    STANDARD_FIELDS = [
        ReportField(
            name="gene",
            source_columns=["gene", "Gene", "GENE", "gene_symbol", "Gene_Symbol"],
            required=True,
            description="Gene symbol"
        ),
        ReportField(
            name="variant",
            source_columns=["variant", "Variant", "VARIANT", "protein_change", "Protein_Change", "hgvs_p"],
            required=True,
            description="Variant notation"
        ),
        ReportField(
            name="transcript",
            source_columns=["transcript", "Transcript", "TRANSCRIPT", "transcript_id", "Transcript_ID"],
            required=False,
            description="Transcript identifier"
        ),
        ReportField(
            name="inferred_classification",
            source_columns=[
                "inferred_classification", "Inferred_Classification", "INFERRED_CLASSIFICATION",
                "classification", "Classification", "CLASSIFICATION",
                "pathogenicity", "Pathogenicity", "PATHOGENICITY"
            ],
            required=False,
            default_value="Unknown",
            description="Inferred variant classification"
        ),
        ReportField(
            name="diagnostic_assertions",
            source_columns=[
                "diagnostic_assertions", "Diagnostic_Assertions", "DIAGNOSTIC_ASSERTIONS",
                "diagnostic", "Diagnostic", "DIAGNOSTIC",
                "dx_assertions", "Dx_Assertions"
            ],
            required=False,
            description="Diagnostic assertions from knowledge base"
        ),
        ReportField(
            name="prognostic_assertions",
            source_columns=[
                "prognostic_assertions", "Prognostic_Assertions", "PROGNOSTIC_ASSERTIONS",
                "prognostic", "Prognostic", "PROGNOSTIC",
                "pr_assertions", "Pr_Assertions"
            ],
            required=False,
            description="Prognostic assertions from knowledge base"
        ),
        ReportField(
            name="therapeutic_assertions",
            source_columns=[
                "therapeutic_assertions", "Therapeutic_Assertions", "THERAPEUTIC_ASSERTIONS",
                "therapeutic", "Therapeutic", "THERAPEUTIC",
                "tx_assertions", "Tx_Assertions",
                "treatment", "Treatment", "TREATMENT"
            ],
            required=False,
            description="Therapeutic assertions from knowledge base"
        ),
        ReportField(
            name="trial_ids",
            source_columns=[
                "trial_ids", "Trial_IDs", "TRIAL_IDS",
                "clinical_trials", "Clinical_Trials", "CLINICAL_TRIALS",
                "trials", "Trials", "TRIALS",
                "trial_id", "Trial_ID"
            ],
            required=False,
            description="Clinical trial identifiers"
        ),
        ReportField(
            name="diseases",
            source_columns=[
                "diseases", "Diseases", "DISEASES",
                "disease", "Disease", "DISEASE",
                "conditions", "Conditions", "CONDITIONS",
                "indication", "Indication", "INDICATION"
            ],
            required=False,
            description="Associated diseases and conditions"
        ),
        ReportField(
            name="kb_version",
            source_columns=[
                "kb_version", "KB_Version", "KB_VERSION",
                "knowledge_base", "Knowledge_Base", "KNOWLEDGE_BASE",
                "database_version", "Database_Version"
            ],
            required=False,
            description="Knowledge base version used"
        )
    ]
    
    def __init__(self, config: Config):
        self.config = config
        self.fields = self.STANDARD_FIELDS.copy()
    
    def add_custom_field(self, field: ReportField) -> None:
        """Add a custom field to the extraction configuration."""
        self.fields.append(field)
    
    def _find_matching_column(self, available_columns: Set[str], field: ReportField) -> Optional[str]:
        """
        Find the first matching column for a field.
        
        Args:
            available_columns: Set of available column names
            field: Field configuration
        
        Returns:
            Matching column name or None
        """
        for source_col in field.source_columns:
            if source_col in available_columns:
                return source_col
        return None
    
    def _extract_kb_results(self, row: Dict[str, str]) -> Dict[str, str]:
        """
        Extract knowledge base results from a CSV row.
        
        Args:
            row: CSV row as dictionary
        
        Returns:
            Dictionary with extracted KB results
        """
        kb_results = {}
        
        # Look for KB results patterns
        kb_patterns = [
            r'kb_results?\.(.+)',
            r'knowledge_base\.(.+)',
            r'results?\.(.+)',
            r'assertions?\.(.+)'
        ]
        
        for column, value in row.items():
            for pattern in kb_patterns:
                match = re.match(pattern, column.lower())
                if match:
                    result_type = match.group(1)
                    if value and value.strip():
                        kb_results[result_type] = value
        
        return kb_results
    
    def _merge_list_values(self, values: List[str]) -> str:
        """
        Merge multiple list values into a single string.
        
        Args:
            values: List of string values
        
        Returns:
            Merged string value
        """
        # Remove empty values
        clean_values = [v.strip() for v in values if v and v.strip()]
        
        if not clean_values:
            return ""
        
        # If values look like JSON arrays, parse and merge
        merged_items = []
        for value in clean_values:
            if value.startswith('[') and value.endswith(']'):
                try:
                    import json
                    items = json.loads(value)
                    if isinstance(items, list):
                        merged_items.extend(items)
                    else:
                        merged_items.append(value)
                except json.JSONDecodeError:
                    merged_items.append(value)
            else:
                # Split on common delimiters
                if ';' in value:
                    merged_items.extend(v.strip() for v in value.split(';'))
                elif ',' in value:
                    merged_items.extend(v.strip() for v in value.split(','))
                else:
                    merged_items.append(value)
        
        # Remove duplicates while preserving order
        unique_items = []
        seen = set()
        for item in merged_items:
            if item not in seen:
                unique_items.append(item)
                seen.add(item)
        
        return '; '.join(unique_items)
    
    def extract_from_csv(self, csv_file: Path) -> List[Dict[str, str]]:
        """
        Extract data from a single CSV file.
        
        Args:
            csv_file: Path to CSV file
        
        Returns:
            List of extracted records
        """
        try:
            data = read_csv_with_encoding_detection(csv_file)
            if not data:
                return []
            
            available_columns = set(data[0].keys())
            extracted_records = []
            
            for row in data:
                extracted_row = {}
                
                # Extract standard fields
                for field in self.fields:
                    matching_column = self._find_matching_column(available_columns, field)
                    
                    if matching_column:
                        value = row.get(matching_column, "").strip()
                        extracted_row[field.name] = value if value else field.default_value
                    else:
                        extracted_row[field.name] = field.default_value
                
                # Extract KB results
                kb_results = self._extract_kb_results(row)
                if kb_results:
                    # Merge KB results into relevant fields
                    for result_type, value in kb_results.items():
                        if 'diagnostic' in result_type.lower():
                            existing = extracted_row.get('diagnostic_assertions', '')
                            extracted_row['diagnostic_assertions'] = self._merge_list_values([existing, value])
                        elif 'prognostic' in result_type.lower():
                            existing = extracted_row.get('prognostic_assertions', '')
                            extracted_row['prognostic_assertions'] = self._merge_list_values([existing, value])
                        elif 'therapeutic' in result_type.lower() or 'treatment' in result_type.lower():
                            existing = extracted_row.get('therapeutic_assertions', '')
                            extracted_row['therapeutic_assertions'] = self._merge_list_values([existing, value])
                        elif 'trial' in result_type.lower():
                            existing = extracted_row.get('trial_ids', '')
                            extracted_row['trial_ids'] = self._merge_list_values([existing, value])
                        elif 'disease' in result_type.lower() or 'condition' in result_type.lower():
                            existing = extracted_row.get('diseases', '')
                            extracted_row['diseases'] = self._merge_list_values([existing, value])
                
                # Add source file information
                extracted_row['source_file'] = csv_file.name
                
                extracted_records.append(extracted_row)
            
            return extracted_records
        
        except Exception as e:
            print(f"Error extracting from {csv_file}: {e}")
            return []
    
    def build_final_report(
        self,
        csv_files: List[Path],
        output_file: Optional[Path] = None
    ) -> ExtractionResult:
        """
        Build final report from multiple CSV files.
        
        Args:
            csv_files: List of CSV file paths
            output_file: Optional path for output file
        
        Returns:
            ExtractionResult with processing details
        """
        if not csv_files:
            return ExtractionResult(
                success=False,
                input_files=[],
                error_message="No CSV files provided"
            )
        
        # Determine output file
        if not output_file:
            output_file = self.config.get_output_dir() / "final_report.csv"
        
        try:
            all_records = []
            file_summaries = {}
            
            # Extract from each CSV file
            for csv_file in csv_files:
                if not csv_file.exists():
                    print(f"Warning: CSV file not found: {csv_file}")
                    continue
                
                records = self.extract_from_csv(csv_file)
                all_records.extend(records)
                
                file_summaries[str(csv_file)] = {
                    'records_extracted': len(records),
                    'file_size': csv_file.stat().st_size
                }
            
            if not all_records:
                return ExtractionResult(
                    success=False,
                    input_files=csv_files,
                    error_message="No records extracted from any CSV files"
                )
            
            # Add record metadata
            for i, record in enumerate(all_records):
                record['record_id'] = f"record_{i+1:04d}"
                record['extraction_timestamp'] = self._get_timestamp()
            
            # Write final report
            success = write_csv_safely(all_records, output_file)
            
            if not success:
                return ExtractionResult(
                    success=False,
                    input_files=csv_files,
                    error_message="Failed to write final report CSV"
                )
            
            # Generate summary
            extraction_summary = {
                'total_input_files': len(csv_files),
                'files_processed': len([f for f in csv_files if f.exists()]),
                'total_records': len(all_records),
                'file_summaries': file_summaries,
                'field_coverage': self._analyze_field_coverage(all_records),
                'kb_versions_found': self._find_kb_versions(all_records)
            }
            
            return ExtractionResult(
                success=True,
                input_files=csv_files,
                output_file=output_file,
                records_extracted=len(all_records),
                extraction_summary=extraction_summary
            )
        
        except Exception as e:
            return ExtractionResult(
                success=False,
                input_files=csv_files,
                error_message=f"Error building final report: {str(e)}"
            )
    
    def _analyze_field_coverage(self, records: List[Dict[str, str]]) -> Dict[str, Any]:
        """Analyze field coverage across all records."""
        if not records:
            return {}
        
        field_stats = {}
        total_records = len(records)
        
        for field in self.fields:
            populated_count = sum(1 for record in records if record.get(field.name, '').strip())
            field_stats[field.name] = {
                'populated_records': populated_count,
                'coverage_percentage': (populated_count / total_records) * 100,
                'required': field.required
            }
        
        return field_stats
    
    def _find_kb_versions(self, records: List[Dict[str, str]]) -> List[str]:
        """Find all knowledge base versions used in the records."""
        kb_versions = set()
        
        for record in records:
            kb_version = record.get('kb_version', '').strip()
            if kb_version:
                kb_versions.add(kb_version)
        
        return sorted(list(kb_versions))
    
    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def generate_report_documentation(self) -> str:
        """Generate documentation for the final report format."""
        docs = []
        
        docs.append("# Final Report Documentation\n")
        docs.append("This document describes the structure and fields of the final genomics impact assessment report.\n")
        
        docs.append("## Report Fields\n")
        
        for field in self.fields:
            required_marker = " *(Required)*" if field.required else ""
            docs.append(f"### {field.name.title()}{required_marker}")
            docs.append(f"- **Description**: {field.description}")
            docs.append(f"- **Source Columns**: {', '.join(field.source_columns)}")
            if field.default_value:
                docs.append(f"- **Default Value**: {field.default_value}")
            docs.append("")
        
        docs.append("## Additional Fields\n")
        docs.append("- **source_file**: Name of the source CSV file")
        docs.append("- **record_id**: Unique identifier for each record")
        docs.append("- **extraction_timestamp**: Timestamp when the record was extracted")
        
        docs.append("\n## Data Processing Notes\n")
        docs.append("- Multiple values in list fields are separated by semicolons (;)")
        docs.append("- Knowledge base results are automatically parsed and merged into relevant assertion fields")
        docs.append("- Empty values are replaced with default values where specified")
        docs.append("- Records from multiple CSV files are consolidated into a single report")
        
        return "\n".join(docs)
