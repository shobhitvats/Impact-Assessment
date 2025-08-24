#!/usr/bin/env python3
"""
Quick functional test to verify the pipeline components work
"""
import os
import sys

# Set up environment
os.environ.update({
    'GENOMICS_TRANSVAR_EXECUTABLE': 'transvar',
    'GENOMICS_SARJ_SCRIPT': '/workspaces/Impact-Assessment/external_tools/mock_nirvana_junior.sh',
    'GENOMICS_TPS_EXECUTABLE': '/workspaces/Impact-Assessment/external_tools/mock_tps.sh',
    'GENOMICS_JSON_TO_CSV_SCRIPT': '/workspaces/Impact-Assessment/external_tools/mock_json_to_csv.py',
})

sys.path.insert(0, '/workspaces/Impact-Assessment')

try:
    from genomics_automation.config import Config
    from genomics_automation.transvar_adapter import TransVarAdapter
    
    print("🧪 Testing updated components...")
    
    # Test configuration
    config = Config()
    print(f"✅ Config loaded: {config.transvar.database}")
    
    # Test TransVar adapter
    adapter = TransVarAdapter(config.transvar)
    
    # Test the cleaning method
    test_variant = "NM_000051.3:c.1521_1523delCTT"
    cleaned = adapter.clean_protein_notation(test_variant)
    print(f"✅ Variant cleaning works: {test_variant} -> {cleaned}")
    
    # Test command building
    cmd = adapter.build_transvar_command("p.Leu507Phe", "NM_000051.3")
    print(f"✅ Command building works: {' '.join(cmd)}")
    
    print("🎉 All components working correctly!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
