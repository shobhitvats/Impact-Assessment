"""
Tests for TransVar adapter functionality.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import subprocess

from genomics_automation.transvar_adapter import (
    TransVarAdapter,
    TransVarResult,
    ProteinNotationCleaner,
    CoordinateParser,
    VCFBuilder,
    convert_to_vcf_with_detailed_logs
)
from genomics_automation.config import Config


class TestProteinNotationCleaner:
    """Test protein notation cleaning functionality."""
    
    def test_three_letter_to_one_letter_conversion(self):
        """Test amino acid conversion."""
        cleaner = ProteinNotationCleaner()
        
        test_cases = [
            ("p.Ala123Thr", "p.A123T"),
            ("p.Val600Glu", "p.V600E"),
            ("p.Arg273His", "p.R273H"),
            ("p.Leu858Arg", "p.L858R")
        ]
        
        for input_notation, expected in test_cases:
            result = cleaner.clean_protein_notation(input_notation)
            assert result == expected
    
    def test_frameshift_normalization(self):
        """Test frameshift notation normalization."""
        cleaner = ProteinNotationCleaner()
        
        test_cases = [
            ("p.Gln61fs*10", "p.Q61fs"),
            ("p.Lys123frameshift", "p.K123fs"),
            ("p.Met1fs", "p.M1fs")
        ]
        
        for input_notation, expected in test_cases:
            result = cleaner.clean_protein_notation(input_notation)
            assert result == expected
    
    def test_parentheses_removal(self):
        """Test parentheses and whitespace removal."""
        cleaner = ProteinNotationCleaner()
        
        test_cases = [
            ("p.(Ala123Thr)", "p.A123T"),
            ("p. Val600Glu ", "p.V600E"),
            ("p.( Arg273His )", "p.R273H")
        ]
        
        for input_notation, expected in test_cases:
            result = cleaner.clean_protein_notation(input_notation)
            assert result == expected


class TestCoordinateParser:
    """Test coordinate parsing functionality."""
    
    def test_genomic_coordinate_parsing(self):
        """Test parsing of genomic coordinates."""
        parser = CoordinateParser()
        
        transvar_output = "chr7:g.140453136A>T"
        coordinates = parser.parse_coordinates(transvar_output)
        
        assert coordinates['chrom'] == 'chr7'
        assert coordinates['pos'] == '140453136'
        assert coordinates['change'] == 'A>T'
        assert coordinates['type'] == 'genomic'
    
    def test_coding_coordinate_parsing(self):
        """Test parsing of coding coordinates."""
        parser = CoordinateParser()
        
        transvar_output = "NM_004333.4:c.1799T>A"
        coordinates = parser.parse_coordinates(transvar_output)
        
        assert coordinates['c_pos'] == '1799'
        assert coordinates['c_change'] == 'T>A'
    
    def test_protein_coordinate_parsing(self):
        """Test parsing of protein coordinates."""
        parser = CoordinateParser()
        
        transvar_output = "NP_004324.2:p.V600E"
        coordinates = parser.parse_coordinates(transvar_output)
        
        assert coordinates['p_change'] == 'V600E'
    
    def test_coordinate_validation(self):
        """Test coordinate validation."""
        parser = CoordinateParser()
        
        # Valid coordinates
        valid_coords = {'chrom': 'chr7', 'pos': '140453136', 'change': 'A>T'}
        is_valid, error_msg = parser.validate_coordinates(valid_coords)
        assert is_valid
        assert error_msg == ""
        
        # Missing coordinates
        empty_coords = {}
        is_valid, error_msg = parser.validate_coordinates(empty_coords)
        assert not is_valid
        assert "No coordinates found" in error_msg
        
        # Invalid position
        invalid_coords = {'chrom': 'chr7', 'pos': 'invalid', 'change': 'A>T'}
        is_valid, error_msg = parser.validate_coordinates(invalid_coords)
        assert not is_valid
        assert "Invalid position" in error_msg


class TestVCFBuilder:
    """Test VCF building functionality."""
    
    def test_vcf_header_generation(self):
        """Test VCF header generation."""
        builder = VCFBuilder()
        header = builder.build_vcf_header()
        
        assert "##fileformat=VCFv4.2" in header
        assert "##source=GenomicsAutomationPipeline" in header
        assert "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO" in header
    
    def test_vcf_line_building(self):
        """Test VCF line building from TransVar result."""
        builder = VCFBuilder()
        
        # Create mock TransVar result
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
        
        vcf_line = builder.build_vcf_line(result)
        
        assert vcf_line is not None
        assert "chr7\t140453136" in vcf_line
        assert "GENE=BRAF" in vcf_line
        assert "PROTEIN=p.V600E" in vcf_line
    
    def test_change_notation_parsing(self):
        """Test parsing of change notation."""
        builder = VCFBuilder()
        
        # Substitution
        ref, alt = builder._parse_change_notation("A>T")
        assert ref == "A"
        assert alt == "T"
        
        # Deletion
        ref, alt = builder._parse_change_notation("delA")
        assert ref == "A"
        assert alt == "."
        
        # Insertion
        ref, alt = builder._parse_change_notation("insG")
        assert ref == "."
        assert alt == "G"


class TestTransVarAdapter:
    """Test TransVar adapter functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = Config()
        self.adapter = TransVarAdapter(self.config)
    
    def test_command_building(self):
        """Test TransVar command construction."""
        self.setUp()
        
        cmd = self.adapter.build_transvar_command("p.V600E", "NM_004333.4")
        
        assert "transvar" in cmd
        assert "panno" in cmd
        assert "NM_004333.4:p.V600E" in cmd
        assert any("--refseq" in str(flag) or "--ucsc" in str(flag) or "--ensembl" in str(flag) for flag in cmd)
    
    @patch('genomics_automation.transvar_adapter.subprocess.run')
    def test_successful_transvar_run(self, mock_run):
        """Test successful TransVar execution."""
        self.setUp()
        
        # Mock successful subprocess run
        mock_result = Mock()
        mock_result.stdout = "chr7:g.140453136A>T\tNM_004333.4:c.1799T>A\tNP_004324.2:p.V600E"
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        result = self.adapter.run_transvar_panno("BRAF", "p.V600E")
        
        assert result.success
        assert result.gene == "BRAF"
        assert result.protein_change == "p.V600E"
        assert result.coordinates is not None
    
    @patch('genomics_automation.transvar_adapter.subprocess.run')
    def test_failed_transvar_run(self, mock_run):
        """Test failed TransVar execution."""
        self.setUp()
        
        # Mock failed subprocess run
        mock_run.side_effect = subprocess.CalledProcessError(1, "transvar", stderr="Error message")
        
        result = self.adapter.run_transvar_panno("INVALID", "p.Invalid")
        
        assert not result.success
        assert "TransVar error" in result.error_message
    
    @patch('genomics_automation.transvar_adapter.subprocess.run')
    def test_batch_processing(self, mock_run):
        """Test batch processing of variants."""
        self.setUp()
        
        # Mock successful subprocess runs
        mock_result = Mock()
        mock_result.stdout = "chr7:g.140453136A>T\tNM_004333.4:c.1799T>A\tNP_004324.2:p.V600E"
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        variants = [
            {"gene": "BRAF", "protein_change": "p.V600E"},
            {"gene": "TP53", "protein_change": "p.R273H"}
        ]
        
        results, metrics = self.adapter.process_batch(variants)
        
        assert len(results) == 2
        assert metrics['total'] == 2
        assert metrics['successful'] == 2
        assert metrics['failed'] == 0


