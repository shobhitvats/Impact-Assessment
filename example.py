#!/usr/bin/env python3
"""
Example script demonstrating the Genomics Automation Pipeline usage.

This script shows how to use the pipeline programmatically without the Streamlit UI.
"""

import sys
from pathlib import Path
from genomics_automation.config import Config, KBSpec
from genomics_automation.pipeline import run_full_pipeline


def example_variant_processing():
    """Example: Process a list of variants through the full pipeline."""
    
    print("🧬 Genomics Automation Pipeline - Example Usage")
    print("=" * 60)
    
    # Example variants
    variants = [
        {"gene": "BRAF", "protein_change": "p.V600E"},
        {"gene": "TP53", "protein_change": "p.R273H"},
        {"gene": "EGFR", "protein_change": "p.L858R"},
        {"gene": "KRAS", "protein_change": "p.G12D"}
    ]
    
    print(f"Processing {len(variants)} variants:")
    for variant in variants:
        print(f"  - {variant['gene']}: {variant['protein_change']}")
    
    # Configure the pipeline
    config = Config()
    
    # Note: In a real setup, you would configure actual tool paths
    print("\n⚠️  Configuration Note:")
    print("This example uses default configuration. For actual usage, configure:")
    print("  - TransVar installation and database")
    print("  - Nirvana Junior script path")
    print("  - TPS and Nirvana executable paths")
    print("  - Knowledge base configurations")
    print("  - JSON to CSV converter script")
    
    # Example knowledge bases (would be real paths in production)
    config.paths.knowledge_bases = [
        KBSpec(
            version="2023.1",
            path="/path/to/kb/2023.1/",
            description="Primary Knowledge Base"
        ),
        KBSpec(
            version="2023.2", 
            path="/path/to/kb/2023.2/",
            description="Updated Knowledge Base"
        )
    ]
    
    # Set up output directory
    output_dir = Path("./example_output")
    output_dir.mkdir(exist_ok=True)
    
    print(f"\n📁 Output directory: {output_dir.absolute()}")
    
    # For demonstration, we'll only run the TransVar stage
    config.stages.run_sarj = False
    config.stages.run_tps = False  
    config.stages.run_json_conversion = False
    config.stages.run_report_extraction = False
    
    print("\n🚀 Running pipeline (TransVar and VCF generation only for demo)...")
    
    try:
        # Run the pipeline
        result = run_full_pipeline(
            inputs=variants,
            config=config,
            output_dir=output_dir
        )
        
        # Display results
        print("\n📊 Pipeline Results:")
        print(f"  Success: {result.success}")
        print(f"  Run ID: {result.run_id}")
        print(f"  Execution Time: {result.execution_time:.2f} seconds")
        print(f"  Stages Completed: {len(result.stages_completed)}")
        
        if result.artifacts:
            print("\n📁 Generated Artifacts:")
            for artifact_name, artifact_path in result.artifacts.items():
                if artifact_path and Path(artifact_path).exists():
                    file_size = Path(artifact_path).stat().st_size
                    print(f"  - {artifact_name}: {artifact_path} ({file_size} bytes)")
        
        if result.errors:
            print("\n❌ Errors:")
            for error in result.errors:
                print(f"  - {error}")
        
        print(f"\n✅ Results saved to: {result.run_directory}")
        
    except Exception as e:
        print(f"\n❌ Pipeline failed with error: {e}")
        return False
    
    return True


