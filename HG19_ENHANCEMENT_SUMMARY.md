# Configuration Updates Summary

## Overview
Updated the genomics automation pipeline to use hg19 as the default reference genome with enhanced CSV output capabilities including protein changes and preferred transcript analysis.

## Changes Made

### 1. Reference Genome Configuration
- **Default Reference Version**: Changed from hg38 to hg19
- **Default Reference File**: Set to `/workspaces/Impact-Assessment/hg19.fa`
- **Git LFS Configuration**: Set up to handle large reference genome files

### 2. Processing Configuration  
- **Default Thread Count**: Increased from 4 to 16 threads for better performance
- **Max Thread Limit**: Increased UI slider maximum to 32 threads

### 3. Enhanced CSV Output

#### New Features Added:
- **Protein Changes Column**: Extracts clean protein change notation (e.g., "p.Arg123Gln")
- **Preferred Transcript Analysis**: Determines if transcript is preferred based on:
  - MANE Select transcripts (highest priority)
  - MANE Plus Clinical transcripts
  - RefSeq transcripts (NM_ prefix)
  - Ensembl transcripts (ENST prefix)
  - Canonical transcript annotations

#### New CSV Columns:
- `preferred_transcript`: "Yes"/"No" indicator
- `transcript_preference_reason`: Detailed reasoning (optional)
- `protein_change`: Clean protein change notation

### 4. Files Created/Modified

#### New Files:
- `genomics_automation/transcript_config.py`: Transcript preference logic
- `external_tools/enhanced_json_to_csv.py`: Enhanced CSV converter

#### Modified Files:
- `genomics_automation/config.py`: Updated defaults for hg19, threads, reference file
- `.env.example`: Updated environment variable defaults
- `app.py`: Enhanced UI with CSV output preferences
- `.gitignore`: Modified to allow hg19 files via Git LFS

### 5. Environment Variable Changes

#### Updated Defaults in `.env.example`:
```bash
# Changed from hg38 to hg19
export GENOMICS_TRANSVAR_REF_VERSION="hg19"

# Added reference file path
export GENOMICS_TRANSVAR_REFERENCE_FILE="/workspaces/Impact-Assessment/hg19.fa"

# Increased default threads from 4 to 16  
export GENOMICS_MAX_WORKERS="16"

# Updated to use enhanced converter
export GENOMICS_JSON_TO_CSV_SCRIPT="/workspaces/Impact-Assessment/external_tools/enhanced_json_to_csv.py"
```

### 6. UI Enhancements

#### New Configuration Options:
- **CSV Converter Type**: Choose between Enhanced or Basic converter
- **Protein Changes**: Toggle inclusion of protein change column
- **Transcript Preferences**: Toggle preferred transcript analysis
- **Preference Details**: Toggle detailed reasoning column

#### Improved Defaults:
- Reference version selector defaults to hg19
- Reference FASTA field pre-populated with hg19.fa path
- Max workers slider allows up to 32 threads

### 7. Reference Genome Integration

#### Git LFS Setup:
- Configured to track `*.fa` files with Git LFS
- Ready to commit hg19.fa and hg19.fa.fai files

#### Usage:
- Pipeline will automatically use `/workspaces/Impact-Assessment/hg19.fa` as reference
- No need for manual reference file configuration in most cases

## Usage Instructions

### 1. Start the Application:
```bash
streamlit run app.py
```

### 2. Default Configuration:
- Reference: hg19
- Threads: 16
- CSV Format: Enhanced with protein changes and transcript preferences

### 3. CSV Output Features:
- Protein changes extracted and displayed in clean format
- Transcript preference analysis performed automatically
- Additional columns for better variant interpretation

### 4. Customization:
- All settings can be modified via the sidebar UI
- Environment variables can override defaults
- Choice between enhanced and basic CSV formats

## Benefits

1. **Improved Performance**: 16 threads by default for faster processing
2. **Better Annotation**: hg19 reference genome provides more comprehensive coverage
3. **Enhanced Output**: Protein changes and transcript preferences aid in interpretation
4. **User-Friendly**: Pre-configured defaults require minimal setup
5. **Flexible**: Easy switching between output formats and configuration options
