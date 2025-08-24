#!/bin/bash
# Mock Nirvana Junior (SARJ) script for demonstration
# In production, this would be the actual Nirvana Junior executable

INPUT_VCF="$1"
OUTPUT_JSON="$2"

echo "Mock SARJ Processing: $INPUT_VCF -> $OUTPUT_JSON"

# Create a mock SARJ output that simulates real Nirvana annotation
cat > "$OUTPUT_JSON" << 'EOF'
{
  "header": {
    "annotator": "Nirvana_3.18.1",
    "creationTime": "2025-08-23T12:00:00.000000Z",
    "genomeAssembly": "GRCh38",
    "schemaVersion": 6,
    "dataVersion": "3.18.1",
    "vepVersion": "95",
    "samples": []
  },
  "positions": [
    {
      "chromosome": "11",
      "position": 108236402,
      "refAllele": "C",
      "altAlleles": ["T"],
      "quality": 100,
      "filters": ["PASS"],
      "variants": [
        {
          "vid": "11-108236402-C-T",
          "chromosome": "11",
          "begin": 108236402,
          "end": 108236402,
          "isReferenceMinor": false,
          "refAllele": "C",
          "altAllele": "T",
          "variantType": "SNV",
          "hgvsg": "NC_000011.10:g.108236402C>T",
          "phylopScore": 0.9,
          "isDeNovo": false,
          "transcripts": [
            {
              "transcript": "ENST00000534358.1",
              "source": "Ensembl",
              "bioType": "protein_coding",
              "hgnc": "HGNC:582",
              "consequence": ["missense_variant"],
              "hgvsc": "ENST00000534358.1:c.1521C>T",
              "hgvsp": "ENSP00000439902.1:p.(Leu507=)",
              "geneId": "ENSG00000166913",
              "geneName": "ATM",
              "proteinId": "ENSP00000439902.1",
              "codons": "CTT/TTT",
              "aminoAcids": "L/F"
            }
          ]
        }
      ]
    }
  ]
}
EOF

echo "Mock SARJ output created at: $OUTPUT_JSON"
