#!/usr/bin/env python3
"""
Test SARJ generation with the fixed command structure
"""
import os
import sys
import tempfile
from pathlib import Path

# Set up environment
os.environ.update({
    'GENOMICS_TRANSVAR_EXECUTABLE': 'transvar',
    'GENOMICS_SARJ_SCRIPT': '/workspaces/Impact-Assessment/external_tools/mock_nirvana_junior.sh',
    'GENOMICS_TPS_EXECUTABLE': '/workspaces/Impact-Assessment/external_tools/mock_tps.sh',
    'GENOMICS_JSON_TO_CSV_SCRIPT': '/workspaces/Impact-Assessment/external_tools/mock_json_to_csv.py',
    'GENOMICS_OUTPUT_DIR': '/workspaces/Impact-Assessment/test_output',
})

sys.path.insert(0, '/workspaces/Impact-Assessment')

def test_sarj_generation():
    """Test SARJ generation with the VCF file"""
    try:
        from genomics_automation.config import Config
        from genomics_automation.sarj_runner import SARJRunner
        
        print("🧪 Testing SARJ Generation...")
        
        # Create config and SARJ runner
        config = Config()
        sarj_runner = SARJRunner(config)
        
        # Validate setup
        is_valid, error_msg = sarj_runner.validate_setup()
        if not is_valid:
            print(f"❌ Setup validation failed: {error_msg}")
            return False
        
        print("✅ SARJ runner setup is valid")
        
        # Test with the batch_mutations.vcf file
        input_vcf = Path("/workspaces/Impact-Assessment/batch_mutations.vcf")
        
        if not input_vcf.exists():
            print(f"❌ Input VCF file not found: {input_vcf}")
            return False
        
        print(f"✅ Input VCF file found: {input_vcf}")
        
        # Create temporary output directory
        output_dir = Path("/workspaces/Impact-Assessment/test_output")
        output_dir.mkdir(exist_ok=True)
        
        # Run SARJ generation
        print("🔄 Running SARJ generation...")
        result = sarj_runner.run_sarj(input_vcf, output_dir)
        
        if result.success:
            print(f"✅ SARJ generation successful!")
            print(f"   Output file: {result.output_sarj}")
            print(f"   Execution time: {result.execution_time:.2f}s")
            print(f"   Command used: {result.command_used}")
            
            # Check if output file exists and has content
            if result.output_sarj and result.output_sarj.exists():
                file_size = result.output_sarj.stat().st_size
                print(f"   Output file size: {file_size} bytes")
                
                if file_size > 0:
                    print("✅ SARJ output file created successfully with content")
                    return True
                else:
                    print("❌ SARJ output file is empty")
                    return False
            else:
                print("❌ SARJ output file was not created")
                return False
        else:
            print(f"❌ SARJ generation failed: {result.error_message}")
            print(f"   Command used: {result.command_used}")
            if result.stdout:
                print(f"   Stdout: {result.stdout}")
            if result.stderr:
                print(f"   Stderr: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("🚀 SARJ Generation Fix Test")
    print("=" * 40)
    
    if test_sarj_generation():
        print("\n🎉 SARJ generation test PASSED!")
        print("✅ The SARJ generation fix is working correctly")
    else:
        print("\n❌ SARJ generation test FAILED!")
        print("⚠️ Please check the configuration and mock script")
    
if __name__ == "__main__":
    main()
