#!/bin/bash
# Genomics Automation Pipeline Startup Script

# Set up environment variables
export GENOMICS_TRANSVAR_EXECUTABLE="transvar"
export GENOMICS_SARJ_SCRIPT="/workspaces/Impact-Assessment/external_tools/mock_nirvana_junior.sh"
export GENOMICS_TPS_EXECUTABLE="/workspaces/Impact-Assessment/external_tools/mock_tps.sh"
export GENOMICS_NIRVANA_EXECUTABLE="/workspaces/Impact-Assessment/external_tools/mock_tps.sh"
export GENOMICS_JSON_TO_CSV_SCRIPT="/workspaces/Impact-Assessment/external_tools/mock_json_to_csv.py"

# Knowledge Base paths (mock directories)
export GENOMICS_KB_COSMIC="/workspaces/Impact-Assessment/external_tools/cosmic_kb"
export GENOMICS_KB_CLINVAR="/workspaces/Impact-Assessment/external_tools/clinvar_kb"
export GENOMICS_KB_ONCOKB="/workspaces/Impact-Assessment/external_tools/oncokb_kb"

# Processing settings
export GENOMICS_MAX_WORKERS="4"
export GENOMICS_TIMEOUT_SECONDS="300"
export GENOMICS_RETRY_ATTEMPTS="3"

# TransVar settings
export GENOMICS_TRANSVAR_DATABASE="refseq"
export GENOMICS_TRANSVAR_REF_VERSION="hg38"
export GENOMICS_TRANSVAR_USE_CCDS="true"

# Output settings
export GENOMICS_OUTPUT_DIR="/workspaces/Impact-Assessment/output"
export GENOMICS_TEMP_DIR="/workspaces/Impact-Assessment/temp"

# Create necessary directories
mkdir -p "$GENOMICS_OUTPUT_DIR"
mkdir -p "$GENOMICS_TEMP_DIR"
mkdir -p "/workspaces/Impact-Assessment/logs"

# Create mock KB directories
mkdir -p "$GENOMICS_KB_COSMIC" "$GENOMICS_KB_CLINVAR" "$GENOMICS_KB_ONCOKB"

echo "🧬 Starting Genomics Automation Pipeline..."
echo "📍 External tools configured at: /workspaces/Impact-Assessment/external_tools/"
echo "📊 Output directory: $GENOMICS_OUTPUT_DIR"
echo "🔬 TransVar executable: $GENOMICS_TRANSVAR_EXECUTABLE"

# Change to the application directory
cd /workspaces/Impact-Assessment

# Test that everything is working
echo "🧪 Testing configuration..."
python -c "
from genomics_automation.config import Config
config = Config()
print(f'✅ Configuration loaded successfully')
print(f'   - Database: {config.transvar.database}')
print(f'   - Reference: {config.transvar.ref_version}')
print(f'   - SARJ Script: {config.paths.junior_script_path}')
print(f'   - TPS Executable: {config.paths.tps_path}')
print(f'   - Output Dir: {config.paths.output_dir}')
"

echo ""
echo "🚀 Starting Streamlit application..."
echo "📱 Access the app at: http://localhost:8501"
echo ""

# Start Streamlit
streamlit run app.py --server.headless true --server.port 8501
