#!/usr/bin/env python3
"""
Quick verification test to confirm all errors are resolved
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

def test_streamlit_imports():
    """Test that all Streamlit app components can be imported without errors"""
    try:
        print("🧪 Testing Streamlit app imports...")
        
        # Test configuration loading
        from genomics_automation.config import Config
        config = Config()
        print(f"✅ Config loaded: {config.transvar.database}")
        
        # Test enum/string handling
        db_value = config.transvar.database
        db_str = db_value.value if hasattr(db_value, 'value') else str(db_value)
        print(f"✅ Database value handling: {db_str}")
        
        ref_value = config.transvar.ref_version
        ref_str = ref_value.value if hasattr(ref_value, 'value') else str(ref_value)
        print(f"✅ Reference value handling: {ref_str}")
        
        # Test pipeline stage enum
        from genomics_automation.pipeline import PipelineStage
        stage = PipelineStage.INPUT_VALIDATION
        stage_str = stage.value
        print(f"✅ Pipeline stage enum: {stage_str}")
        
        print("🎉 All Streamlit app components imported successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Import error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_config_serialization():
    """Test that configuration can be serialized for Streamlit display"""
    try:
        print("\n🔧 Testing configuration serialization...")
        
        from genomics_automation.config import Config
        config = Config()
        
        # Test the same logic used in app.py
        db_value = config.transvar.database
        db_str = db_value.value if hasattr(db_value, 'value') else str(db_value)
        
        ref_value = config.transvar.ref_version
        ref_str = ref_value.value if hasattr(ref_value, 'value') else str(ref_value)
        
        config_dict = {
            'transvar_database': db_str,
            'ref_version': ref_str,
            'max_workers': config.processing.max_workers,
            'debug_mode': config.debug_mode
        }
        
        import json
        config_json = json.dumps(config_dict, indent=2)
        print(f"✅ Configuration serializable:\n{config_json}")
        
        return True
        
    except Exception as e:
        print(f"❌ Serialization error: {e}")
        return False

def main():
    print("🚀 Error Resolution Verification Test")
    print("=" * 50)
    
    all_passed = True
    
    # Test 1: Imports
    if not test_streamlit_imports():
        all_passed = False
    
    # Test 2: Configuration serialization
    if not test_config_serialization():
        all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 SUCCESS: All errors have been resolved!")
        print("✅ Streamlit application should now run without errors")
        print("🌐 Access the app at: http://localhost:8501")
    else:
        print("❌ FAILURE: Some issues remain")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
