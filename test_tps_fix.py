#!/usr/bin/env python3
"""
Test TPS processing with the fixed configuration
"""
import os
import sys
from pathlib import Path

# Set up environment
os.environ.update({
    'GENOMICS_TRANSVAR_EXECUTABLE': 'transvar',
    'GENOMICS_SARJ_SCRIPT': '/workspaces/Impact-Assessment/external_tools/mock_nirvana_junior.sh',
    'GENOMICS_TPS_EXECUTABLE': '/workspaces/Impact-Assessment/external_tools/mock_tps.sh',
    'GENOMICS_NIRVANA_EXECUTABLE': '/workspaces/Impact-Assessment/external_tools/mock_tps.sh',
    'GENOMICS_JSON_TO_CSV_SCRIPT': '/workspaces/Impact-Assessment/external_tools/mock_json_to_csv.py',
    'GENOMICS_OUTPUT_DIR': '/workspaces/Impact-Assessment/test_output',
    'GENOMICS_KB_COSMIC': 'cosmic',
    'GENOMICS_KB_CLINVAR': 'clinvar',
})

sys.path.insert(0, '/workspaces/Impact-Assessment')

def test_tps_processing():
    """Test TPS processing with the fixed configuration"""
    try:
        from genomics_automation.config import Config
        from genomics_automation.tps_runner import TPSRunner
        
        print("🧪 Testing TPS Processing...")
        
        # Create config and TPS runner
        config = Config()
        tps_runner = TPSRunner(config)
        
        print(f"✅ TPS Path: {config.paths.tps_path}")
        print(f"✅ Nirvana Path: {config.paths.nirvana_path}")
        print(f"✅ Knowledge Bases: {len(config.paths.knowledge_bases)}")
        
        # Validate setup
        is_valid, error_msg = tps_runner.validate_setup()
        if not is_valid:
            print(f"❌ Setup validation failed: {error_msg}")
            return False
        
        print("✅ TPS runner setup is valid")
        print(f"✅ Available knowledge bases:")
        for kb in config.paths.knowledge_bases:
            print(f"   - {kb.version}: {kb.path}")
        
        # Test command building
        input_sarj = Path("/tmp/test.json")
        output_json = Path("/tmp/test_tps.json")
        kb_spec = config.paths.knowledge_bases[0]
        
        cmd = tps_runner.build_tps_command(input_sarj, kb_spec, output_json)
        print(f"✅ TPS command built: {' '.join(cmd)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("🚀 TPS Processing Fix Test")
    print("=" * 40)
    
    if test_tps_processing():
        print("\n🎉 TPS processing test PASSED!")
        print("✅ The TPS configuration fix is working correctly")
    else:
        print("\n❌ TPS processing test FAILED!")
        print("⚠️ Please check the configuration")
    
if __name__ == "__main__":
    main()