class TestVCFConversion:
    """Test VCF conversion functionality."""
    
    def test_vcf_conversion_with_logs(self, tmp_path):
        """Test VCF conversion with detailed logging."""
        output_path = tmp_path / "test.vcf"
        
        # Create mock TransVar results
        results = [
            TransVarResult(
                gene="BRAF",
                transcript="NM_004333.4",
                protein_change="p.V600E",
                original_input="BRAF:p.V600E",
                success=True,
                vcf_line="chr7\t140453136\t.\tA\tT\t.\t.\tGENE=BRAF;PROTEIN=p.V600E",
                coordinates={'chrom': 'chr7', 'pos': '140453136', 'change': 'A>T'}
            ),
            TransVarResult(
                gene="INVALID",
                transcript="",
                protein_change="p.Invalid",
                original_input="INVALID:p.Invalid",
                success=False,
                error_message="Invalid coordinates"
            )
        ]
        
        stats = convert_to_vcf_with_detailed_logs(results, output_path, log_failures=True)
        
        assert stats['total_variants'] == 2
        assert stats['successful_conversions'] == 1
        assert stats['failed_conversions'] == 1
        assert stats['success_rate'] == 0.5
        assert output_path.exists()
        
        # Check VCF file content
        with open(output_path, 'r') as f:
            content = f.read()
            assert "##fileformat=VCFv4.2" in content
            assert "chr7\t140453136" in content
        
        # Check failure analysis
        failure_analysis = stats['failure_analysis']
        assert 'failure_types' in failure_analysis
        assert 'recommendations' in failure_analysis


if __name__ == "__main__":
    pytest.main([__file__])
