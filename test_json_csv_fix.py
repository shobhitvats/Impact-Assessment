#!/usr/bin/env python3
"""
Test JSON to CSV conversion fix
"""

import json
import tempfile
from pathlib import Path
import sys
import os

# Add the project root to Python path
sys.path.insert(0, '/workspaces/Impact-Assessment')

from genomics_automation.config import Config
from genomics_automation.json_to_csv import JSONToCSVConverter

def create_test_json():
    """Create a test JSON file with TPS-like output"""
    test_data = {
        "metadata": {
            "timestamp": "2025-08-23T13:13:36",
            "knowledge_base": "cosmic",
            "total_variants": 2
        },
        "variants": [
            {
                "variant": "chr17:g.43044295G>A",
                "gene": "BRCA1",
                "transcript": "NM_007294.4",
                "hgvsc": "c.68G>A",
                "hgvsp": "p.Cys23Tyr",
                "variantType": "missense",
                "clinicalSignificance": {
                    "classification": "Pathogenic",
                    "evidence": "Strong",
                    "acmgCriteria": ["PM1", "PP3", "PS3"],
                    "confidence": "High"
                },
                "populationFrequency": {
                    "gnomad": {"af": 0.0001, "ac": 12, "an": 125568}
                },
                "functionalPredictions": {
                    "sift": {"score": 0.01, "prediction": "Deleterious"},
                    "polyphen": {"score": 0.99, "prediction": "Probably damaging"},
                    "cadd": {"phred": 28.5}
                },
                "diseaseAssociations": [
                    {"disease": "Breast cancer", "omim": "114480"},
                    {"disease": "Ovarian cancer", "omim": "167000"}
                ],
                "therapeuticImplications": [
                    {"drug": "Olaparib", "responseType": "Sensitive"},
                    {"drug": "Cisplatin", "responseType": "Sensitive"}
                ]
            },
            {
                "variant": "chr13:g.32379913G>T",
                "gene": "BRCA2",
                "transcript": "NM_000059.4",
                "hgvsc": "c.1813G>T",
                "hgvsp": "p.Glu605Ter",
                "variantType": "nonsense",
                "clinicalSignificance": {
                    "classification": "Pathogenic",
                    "evidence": "Very Strong",
                    "acmgCriteria": ["PVS1", "PM2"],
                    "confidence": "Very High"
                },
                "populationFrequency": {
                    "gnomad": {"af": 0.0, "ac": 0, "an": 125568}
                },
                "functionalPredictions": {
                    "sift": {"score": None, "prediction": "N/A"},
                    "polyphen": {"score": None, "prediction": "N/A"},
                    "cadd": {"phred": 35.2}
                },
                "diseaseAssociations": [
                    {"disease": "Breast cancer", "omim": "114480"},
                    {"disease": "Ovarian cancer", "omim": "167000"}
                ],
                "therapeuticImplications": [
                    {"drug": "Olaparib", "responseType": "Sensitive"},
                    {"drug": "Rucaparib", "responseType": "Sensitive"}
                ]
            }
        ]
    }
    
    # Create temporary JSON file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(test_data, f, indent=2)
        return Path(f.name)

def test_json_to_csv_conversion():
    """Test the JSON to CSV conversion with the fixed command format"""
    print("🧪 Testing JSON to CSV conversion fix...")
    
    # Load environment
    os.system("source /workspaces/Impact-Assessment/.env.example")
    
    # Create config
    config = Config()
    print(f"✅ Using JSON to CSV script: {config.paths.json_to_csv_script}")
    
    # Create converter
    converter = JSONToCSVConverter(config)
    
    # Validate setup
    is_valid, error_msg = converter.validate_setup()
    if not is_valid:
        print(f"❌ Setup validation failed: {error_msg}")
        return False
    
    print("✅ Converter setup validated")
    
    # Create test JSON
    test_json = create_test_json()
    print(f"✅ Created test JSON: {test_json}")
    
    try:
        # Test conversion
        result = converter.convert_json_to_csv(test_json)
        
        if result.success:
            print(f"✅ Conversion successful!")
            print(f"   Input: {result.input_json}")
            print(f"   Output: {result.output_csv}")
            print(f"   Records: {result.record_count}")
            print(f"   Time: {result.execution_time:.2f}s")
            print(f"   Command used: {result.command_used}")
            
            # Check if output file exists and has content
            if result.output_csv and result.output_csv.exists():
                size = result.output_csv.stat().st_size
                print(f"   Output file size: {size} bytes")
                
                # Show first few lines
                with open(result.output_csv, 'r') as f:
                    lines = f.readlines()[:5]
                    print(f"   First {len(lines)} lines:")
                    for i, line in enumerate(lines):
                        print(f"     {i+1}: {line.strip()}")
                
                return True
            else:
                print("❌ Output file was not created")
                return False
        else:
            print(f"❌ Conversion failed: {result.error_message}")
            if result.command_used:
                print(f"   Command: {result.command_used}")
            if result.stderr:
                print(f"   Error output: {result.stderr}")
            if result.stdout:
                print(f"   Standard output: {result.stdout}")
            return False
    
    finally:
        # Clean up test file
        if test_json.exists():
            test_json.unlink()
            print(f"🧹 Cleaned up test file: {test_json}")

if __name__ == "__main__":
    success = test_json_to_csv_conversion()
    if success:
        print("\n🎉 JSON to CSV conversion test PASSED!")
        sys.exit(0)
    else:
        print("\n❌ JSON to CSV conversion test FAILED!")
        sys.exit(1)
