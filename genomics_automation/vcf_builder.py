"""
VCF builder module for generating VCF files from various input formats.
"""

import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

from .transvar_adapter import TransVarResult, VCFBuilder as BaseVCFBuilder
from .utils import write_csv_safely


class VariantType(Enum):
    """Supported variant types."""
    SUBSTITUTION = "substitution"
    DELETION = "deletion"
    INSERTION = "insertion"
    INDEL = "indel"
    CNV_GAIN = "cnv_gain"
    CNV_LOSS = "cnv_loss"
    SPLICE = "splice"
    RNA_FUSION = "rna_fusion"
    DNA_FUSION = "dna_fusion"
    COMPLEX = "complex"


@dataclass
class VariantTemplate:
    """Template for generating VCF entries from different variant types."""
    variant_type: VariantType
    pattern: str
    description: str
    supported: bool = True
    requires_coordinates: bool = False


class VariantClassifier:
    """Classifies variants based on notation patterns."""
    
    # Variant classification patterns
    PATTERNS = {
        VariantType.SUBSTITUTION: [
            r'p\.[A-Z]\d+[A-Z]',  # p.A123T
            r'c\.\d+[ATCG]>[ATCG]',  # c.123A>T
            r'g\.\d+[ATCG]>[ATCG]'   # g.123A>T
        ],
        VariantType.DELETION: [
            r'p\.[A-Z]\d+del',  # p.A123del
            r'c\.\d+del[ATCG]*',  # c.123delA
            r'g\.\d+del[ATCG]*'   # g.123delA
        ],
        VariantType.INSERTION: [
            r'p\.[A-Z]\d+_[A-Z]\d+ins[A-Z]+',  # p.A123_T124insV
            r'c\.\d+_\d+ins[ATCG]+',  # c.123_124insA
            r'g\.\d+_\d+ins[ATCG]+'   # g.123_124insA
        ],
        VariantType.CNV_GAIN: [
            r'gain',
            r'amplification',
            r'duplication'
        ],
        VariantType.CNV_LOSS: [
            r'loss',
            r'deletion',
            r'del(?!.)',  # 'del' not followed by nucleotides
        ],
        VariantType.SPLICE: [
            r'splice',
            r'exon.*skip',
            r'intron'
        ],
        VariantType.RNA_FUSION: [
            r'rna.*fusion',
            r'transcript.*fusion'
        ],
        VariantType.DNA_FUSION: [
            r'dna.*fusion',
            r'chromosomal.*rearrangement'
        ]
    }
    
    @classmethod
    def classify_variant(cls, notation: str) -> VariantType:
        """
        Classify a variant based on its notation.
        
        Args:
            notation: Variant notation string
        
        Returns:
            VariantType classification
        """
        notation_lower = notation.lower()
        
        for variant_type, patterns in cls.PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, notation_lower):
                    return variant_type
        
        return VariantType.COMPLEX


