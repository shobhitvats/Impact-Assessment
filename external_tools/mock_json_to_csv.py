#!/usr/bin/env python3
"""
Mock JSON to CSV converter for demonstration
In production, this would be the actual converter script
"""

import json
import csv
import sys
import argparse

def convert_tps_json_to_csv(input_json, output_csv):
    """Convert TPS JSON output to CSV format"""
    
    with open(input_json, 'r') as f:
        data = json.load(f)
    
    variants = data.get('variants', [])
    
    # Define CSV columns
    fieldnames = [
        'variant_id', 'gene', 'transcript', 'preferred_transcript', 'hgvsc', 'hgvsp', 
        'protein_change', 'variant_type', 'clinical_significance', 'evidence', 
        'acmg_criteria', 'confidence', 'gnomad_af', 'gnomad_ac', 'gnomad_an',
        'sift_score', 'sift_prediction', 'polyphen_score', 'polyphen_prediction',
        'cadd_phred', 'diseases', 'therapeutic_implications'
    ]
    
    with open(output_csv, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for variant in variants:
            # Extract nested data
            clinical_sig = variant.get('clinicalSignificance', {})
            pop_freq = variant.get('populationFrequency', {}).get('gnomad', {})
            func_pred = variant.get('functionalPredictions', {})
            
            # Format diseases and therapies
            diseases = '; '.join([
                f"{d['disease']} ({d.get('omim', 'N/A')})" 
                for d in variant.get('diseaseAssociations', [])
            ])
            
            therapies = '; '.join([
                f"{t['drug']} ({t['responseType']})" 
                for t in variant.get('therapeuticImplications', [])
            ])
            
            # Extract protein change from hgvsp or create it
            hgvsp = variant.get('hgvsp', '')
            protein_change = ""
            if hgvsp:
                # Extract just the protein change part (e.g., "p.Arg123Gln" from "NP_000123.1:p.Arg123Gln")
                if ':' in hgvsp:
                    protein_change = hgvsp.split(':')[-1]
                else:
                    protein_change = hgvsp
            
            # Determine preferred transcript (in production this would come from database)
            transcript = variant.get('transcript', '')
            preferred_transcript = "Yes" if transcript and any(x in transcript.lower() for x in ['nm_', 'refseq', 'mane']) else "No"
            
            row = {
                'variant_id': variant.get('variant', ''),
                'gene': variant.get('gene', ''),
                'transcript': transcript,
                'preferred_transcript': preferred_transcript,
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
            
            writer.writerow(row)
    
    print(f"Converted {len(variants)} variants from {input_json} to {output_csv}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Convert TPS JSON to CSV')
    parser.add_argument('input_json', help='Input JSON file')
    parser.add_argument('output_csv', help='Output CSV file')
    
    args = parser.parse_args()
    convert_tps_json_to_csv(args.input_json, args.output_csv)
