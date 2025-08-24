"""
Tests for VCF builder functionality.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock

from genomics_automation.vcf_builder import (
    VariantClassifier,
    VariantType,
    EnhancedVCFBuilder,
    BatchVCFProcessor,
    VariantTemplate
)
from genomics_automation.transvar_adapter import TransVarResult


class TestVariantClassifier:
    """Test variant classification functionality."""
    
    def test_substitution_classification(self):
        """Test classification of substitution variants."""
        classifier = VariantClassifier()
        
        test_cases = [
            "p.V600E",
            "p.A123T",
            "c.123A>T",
            "g.123A>T"
        ]
        
        for notation in test_cases:
            variant_type = classifier.classify_variant(notation)
            assert variant_type == VariantType.SUBSTITUTION
    
    def test_deletion_classification(self):
        """Test classification of deletion variants."""
        classifier = VariantClassifier()
        
        test_cases = [
            "p.A123del",
            "c.123delA",
            "g.123delAT"
        ]
        
        for notation in test_cases:
            variant_type = classifier.classify_variant(notation)
            assert variant_type == VariantType.DELETION
    
    def test_insertion_classification(self):
        """Test classification of insertion variants."""
        classifier = VariantClassifier()
        
        test_cases = [
            "p.A123_T124insV",
            "c.123_124insA",
            "g.123_124insATCG"
        ]
        
        for notation in test_cases:
            variant_type = classifier.classify_variant(notation)
            assert variant_type == VariantType.INSERTION
    
    def test_cnv_classification(self):
        """Test classification of CNV variants."""
        classifier = VariantClassifier()
        
        gain_cases = ["gain", "amplification", "duplication"]
        loss_cases = ["loss", "deletion", "del"]
        
        for notation in gain_cases:
            variant_type = classifier.classify_variant(notation)
            assert variant_type == VariantType.CNV_GAIN
        
        for notation in loss_cases:
            variant_type = classifier.classify_variant(notation)
            assert variant_type == VariantType.CNV_LOSS
    
    def test_splice_classification(self):
        """Test classification of splice variants."""
        classifier = VariantClassifier()
        
        test_cases = [
            "splice site mutation",
            "exon 5 skipping",
            "intron variant"
        ]
        
        for notation in test_cases:
            variant_type = classifier.classify_variant(notation)
            assert variant_type == VariantType.SPLICE
    
    def test_fusion_classification(self):
        """Test classification of fusion variants."""
        classifier = VariantClassifier()
        
        rna_cases = ["rna fusion", "transcript fusion"]
        dna_cases = ["dna fusion", "chromosomal rearrangement"]
        
        for notation in rna_cases:
            variant_type = classifier.classify_variant(notation)
            assert variant_type == VariantType.RNA_FUSION
        
        for notation in dna_cases:
            variant_type = classifier.classify_variant(notation)
            assert variant_type == VariantType.DNA_FUSION
    
    def test_complex_classification(self):
        """Test classification of complex/unknown variants."""
        classifier = VariantClassifier()
        
        test_cases = [
            "unknown variant",
            "complex rearrangement",
            "novel mutation"
        ]
        
        for notation in test_cases:
            variant_type = classifier.classify_variant(notation)
            assert variant_type == VariantType.COMPLEX


class TestEnhancedVCFBuilder:
    """Test enhanced VCF builder functionality."""
    
    def test_template_management(self):
        """Test variant template management."""
        builder = EnhancedVCFBuilder()
        
        supported = builder.get_supported_templates()
        unsupported = builder.get_unsupported_templates()
        
        # Check that we have both supported and unsupported templates
        assert len(supported) > 0
        assert len(unsupported) > 0
        
        # Check template properties
        for template in supported:
            assert template.supported
            assert not template.requires_coordinates
        
        for template in unsupported:
            assert not template.supported
            assert template.requires_coordinates
    
    def test_enhanced_header_generation(self):
        """Test enhanced VCF header generation."""
        builder = EnhancedVCFBuilder()
        
        header = builder.build_enhanced_vcf_header(include_templates=True)
        
        assert "##fileformat=VCFv4.2" in header
        assert "##automationVersion=1.0.0" in header
        assert "##AUTOMATION_SCOPE=Small variants" in header
        assert "##AUTOMATION_EXCLUDED=CNV, splice" in header
        assert "VARIANT_TYPE" in header
        assert "AUTO_GENERATED" in header
    
    def test_enhanced_vcf_line_building(self):
        """Test enhanced VCF line building with classification."""
        builder = EnhancedVCFBuilder()
        
        result = TransVarResult(
            gene="BRAF",
            transcript="NM_004333.4",
            protein_change="p.V600E",
            original_input="BRAF:p.V600E",
            success=True,
            coordinates={
                'chrom': 'chr7',
                'pos': '140453136',
                'change': 'A>T'
            }
        )
        
        vcf_line = builder.build_enhanced_vcf_line(result, include_classification=True)
        
        assert vcf_line is not None
        assert "VARIANT_TYPE=substitution" in vcf_line
        assert "AUTO_GENERATED" in vcf_line
        assert "GENE=BRAF" in vcf_line


class TestBatchVCFProcessor:
    """Test batch VCF processing functionality."""
    
    def setUp(self, tmp_path):
        """Set up test fixtures."""
        self.output_dir = tmp_path / "vcf_output"
        self.output_dir.mkdir()
        self.processor = BatchVCFProcessor(self.output_dir)
    
    def test_supported_variant_processing(self, tmp_path):
        """Test processing of supported variants."""
        self.setUp(tmp_path)
        
        # Create mock results with supported variants
        results = [
            TransVarResult(
                gene="BRAF",
                transcript="NM_004333.4",
                protein_change="p.V600E",
                original_input="BRAF:p.V600E",
                success=True,
                coordinates={'chrom': 'chr7', 'pos': '140453136', 'change': 'A>T'}
            ),
            TransVarResult(
                gene="TP53",
                transcript="NM_000546.5",
                protein_change="p.R273H",
                original_input="TP53:p.R273H",
                success=True,
                coordinates={'chrom': 'chr17', 'pos': '7577120', 'change': 'G>A'}
            )
        ]
        
        stats = self.processor.process_transvar_results(results, "test_variants.vcf")
        
        assert stats['total_variants'] == 2
        assert stats['supported_variants'] == 2
        assert stats['unsupported_variants'] == 0
        
        # Check VCF file was created
        vcf_file = Path(stats['vcf_file'])
        assert vcf_file.exists()
        
        # Check VCF content
        with open(vcf_file, 'r') as f:
            content = f.read()
            assert "##fileformat=VCFv4.2" in content
            assert "chr7\t140453136" in content
            assert "chr17\t7577120" in content
    
    def test_unsupported_variant_processing(self, tmp_path):
        """Test processing of unsupported variants."""
        self.setUp(tmp_path)
        
        # Create mock results with unsupported variants
        results = [
            TransVarResult(
                gene="GENE1",
                transcript="",
                protein_change="CNV gain",
                original_input="GENE1:CNV gain",
                success=True,
                coordinates={}
            ),
            TransVarResult(
                gene="GENE2",
                transcript="",
                protein_change="splice site mutation",
                original_input="GENE2:splice site mutation",
                success=True,
                coordinates={}
            )
        ]
        
        stats = self.processor.process_transvar_results(results, "test_unsupported.vcf")
        
        assert stats['total_variants'] == 2
        assert stats['supported_variants'] == 0
        assert stats['unsupported_variants'] == 2
        
        # Check unsupported report was created
        unsupported_stats = stats['unsupported_statistics']
        assert unsupported_stats['count'] == 2
        assert 'cnv_gain' in unsupported_stats['types']
        assert 'splice' in unsupported_stats['types']
    
    def test_mixed_variant_processing(self, tmp_path):
        """Test processing of mixed supported/unsupported variants."""
        self.setUp(tmp_path)
        
        # Create mock results with mixed variants
        results = [
            TransVarResult(
                gene="BRAF",
                transcript="NM_004333.4",
                protein_change="p.V600E",
                original_input="BRAF:p.V600E",
                success=True,
                coordinates={'chrom': 'chr7', 'pos': '140453136', 'change': 'A>T'}
            ),
            TransVarResult(
                gene="GENE1",
                transcript="",
                protein_change="CNV gain",
                original_input="GENE1:CNV gain",
                success=True,
                coordinates={}
            )
        ]
        
        stats = self.processor.process_transvar_results(results, "test_mixed.vcf")
        
        assert stats['total_variants'] == 2
        assert stats['supported_variants'] == 1
        assert stats['unsupported_variants'] == 1
        
        # Check variant type counts
        type_counts = stats['variant_type_counts']
        assert 'substitution' in type_counts
        assert 'cnv_gain' in type_counts
    
    def test_template_documentation_generation(self, tmp_path):
        """Test template documentation generation."""
        self.setUp(tmp_path)
        
        docs = self.processor.generate_template_documentation()
        
        assert "# Genomics Automation - Variant Type Support" in docs
        assert "## Supported Variant Types" in docs
        assert "## Unsupported Variant Types" in docs
        assert "✅ Fully automated" in docs
        assert "⚠️ Requires user-provided coordinates" in docs
        assert "## Usage Notes" in docs


class TestVariantTemplate:
    """Test variant template functionality."""
    
    def test_template_creation(self):
        """Test variant template creation."""
        template = VariantTemplate(
            variant_type=VariantType.SUBSTITUTION,
            pattern="p.A123T",
            description="Single amino acid substitution",
            supported=True,
            requires_coordinates=False
        )
        
        assert template.variant_type == VariantType.SUBSTITUTION
        assert template.pattern == "p.A123T"
        assert template.description == "Single amino acid substitution"
        assert template.supported
        assert not template.requires_coordinates
    
    def test_unsupported_template(self):
        """Test unsupported variant template."""
        template = VariantTemplate(
            variant_type=VariantType.CNV_GAIN,
            pattern="CNV gain",
            description="Copy number gain - requires manual coordinates",
            supported=False,
            requires_coordinates=True
        )
        
        assert template.variant_type == VariantType.CNV_GAIN
        assert not template.supported
        assert template.requires_coordinates


if __name__ == "__main__":
    pytest.main([__file__])