class EnhancedVCFBuilder(BaseVCFBuilder):
    """Enhanced VCF builder with support for multiple variant types."""
    
    # Templates for different variant types
    VARIANT_TEMPLATES = {
        VariantType.SUBSTITUTION: VariantTemplate(
            variant_type=VariantType.SUBSTITUTION,
            pattern="Standard substitution variants (p.A123T, c.123A>T)",
            description="Single nucleotide or amino acid substitutions",
            supported=True
        ),
        VariantType.DELETION: VariantTemplate(
            variant_type=VariantType.DELETION,
            pattern="Deletion variants (p.A123del, c.123delA)",
            description="Small deletions",
            supported=True
        ),
        VariantType.INSERTION: VariantTemplate(
            variant_type=VariantType.INSERTION,
            pattern="Insertion variants (p.A123_T124insV, c.123_124insA)",
            description="Small insertions",
            supported=True
        ),
        VariantType.CNV_GAIN: VariantTemplate(
            variant_type=VariantType.CNV_GAIN,
            pattern="CNV gain/amplification",
            description="Copy number gains - requires user-provided coordinates",
            supported=False,
            requires_coordinates=True
        ),
        VariantType.CNV_LOSS: VariantTemplate(
            variant_type=VariantType.CNV_LOSS,
            pattern="CNV loss/deletion",
            description="Copy number losses - requires user-provided coordinates",
            supported=False,
            requires_coordinates=True
        ),
        VariantType.SPLICE: VariantTemplate(
            variant_type=VariantType.SPLICE,
            pattern="Splice variants (exon skipping)",
            description="Splicing alterations - requires user-provided breakpoints",
            supported=False,
            requires_coordinates=True
        ),
        VariantType.RNA_FUSION: VariantTemplate(
            variant_type=VariantType.RNA_FUSION,
            pattern="RNA fusion events",
            description="RNA transcript fusions - requires user-provided breakpoints per gene",
            supported=False,
            requires_coordinates=True
        ),
        VariantType.DNA_FUSION: VariantTemplate(
            variant_type=VariantType.DNA_FUSION,
            pattern="DNA fusion events",
            description="DNA rearrangements and fusions - requires user-provided breakpoints per gene",
            supported=False,
            requires_coordinates=True
        )
    }
    
    @classmethod
    def get_supported_templates(cls) -> List[VariantTemplate]:
        """Get list of supported variant templates."""
        return [template for template in cls.VARIANT_TEMPLATES.values() if template.supported]
    
    @classmethod
    def get_unsupported_templates(cls) -> List[VariantTemplate]:
        """Get list of unsupported variant templates with placeholders."""
        return [template for template in cls.VARIANT_TEMPLATES.values() if not template.supported]
    
    @classmethod
    def build_enhanced_vcf_header(cls, include_templates: bool = True) -> str:
        """
        Build enhanced VCF header with template information.
        
        Args:
            include_templates: Whether to include variant template information
        
        Returns:
            VCF header string
        """
        header_lines = [
            "##fileformat=VCFv4.2",
            "##source=GenomicsAutomationPipeline",
            f"##automationVersion=1.0.0",
            "##INFO=<ID=GENE,Number=1,Type=String,Description=\"Gene symbol\">",
            "##INFO=<ID=TRANSCRIPT,Number=1,Type=String,Description=\"Transcript ID\">",
            "##INFO=<ID=PROTEIN,Number=1,Type=String,Description=\"Protein change\">",
            "##INFO=<ID=VARIANT_TYPE,Number=1,Type=String,Description=\"Variant classification\">",
            "##INFO=<ID=AUTO_GENERATED,Number=0,Type=Flag,Description=\"Automatically generated from TransVar\">"
        ]
        
        if include_templates:
            header_lines.append("##AUTOMATION_SCOPE=Small variants (substitutions, small indels)")
            header_lines.append("##AUTOMATION_EXCLUDED=CNV, splice, RNA/DNA fusions (require manual coordinates)")
        
        header_lines.append("#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO")
        
        return "\n".join(header_lines)
    
    @classmethod
    def build_enhanced_vcf_line(cls, result: TransVarResult, include_classification: bool = True) -> Optional[str]:
        """
        Build enhanced VCF line with variant classification.
        
        Args:
            result: TransVar result
            include_classification: Whether to include variant type classification
        
        Returns:
            Enhanced VCF line or None if invalid
        """
        if not result.success or not result.coordinates:
            return None
        
        coords = result.coordinates
        
        # Extract chromosome and position
        chrom = coords.get('chrom', '.')
        pos = coords.get('pos', '.')
        
        # Parse REF and ALT from change notation
        change = coords.get('change', '')
        ref, alt = cls._parse_change_notation(change)
        
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
        
        # Add variant classification
        if include_classification:
            variant_type = VariantClassifier.classify_variant(result.protein_change)
            info_parts.append(f"VARIANT_TYPE={variant_type.value}")
        
        # Mark as auto-generated
        info_parts.append("AUTO_GENERATED")
        
        info_field = ";".join(info_parts) if info_parts else "."
        
        # Build VCF line
        vcf_line = f"{chrom}\t{pos}\t.\t{ref}\t{alt}\t.\t.\t{info_field}"
        
        return vcf_line


