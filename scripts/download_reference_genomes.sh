#!/bin/bash
"""
Download Reference Genomes Script

This script downloads the hg19 reference genome files needed for the 
genomics automation pipeline.
"""

set -e  # Exit on any error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🧬 Genomics Pipeline - Reference Genome Downloader${NC}"
echo "=================================================="

# Check if files already exist
HG19_FA="$PROJECT_ROOT/hg19.fa"
HG19_FAI="$PROJECT_ROOT/hg19.fa.fai"

if [[ -f "$HG19_FA" && -f "$HG19_FAI" ]]; then
    echo -e "${GREEN}✅ Reference genome files already exist:${NC}"
    echo "   - hg19.fa ($(du -h "$HG19_FA" | cut -f1))"
    echo "   - hg19.fa.fai ($(du -h "$HG19_FAI" | cut -f1))"
    echo ""
    read -p "Do you want to re-download? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${BLUE}Skipping download. Files are ready for use.${NC}"
        exit 0
    fi
fi

echo -e "${YELLOW}📥 Downloading hg19 reference genome...${NC}"
echo ""

# Create temporary directory
TEMP_DIR=$(mktemp -d)
echo "Using temporary directory: $TEMP_DIR"

# Function to cleanup on exit
cleanup() {
    echo -e "${YELLOW}🧹 Cleaning up temporary files...${NC}"
    rm -rf "$TEMP_DIR"
}
trap cleanup EXIT

cd "$TEMP_DIR"

# Download options - user can choose source
echo "Select download source:"
echo "1) UCSC Genome Browser (recommended)"
echo "2) NCBI GenBank"
echo "3) Ensembl"
echo ""
read -p "Enter choice (1-3) [default: 1]: " choice
choice=${choice:-1}

case $choice in
    1)
        echo -e "${BLUE}📡 Downloading from UCSC Genome Browser...${NC}"
        BASE_URL="https://hgdownload.cse.ucsc.edu/goldenPath/hg19/bigZips"
        
        echo "Downloading hg19.fa.gz (this may take several minutes)..."
        wget -c "$BASE_URL/hg19.fa.gz" -O hg19.fa.gz
        
        echo "Extracting hg19.fa..."
        gunzip hg19.fa.gz
        
        echo "Generating FASTA index..."
        samtools faidx hg19.fa
        ;;
        
    2)
        echo -e "${BLUE}📡 Downloading from NCBI GenBank...${NC}"
        # Note: This is a simplified example - actual NCBI download would be more complex
        echo -e "${RED}❌ NCBI download not implemented in this demo script${NC}"
        echo "Please use UCSC option (1) for now."
        exit 1
        ;;
        
    3)
        echo -e "${BLUE}📡 Downloading from Ensembl...${NC}"
        echo -e "${RED}❌ Ensembl download not implemented in this demo script${NC}"
        echo "Please use UCSC option (1) for now."
        exit 1
        ;;
        
    *)
        echo -e "${RED}❌ Invalid choice. Exiting.${NC}"
        exit 1
        ;;
esac

# Verify files were downloaded
if [[ ! -f "hg19.fa" ]]; then
    echo -e "${RED}❌ Error: hg19.fa was not created${NC}"
    exit 1
fi

if [[ ! -f "hg19.fa.fai" ]]; then
    echo -e "${YELLOW}⚠️  FASTA index not found, creating it...${NC}"
    if command -v samtools &> /dev/null; then
        samtools faidx hg19.fa
    else
        echo -e "${RED}❌ samtools not found. Please install samtools or create the index manually.${NC}"
        exit 1
    fi
fi

# Move files to project directory
echo -e "${BLUE}📁 Moving files to project directory...${NC}"
mv hg19.fa "$PROJECT_ROOT/"
mv hg19.fa.fai "$PROJECT_ROOT/"

# Verify final files
echo -e "${GREEN}✅ Reference genome files successfully downloaded:${NC}"
echo "   - hg19.fa ($(du -h "$PROJECT_ROOT/hg19.fa" | cut -f1))"
echo "   - hg19.fa.fai ($(du -h "$PROJECT_ROOT/hg19.fa.fai" | cut -f1))"
echo ""

echo -e "${GREEN}🎉 Download completed successfully!${NC}"
echo ""
echo -e "${BLUE}The genomics pipeline is now ready to use with hg19 reference genome.${NC}"
echo ""
echo "Next steps:"
echo "  1. Start the pipeline: streamlit run app.py"
echo "  2. The reference path is automatically configured: /workspaces/Impact-Assessment/hg19.fa"
echo ""
