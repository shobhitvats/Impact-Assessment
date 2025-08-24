#!/usr/bin/env python3
"""
Enhanced JSON to CSV converter with protein change and preferred transcript support.
Production-ready version of the JSON to CSV converter.
"""

import json
import csv
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Any

# Import our transcript selector
sys.path.append(str(Path(__file__).parent.parent))
from genomics_automation.transcript_config import default_transcript_selector


def extract_protein_change(hgvsp: str) -> str:
    """
    Extract clean protein change from HGVS protein notation.
    
    Args:
        hgvsp: HGVS protein notation (e.g., "NP_000123.1:p.Arg123Gln")
    
    Returns:
        Clean protein change (e.g., "p.Arg123Gln")
    """
    if not hgvsp:
        return ""
    
    # Handle different formats
    if ':' in hgvsp:
        # Format: "NP_000123.1:p.Arg123Gln"
        protein_part = hgvsp.split(':')[-1]
    else:
        # Format: "p.Arg123Gln"
        protein_part = hgvsp
    
    # Clean up the protein change
    protein_part = protein_part.strip()
    
    # Ensure it starts with 'p.' if it doesn't already
    if protein_part and not protein_part.startswith('p.'):
        if protein_part.startswith('(') and protein_part.endswith(')'):
            # Handle format like "(p.Arg123Gln)"
            protein_part = protein_part[1:-1]
        if not protein_part.startswith('p.'):
            protein_part = f"p.{protein_part}"
    
    return protein_part


def analyze_transcript_preference(transcript: str, gene: str = None) -> tuple[str, str]:
    """
    Analyze transcript preference using the transcript selector.
    
    Args:
        transcript: Transcript identifier
        gene: Optional gene name
    
    Returns:
        Tuple of (preferred_status, reason)
    """
    if not transcript:
        return "Unknown", "No transcript provided"
    
    is_preferred, reason = default_transcript_selector.is_preferred_transcript(transcript, gene)
    
    if is_preferred:
        return "Yes", reason
    else:
        return "No", reason


def convert_tps_json_to_csv(input_json: str, output_csv: str, 
                           include_preference_details: bool = True) -> None:
    """
    Convert TPS JSON output to enhanced CSV format with protein changes 
    and preferred transcript analysis.
    
    Args:
        input_json: Path to input JSON file
        output_csv: Path to output CSV file
        include_preference_details: Whether to include detailed preference analysis
    """
    
    with open(input_json, 'r') as f:
        data = json.load(f)
    
    variants = data.get('variants', [])
    
    # Define enhanced CSV columns
    fieldnames = [
        'variant_id',
        'gene', 
        'transcript', 
        'preferred_transcript',
        'transcript_preference_reason',
        'hgvsc', 
        'hgvsp', 
        'protein_change',
        'variant_type',
        'clinical_significance', 
        'evidence', 
        'acmg_criteria', 
        'confidence',
        'gnomad_af', 
        'gnomad_ac', 
        'gnomad_an',
        'sift_score', 
        'sift_prediction', 
        'polyphen_score', 
        'polyphen_prediction',
        'cadd_phred', 
        'diseases', 
        'therapeutic_implications'
    ]
    
    # If preference details are not needed, remove the reason column
    if not include_preference_details:
        fieldnames.remove('transcript_preference_reason')
    
    with open(output_csv, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for variant in variants:
            # Extract basic variant information
            gene = variant.get('gene', '')
            transcript = variant.get('transcript', '')
            hgvsp = variant.get('hgvsp', '')
            
            # Extract protein change
            protein_change = extract_protein_change(hgvsp)
            
            # Analyze transcript preference
            preferred_status, preference_reason = analyze_transcript_preference(transcript, gene)
            
            # Extract nested data structures
            clinical_sig = variant.get('clinicalSignificance', {})
            pop_freq = variant.get('populationFrequency', {}).get('gnomad', {})
            func_pred = variant.get('functionalPredictions', {})
            
            # Format complex fields
            diseases = '; '.join([
                f"{d['disease']} ({d.get('omim', 'N/A')})" 
                for d in variant.get('diseaseAssociations', [])
            ])
            
            therapies = '; '.join([
                f"{t['drug']} ({t['responseType']})" 
                for t in variant.get('therapeuticImplications', [])
            ])
            
            # Build the row
            row = {
                'variant_id': variant.get('variant', ''),
                'gene': gene,
                'transcript': transcript,
                'preferred_transcript': preferred_status,
                'hgvsc': variant.get('hgvsc', ''),
                'hgvsp': hgvsp,
                'protein_change': protein_change,
                'variant_type': variant.get('variantType', ''),
                'clinical_significance': clinical_sig.get('classification', ''),
                'evidence': clinical_sig.get('evidence', ''),
                'acmg_criteria': ', '.join(clinical_sig.get('acmgCriteria', [])),
                'confidence': clinical_sig.get('confidence', ''),
                'gnomad_af': pop_freq.get('af', ''),
                'gnomad_ac': pop_freq.get('ac', ''),
                'gnomad_an': pop_freq.get('an', ''),
                'sift_score': func_pred.get('sift', {}).get('score', ''),
                'sift_prediction': func_pred.get('sift', {}).get('prediction', ''),
                'polyphen_score': func_pred.get('polyphen', {}).get('score', ''),
                'polyphen_prediction': func_pred.get('polyphen', {}).get('prediction', ''),
                'cadd_phred': func_pred.get('cadd', {}).get('phred', ''),
                'diseases': diseases,
                'therapeutic_implications': therapies
            }
            
            # Add preference reason if requested
            if include_preference_details:
                row['transcript_preference_reason'] = preference_reason
            
            writer.writerow(row)
    
    print(f"✅ Converted {len(variants)} variants from {input_json} to {output_csv}")
    
    # Print summary of transcript preferences
    preferred_count = sum(1 for v in variants 
                         if analyze_transcript_preference(v.get('transcript'), v.get('gene'))[0] == "Yes")
    
    print(f"📊 Transcript Analysis: {preferred_count}/{len(variants)} variants use preferred transcripts")


def main():
    """Main entry point for the converter."""
    parser = argparse.ArgumentParser(
        description='Convert TPS JSON to enhanced CSV with protein changes and transcript preferences',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python enhanced_json_to_csv.py input.json output.csv
  python enhanced_json_to_csv.py input.json output.csv --no-preference-details
        """
    )
    
    parser.add_argument('input_json', help='Input JSON file from TPS')
    parser.add_argument('output_csv', help='Output CSV file')
    parser.add_argument('--no-preference-details', action='store_true',
                       help='Exclude detailed transcript preference reasons from output')
    
    args = parser.parse_args()
    
    # Validate input file
    if not Path(args.input_json).exists():
        print(f"❌ Error: Input file {args.input_json} not found", file=sys.stderr)
        sys.exit(1)
    
    # Create output directory if needed
    output_path = Path(args.output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        convert_tps_json_to_csv(
            args.input_json, 
            args.output_csv, 
            include_preference_details=not args.no_preference_details
        )
        print(f"🎉 Conversion completed successfully!")
        
    except Exception as e:
        print(f"❌ Error during conversion: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