class BatchVCFProcessor:
    """Processes batches of variants and generates VCF files."""
    
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.vcf_builder = EnhancedVCFBuilder()
        self.classifier = VariantClassifier()
    
    def process_transvar_results(
        self,
        results: List[TransVarResult],
        output_filename: str = "variants.vcf"
    ) -> Dict[str, Any]:
        """
        Process TransVar results and generate VCF file.
        
        Args:
            results: List of TransVar results
            output_filename: Name for output VCF file
        
        Returns:
            Processing statistics and file paths
        """
        output_path = self.output_dir / output_filename
        
        # Classify variants by type
        type_counts = {}
        supported_results = []
        unsupported_results = []
        
        for result in results:
            if result.success:
                variant_type = self.classifier.classify_variant(result.protein_change)
                type_counts[variant_type.value] = type_counts.get(variant_type.value, 0) + 1
                
                template = self.vcf_builder.VARIANT_TEMPLATES.get(variant_type)
                if template and template.supported:
                    supported_results.append(result)
                else:
                    unsupported_results.append((result, variant_type))
        
        # Generate VCF for supported variants
        vcf_stats = self._generate_vcf_file(supported_results, output_path)
        
        # Generate reports for unsupported variants
        unsupported_stats = self._generate_unsupported_report(unsupported_results)
        
        return {
            'vcf_file': str(output_path),
            'total_variants': len(results),
            'supported_variants': len(supported_results),
            'unsupported_variants': len(unsupported_results),
            'variant_type_counts': type_counts,
            'vcf_statistics': vcf_stats,
            'unsupported_statistics': unsupported_stats
        }
    
    def _generate_vcf_file(self, results: List[TransVarResult], output_path: Path) -> Dict[str, Any]:
        """Generate VCF file from supported results."""
        successful_lines = []
        failed_lines = []
        
        with open(output_path, 'w') as f:
            # Write header
            f.write(self.vcf_builder.build_enhanced_vcf_header() + "\n")
            
            # Process each result
            for result in results:
                vcf_line = self.vcf_builder.build_enhanced_vcf_line(result)
                if vcf_line:
                    f.write(vcf_line + "\n")
                    successful_lines.append(result)
                else:
                    failed_lines.append(result)
        
        return {
            'output_file': str(output_path),
            'successful_lines': len(successful_lines),
            'failed_lines': len(failed_lines),
            'success_rate': len(successful_lines) / len(results) if results else 0
        }
    
    def _generate_unsupported_report(
        self,
        unsupported_results: List[Tuple[TransVarResult, VariantType]]
    ) -> Dict[str, Any]:
        """Generate report for unsupported variant types."""
        if not unsupported_results:
            return {'count': 0, 'types': {}}
        
        # Count by type
        type_counts = {}
        for result, variant_type in unsupported_results:
            type_counts[variant_type.value] = type_counts.get(variant_type.value, 0) + 1
        
        # Generate CSV report
        report_data = []
        for result, variant_type in unsupported_results:
            template = self.vcf_builder.VARIANT_TEMPLATES.get(variant_type)
            report_data.append({
                'gene': result.gene,
                'protein_change': result.protein_change,
                'variant_type': variant_type.value,
                'reason_skipped': template.description if template else "Unknown variant type",
                'requires_coordinates': template.requires_coordinates if template else True,
                'original_input': result.original_input
            })
        
        # Write report
        report_path = self.output_dir / "unsupported_variants.csv"
        write_csv_safely(report_data, report_path)
        
        return {
            'count': len(unsupported_results),
            'types': type_counts,
            'report_file': str(report_path),
            'details': report_data[:10]  # First 10 for preview
        }
    
    def generate_template_documentation(self) -> str:
        """Generate documentation for supported and unsupported variant templates."""
        docs = []
        
        docs.append("# Genomics Automation - Variant Type Support\n")
        
        docs.append("## Supported Variant Types (Automated Processing)\n")
        for template in self.vcf_builder.get_supported_templates():
            docs.append(f"- **{template.variant_type.value.title()}**: {template.description}")
            docs.append(f"  - Pattern: {template.pattern}")
            docs.append(f"  - Status: ✅ Fully automated\n")
        
        docs.append("## Unsupported Variant Types (Manual Coordinates Required)\n")
        for template in self.vcf_builder.get_unsupported_templates():
            docs.append(f"- **{template.variant_type.value.title()}**: {template.description}")
            docs.append(f"  - Pattern: {template.pattern}")
            docs.append(f"  - Status: ⚠️ Requires user-provided coordinates/breakpoints")
            docs.append(f"  - Reason: Manual intervention needed for accurate coordinate determination\n")
        
        docs.append("## Usage Notes\n")
        docs.append("- Supported variants will be automatically processed through the TransVar → VCF pipeline")
        docs.append("- Unsupported variants will be flagged and require manual coordinate specification")
        docs.append("- The pipeline preserves all input data and provides detailed logs for manual processing")
        
        return "\n".join(docs)