def example_csv_processing():
    """Example: Process a CSV file through the pipeline."""
    
    print("\n" + "=" * 60)
    print("📄 CSV Processing Example")
    print("=" * 60)
    
    # Create example CSV file
    csv_content = """gene,protein_change,transcript
BRAF,p.V600E,NM_004333.4
TP53,p.R273H,NM_000546.5
EGFR,p.L858R,NM_005228.5
KRAS,p.G12D,NM_033360.3
"""
    
    csv_path = Path("./example_variants.csv")
    with open(csv_path, 'w') as f:
        f.write(csv_content)
    
    print(f"Created example CSV: {csv_path.absolute()}")
    
    # Process CSV through pipeline
    config = Config()
    config.stages.run_sarj = False
    config.stages.run_tps = False
    config.stages.run_json_conversion = False
    config.stages.run_report_extraction = False
    
    output_dir = Path("./csv_example_output")
    output_dir.mkdir(exist_ok=True)
    
    print(f"Processing CSV through pipeline...")
    
    try:
        result = run_full_pipeline(
            inputs=csv_path,
            config=config,
            output_dir=output_dir
        )
        
        print(f"CSV processing {'succeeded' if result.success else 'failed'}")
        print(f"Results in: {result.run_directory}")
        
        # Clean up
        csv_path.unlink()
        
    except Exception as e:
        print(f"CSV processing failed: {e}")
        # Clean up
        if csv_path.exists():
            csv_path.unlink()


def example_configuration():
    """Example: Demonstrate configuration options."""
    
    print("\n" + "=" * 60)
    print("⚙️  Configuration Example")
    print("=" * 60)
    
    # Create a custom configuration
    config = Config()
    
    # TransVar settings
    config.transvar.database = "refseq"
    config.transvar.ref_version = "hg38"
    config.transvar.use_ccds = True
    config.transvar.reference_file = "/path/to/reference.fasta"
    
    # Processing settings
    config.processing.max_workers = 4
    config.processing.timeout_seconds = 300
    
    # Pipeline stages
    config.stages.run_transvar = True
    config.stages.run_sarj = True
    config.stages.run_tps = True
    config.stages.run_json_conversion = True
    config.stages.run_report_extraction = True
    
    # Tool paths (example)
    config.paths.junior_script_path = "/usr/local/bin/nirvana_junior.sh"
    config.paths.tps_path = "/usr/local/bin/tps"
    config.paths.nirvana_path = "/usr/local/bin/nirvana"
    config.paths.json_to_csv_script = "/usr/local/bin/json_to_csv.py"
    
    # Knowledge bases
    config.paths.knowledge_bases = [
        KBSpec(
            version="ClinVar_2023.1",
            path="/data/knowledgebases/clinvar/2023.1/",
            description="ClinVar 2023.1 Release"
        ),
        KBSpec(
            version="OncoKB_2023.2",
            path="/data/knowledgebases/oncokb/2023.2/",
            description="OncoKB 2023.2 Release"
        )
    ]
    
    print("Configuration created with:")
    print(f"  TransVar Database: {config.transvar.database}")
    print(f"  Reference Version: {config.transvar.ref_version}")
    print(f"  Max Workers: {config.processing.max_workers}")
    print(f"  Knowledge Bases: {len(config.paths.knowledge_bases)}")
    
    # Get TransVar flags
    flags = config.get_transvar_flags()
    print(f"  TransVar Flags: {' '.join(flags)}")
    
    # Environment variable example
    print("\nEnvironment variable equivalents:")
    print("  export GENOMICS_TRANSVAR_DATABASE=refseq")
    print("  export GENOMICS_TRANSVAR_REF_VERSION=hg38")
    print("  export GENOMICS_PROCESSING_MAX_WORKERS=4")


def main():
    """Main example function."""
    
    print("🧬 Welcome to the Genomics Automation Pipeline Examples!")
    print("\nThis script demonstrates various ways to use the pipeline.")
    print("For the full interactive experience, run: streamlit run app.py")
    
    # Run examples
    try:
        # Configuration example
        example_configuration()
        
        # Variant processing example  
        success = example_variant_processing()
        
        if success:
            # CSV processing example
            example_csv_processing()
        
        print("\n" + "=" * 60)
        print("✅ Examples completed!")
        print("\nNext steps:")
        print("1. Install and configure external tools (TransVar, Nirvana, etc.)")
        print("2. Update configuration with actual tool paths")
        print("3. Run the full Streamlit UI: streamlit run app.py")
        print("4. Or use the pipeline programmatically as shown in these examples")
        
    except ImportError as e:
        print(f"\n❌ Import error: {e}")
        print("Please install dependencies: pip install -r requirements.txt")
        sys.exit(1)
    
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
