"""
Streamlit UI for the Genomics Automation Pipeline

A comprehensive interface for automating genomics impact assessment workflows,
from VCF input to final report generation.
"""

import os
import subprocess
import streamlit as st
import pandas as pd
import time
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import tempfile
import zipfile

# Load environment variables from .env.example
def load_env_file():
    """Load environment variables from .env.example file."""
    env_file = Path(__file__).parent / ".env.example"
    if env_file.exists():
        # Read and parse the .env.example file
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and line.startswith('export '):
                    # Extract variable name and value from export statement
                    export_line = line[7:]  # Remove 'export '
                    if '=' in export_line:
                        key, value = export_line.split('=', 1)
                        # Remove quotes if present
                        value = value.strip('"\'')
                        os.environ[key] = value

# Load environment variables at startup
load_env_file()

# Import our genomics automation modules
from genomics_automation.config import Config, KBSpec, TransVarConfig, ProcessingConfig, PathConfig
from genomics_automation.pipeline import GenomicsPipeline, PipelineInput, PipelineStage
from genomics_automation.transvar_adapter import TransVarAdapter
from genomics_automation.vcf_builder import BatchVCFProcessor, VariantClassifier
from genomics_automation.utils import generate_run_id, read_csv_with_encoding_detection


# Page configuration
st.set_page_config(
    page_title="Genomics Automation Pipeline",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
.main-header {
    padding: 1rem 0;
    border-bottom: 2px solid #f0f2f6;
    margin-bottom: 1rem;
}
.status-box {
    padding: 1rem;
    border-radius: 0.5rem;
    margin: 0.5rem 0;
}
.success-box {
    background-color: #d4edda;
    border: 1px solid #c3e6cb;
    color: #155724;
}
.error-box {
    background-color: #f8d7da;
    border: 1px solid #f5c6cb;
    color: #721c24;
}
.warning-box {
    background-color: #fff3cd;
    border: 1px solid #ffeaa7;
    color: #856404;
}
.info-box {
    background-color: #d1ecf1;
    border: 1px solid #bee5eb;
    color: #0c5460;
}
</style>
""", unsafe_allow_html=True)


class StreamlitPipelineUI:
    """Main UI class for the Streamlit application."""
    
    def __init__(self):
        self.config = self._load_config()
        self.pipeline = GenomicsPipeline(self.config)
        
        # Session state initialization
        if 'pipeline_running' not in st.session_state:
            st.session_state.pipeline_running = False
        if 'current_results' not in st.session_state:
            st.session_state.current_results = None
        if 'progress_messages' not in st.session_state:
            st.session_state.progress_messages = []
    
    def _load_config(self) -> Config:
        """Load configuration with Streamlit-specific overrides."""
        config = Config()
        
        # Override with session state if available
        if 'user_config' in st.session_state:
            return st.session_state.user_config
        
        return config
    
    def _save_config(self) -> None:
        """Save current configuration to session state."""
        st.session_state.user_config = self.config
    
    def render_sidebar(self) -> None:
        """Render the configuration sidebar."""
        st.sidebar.title("⚙️ Configuration")
        
        # Pipeline Stages
        st.sidebar.subheader("Pipeline Stages")
        self.config.stages.run_transvar = st.sidebar.checkbox(
            "Run TransVar Annotation", 
            value=self.config.stages.run_transvar,
            help="Annotate protein variants using TransVar"
        )
        self.config.stages.run_sarj = st.sidebar.checkbox(
            "Run SARJ Generation", 
            value=self.config.stages.run_sarj,
            help="Generate SARJ files using Nirvana Junior"
        )
        self.config.stages.run_tps = st.sidebar.checkbox(
            "Run TPS Processing", 
            value=self.config.stages.run_tps,
            help="Process with TPS multi-KB Nirvana"
        )
        self.config.stages.run_json_conversion = st.sidebar.checkbox(
            "Run JSON to CSV Conversion", 
            value=self.config.stages.run_json_conversion,
            help="Convert TPS JSON output to CSV"
        )
        self.config.stages.run_report_extraction = st.sidebar.checkbox(
            "Generate Final Report", 
            value=self.config.stages.run_report_extraction,
            help="Extract final report from CSV data"
        )
        
        # TransVar Configuration
        st.sidebar.subheader("TransVar Settings")
        
        # Handle both enum and string values for database
        current_db = self.config.transvar.database
        db_value = current_db.value if hasattr(current_db, 'value') else str(current_db)
        
        self.config.transvar.database = st.sidebar.selectbox(
            "Database",
            options=["refseq", "ucsc", "ensembl"],
            index=["refseq", "ucsc", "ensembl"].index(db_value),
            help="Annotation database for TransVar"
        )
        
        # Handle both enum and string values for reference version
        current_ref = self.config.transvar.ref_version
        ref_value = current_ref.value if hasattr(current_ref, 'value') else str(current_ref)
        
        self.config.transvar.ref_version = st.sidebar.selectbox(
            "Reference Version",
            options=["hg19", "hg38"],
            index=["hg19", "hg38"].index(ref_value) if ref_value in ["hg19", "hg38"] else 0,
            help="Reference genome version"
        )
        
        self.config.transvar.use_ccds = st.sidebar.checkbox(
            "Use CCDS",
            value=self.config.transvar.use_ccds,
            help="Use CCDS annotations"
        )
        
        self.config.transvar.reference_file = st.sidebar.text_input(
            "Reference FASTA",
            value=self.config.transvar.reference_file or "/workspaces/Impact-Assessment/hg19.fa",
            help="🧬 Path to reference FASTA file (hg19.fa located in project directory)"
        )
        
        # Check reference genome status
        ref_exists, ref_message = self.config.check_reference_genome()
        if ref_exists:
            st.sidebar.success(f"✅ {ref_message}")
        else:
            st.sidebar.error(f"❌ {ref_message}")
            if "download" in ref_message:
                if st.sidebar.button("📥 Download hg19 Reference"):
                    st.sidebar.info("Run: `scripts/download_reference_genomes.sh` in terminal")
        
        # Processing Configuration
        st.sidebar.subheader("Processing Settings")
        self.config.processing.max_workers = st.sidebar.slider(
            "Max Workers",
            min_value=1,
            max_value=32,
            value=self.config.processing.max_workers,
            help="Number of parallel processing threads"
        )
        
        self.config.processing.timeout_seconds = st.sidebar.slider(
            "Timeout (seconds)",
            min_value=30,
            max_value=600,
            value=self.config.processing.timeout_seconds,
            help="Timeout for individual operations"
        )
        
        # Tool Paths
        st.sidebar.subheader("Tool Paths")
        self.config.paths.junior_script_path = st.sidebar.text_input(
            "Junior Script Path",
            value=self.config.paths.junior_script_path or "",
            help="Path to Nirvana Junior (SARJ) script"
        )
        
        self.config.paths.tps_path = st.sidebar.text_input(
            "TPS Path",
            value=self.config.paths.tps_path or "",
            help="Path to TPS executable"
        )
        
        self.config.paths.nirvana_path = st.sidebar.text_input(
            "Nirvana Path",
            value=self.config.paths.nirvana_path or "",
            help="Path to Nirvana executable"
        )
        
        self.config.paths.json_to_csv_script = st.sidebar.text_input(
            "JSON to CSV Script",
            value=self.config.paths.json_to_csv_script or "",
            help="Path to JSON to CSV converter script"
        )
        
        # CSV Output Preferences
        st.sidebar.subheader("CSV Output Preferences")
        
        # CSV converter selection
        csv_converter_type = st.sidebar.radio(
            "CSV Converter Type:",
            options=["Enhanced (with protein changes & transcript preferences)", "Basic (simple format)"],
            index=0 if "enhanced" in (self.config.paths.json_to_csv_script or "").lower() else 1,
            help="Choose between enhanced converter with protein changes or basic converter"
        )
        
        # Update the script path based on selection
        if csv_converter_type.startswith("Enhanced"):
            self.config.paths.json_to_csv_script = "/workspaces/Impact-Assessment/external_tools/enhanced_json_to_csv.py"
        else:
            self.config.paths.json_to_csv_script = "/workspaces/Impact-Assessment/external_tools/mock_json_to_csv.py"
        
        # CSV output options
        if csv_converter_type.startswith("Enhanced"):
            include_protein_changes = st.sidebar.checkbox(
                "Include Protein Changes",
                value=True,
                help="✅ Extract and display protein changes (e.g., p.Arg123Gln) in separate column"
            )
            
            include_transcript_preferences = st.sidebar.checkbox(
                "Show Preferred Transcript Status",
                value=True,
                help="✅ Indicate whether each transcript is preferred (MANE Select, RefSeq, etc.)"
            )
            
            include_preference_details = st.sidebar.checkbox(
                "Include Preference Reasoning",
                value=False,
                help="Show detailed reasoning for transcript preference classification"
            )
            
            # Store these preferences in session state for use during processing
            st.session_state.csv_preferences = {
                'include_protein_changes': include_protein_changes,
                'include_transcript_preferences': include_transcript_preferences,
                'include_preference_details': include_preference_details
            }
        
        # Display current CSV configuration
        st.sidebar.info(f"📋 Current converter: {Path(self.config.paths.json_to_csv_script or '').name}")
        
        # Knowledge Bases Configuration
        st.sidebar.subheader("Knowledge Bases")
        self._render_knowledge_bases_config()
        
        # Debug mode
        self.config.debug_mode = st.sidebar.checkbox(
            "Debug Mode",
            value=self.config.debug_mode,
            help="Enable debug logging and preserve intermediate files"
        )
        
        # Save configuration
        self._save_config()
    
    def _render_knowledge_bases_config(self) -> None:
        """Render knowledge bases configuration interface."""
        if 'kb_configs' not in st.session_state:
            st.session_state.kb_configs = self.config.paths.knowledge_bases or []
        
        st.sidebar.write("Configure Knowledge Bases:")
        
        # Add new KB button
        if st.sidebar.button("+ Add Knowledge Base"):
            st.session_state.kb_configs.append(KBSpec(version="", path="", description=""))
        
        # Render existing KBs
        for i, kb in enumerate(st.session_state.kb_configs):
            with st.sidebar.expander(f"KB {i+1}: {kb.version or 'New'}"):
                kb.version = st.text_input(f"Version {i+1}", value=kb.version, key=f"kb_version_{i}")
                kb.path = st.text_input(f"Path {i+1}", value=kb.path, key=f"kb_path_{i}")
                kb.description = st.text_input(f"Description {i+1}", value=kb.description or "", key=f"kb_desc_{i}")
                
                if st.button(f"Remove KB {i+1}", key=f"remove_kb_{i}"):
                    st.session_state.kb_configs.pop(i)
                    st.rerun()
        
        # Update config
        self.config.paths.knowledge_bases = [kb for kb in st.session_state.kb_configs if kb.version and kb.path]
    
    def render_header(self) -> None:
        """Render the main application header."""
        st.markdown('<div class="main-header">', unsafe_allow_html=True)
        st.title("🧬 Genomics Automation Pipeline")
        st.markdown("""
        **Automate the complete Impact Assessment workflow**: VCF Input → SARJ Generation → 
        TPS Output → JSON→CSV → Final Report in one click.
        """)
        st.markdown('</div>', unsafe_allow_html=True)
    
    def render_input_section(self) -> Optional[PipelineInput]:
        """Render the input section and return pipeline input if valid."""
        st.header("📥 Input Configuration")
        
        # Input mode selection
        input_mode = st.radio(
            "Select Input Mode:",
            options=["Variant Entry", "CSV Upload", "VCF Upload"],
            horizontal=True
        )
        
        pipeline_input = None
        
        if input_mode == "Variant Entry":
            pipeline_input = self._render_variant_input()
        elif input_mode == "CSV Upload":
            pipeline_input = self._render_csv_input()
        elif input_mode == "VCF Upload":
            pipeline_input = self._render_vcf_input()
        
        return pipeline_input
    
    def _render_variant_input(self) -> Optional[PipelineInput]:
        """Render variant entry interface."""
        st.subheader("Manual Variant Entry")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Option A: Combined String**")
            combined_input = st.text_area(
                "Gene/Transcript/Protein (one per line)",
                placeholder="BRAF:p.V600E\nTP53:p.R273H\nEGFR:p.L858R",
                help="Enter variants in format: Gene:p.VariantNotation"
            )
        
        with col2:
            st.write("**Option B: Separate Fields**")
            manual_gene = st.text_input("Gene Symbol", placeholder="BRAF")
            manual_transcript = st.text_input("Transcript (optional)", placeholder="NM_004333.4")
            manual_protein = st.text_input("Protein Change", placeholder="p.V600E")
        
        # Process input
        variants = []
        
        if combined_input:
            for line in combined_input.strip().split('\n'):
                if ':' in line:
                    gene, protein_change = line.split(':', 1)
                    variants.append({
                        'gene': gene.strip(),
                        'protein_change': protein_change.strip()
                    })
        
        if manual_gene and manual_protein:
            variants.append({
                'gene': manual_gene.strip(),
                'protein_change': manual_protein.strip()
            })
        
        if variants:
            st.success(f"Ready to process {len(variants)} variants")
            return PipelineInput(mode="variants", data=variants)
        
        return None
    
    def _render_csv_input(self) -> Optional[PipelineInput]:
        """Render CSV upload interface."""
        st.subheader("CSV File Upload")
        
        uploaded_file = st.file_uploader(
            "Upload CSV file with variant data",
            type=['csv'],
            help="CSV should contain columns for gene symbols and protein changes"
        )
        
        if uploaded_file is not None:
            # Save uploaded file temporarily
            with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_path = Path(tmp_file.name)
            
            # Preview the CSV
            try:
                df = pd.read_csv(tmp_path)
                st.write("**CSV Preview:**")
                st.dataframe(df.head())
                
                # Column mapping
                st.write("**Column Mapping:**")
                col1, col2 = st.columns(2)
                
                with col1:
                    gene_column = st.selectbox(
                        "Gene Column",
                        options=df.columns.tolist(),
                        help="Select the column containing gene symbols"
                    )
                
                with col2:
                    protein_column = st.selectbox(
                        "Protein Change Column",
                        options=df.columns.tolist(),
                        help="Select the column containing protein changes"
                    )
                
                if st.button("Validate CSV"):
                    valid_rows = 0
                    for _, row in df.iterrows():
                        if pd.notna(row[gene_column]) and pd.notna(row[protein_column]):
                            valid_rows += 1
                    
                    st.info(f"Found {valid_rows} valid variant rows out of {len(df)} total rows")
                
                return PipelineInput(mode="csv", data=tmp_path)
            
            except Exception as e:
                st.error(f"Error reading CSV file: {e}")
        
        return None
    
    def _render_vcf_input(self) -> Optional[PipelineInput]:
        """Render VCF upload interface."""
        st.subheader("VCF File Upload")
        
        uploaded_file = st.file_uploader(
            "Upload VCF file",
            type=['vcf'],
            help="Upload a VCF file to skip TransVar annotation and proceed directly to SARJ generation"
        )
        
        if uploaded_file is not None:
            # Save uploaded file temporarily
            with tempfile.NamedTemporaryFile(delete=False, suffix='.vcf') as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_path = Path(tmp_file.name)
            
            # Validate VCF
            try:
                with open(tmp_path, 'r') as f:
                    lines = f.readlines()
                
                header_lines = [line for line in lines if line.startswith('#')]
                variant_lines = [line for line in lines if not line.startswith('#') and line.strip()]
                
                st.success(f"VCF file validated: {len(variant_lines)} variants, {len(header_lines)} header lines")
                
                # Show preview
                if variant_lines:
                    st.write("**Variant Preview:**")
                    preview_lines = variant_lines[:5]
                    for i, line in enumerate(preview_lines, 1):
                        st.text(f"{i}: {line.strip()}")
                    
                    if len(variant_lines) > 5:
                        st.text(f"... and {len(variant_lines) - 5} more variants")
                
                return PipelineInput(mode="vcf", data=tmp_path)
            
            except Exception as e:
                st.error(f"Error reading VCF file: {e}")
        
        return None
    
    def render_pipeline_control(self, pipeline_input: PipelineInput) -> None:
        """Render pipeline execution controls."""
        st.header("🚀 Pipeline Execution")
        
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            if st.button(
                "▶️ Run Full Pipeline",
                disabled=st.session_state.pipeline_running,
                type="primary"
            ):
                self._run_pipeline(pipeline_input)
        
        with col2:
            if st.button("🔄 Reset", disabled=st.session_state.pipeline_running):
                self._reset_pipeline()
        
        with col3:
            if st.button("📋 View Config"):
                self._show_config_summary()
    
    def _run_pipeline(self, pipeline_input: PipelineInput) -> None:
        """Execute the pipeline with progress tracking."""
        # Clear any previous download button keys to prevent duplicates
        self._clear_download_session_state()
        
        st.session_state.pipeline_running = True
        st.session_state.progress_messages = []
        
        # Create progress tracking
        progress_bar = st.progress(0)
        status_container = st.container()
        
        def status_callback(status):
            """Callback to update UI with pipeline status."""
            st.session_state.progress_messages.append({
                'stage': status.stage.value,
                'message': status.message,
                'progress': status.progress,
                'error': status.error,
                'timestamp': time.time()
            })
            
            # Update progress bar
            stage_weights = {
                PipelineStage.INPUT_VALIDATION: 0.05,
                PipelineStage.TRANSVAR_ANNOTATION: 0.20,
                PipelineStage.VCF_GENERATION: 0.10,
                PipelineStage.SARJ_GENERATION: 0.20,
                PipelineStage.TPS_PROCESSING: 0.25,
                PipelineStage.JSON_TO_CSV: 0.10,
                PipelineStage.REPORT_EXTRACTION: 0.10
            }
            
            total_progress = sum(stage_weights[stage] for stage in PipelineStage 
                               if any(msg['stage'] == stage.value for msg in st.session_state.progress_messages))
            
            progress_bar.progress(min(total_progress, 1.0))
            
            # Update status display
            with status_container:
                self._render_progress_status()
        
        # Set up pipeline with callback
        self.pipeline.add_status_callback(status_callback)
        
        try:
            # Run pipeline
            result = self.pipeline.run_full_pipeline(pipeline_input)
            st.session_state.current_results = result
            
            if result.success:
                st.success("🎉 Pipeline completed successfully!")
                self._render_results(result)
            else:
                st.error("❌ Pipeline failed")
                for error in result.errors:
                    st.error(error)
        
        except Exception as e:
            st.error(f"Unexpected error: {e}")
        
        finally:
            st.session_state.pipeline_running = False
            progress_bar.progress(1.0)
    
    def _render_progress_status(self) -> None:
        """Render real-time progress status."""
        if not st.session_state.progress_messages:
            return
        
        st.subheader("📊 Pipeline Progress")
        
        # Show latest status
        latest_message = st.session_state.progress_messages[-1]
        
        if latest_message['error']:
            st.markdown(f'<div class="status-box error-box">❌ {latest_message["message"]}</div>', 
                       unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="status-box info-box">⏳ {latest_message["message"]}</div>', 
                       unsafe_allow_html=True)
        
        # Show progress details
        with st.expander("View Progress Details"):
            for msg in reversed(st.session_state.progress_messages[-10:]):  # Last 10 messages
                timestamp = time.strftime('%H:%M:%S', time.localtime(msg['timestamp']))
                stage = msg['stage'].replace('_', ' ').title()
                st.text(f"[{timestamp}] {stage}: {msg['message']}")
    
    def _render_results(self, result) -> None:
        """Render pipeline results."""
        st.header("📊 Pipeline Results")
        
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Execution Time", f"{result.execution_time:.2f}s")
        
        with col2:
            st.metric("Stages Completed", f"{len(result.stages_completed)}")
        
        with col3:
            st.metric("Artifacts Generated", f"{len(result.artifacts)}")
        
        with col4:
            success_rate = 100 if result.success else 0
            st.metric("Success Rate", f"{success_rate}%")
        
        # Results tabs
        tab1, tab2, tab3, tab4 = st.tabs(["📋 Summary", "📁 Downloads", "📈 Metrics", "🔧 Debug"])
        
        with tab1:
            self._render_results_summary(result)
        
        with tab2:
            self._render_downloads(result)
        
        with tab3:
            self._render_metrics(result)
        
        with tab4:
            self._render_debug_info(result)
    
    def _render_results_summary(self, result) -> None:
        """Render results summary."""
        st.subheader("Execution Summary")
        
        st.write(f"**Run ID:** {result.run_id}")
        st.write(f"**Run Directory:** {result.run_directory}")
        st.write(f"**Execution Time:** {result.execution_time:.2f} seconds")
        
        # Stages completed
        st.write("**Stages Completed:**")
        for stage in result.stages_completed:
            st.write(f"✅ {stage.value.replace('_', ' ').title()}")
        
        # Final report preview
        if result.final_report and result.final_report.exists():
            st.subheader("Final Report Preview")
            try:
                df = pd.read_csv(result.final_report)
                st.dataframe(df.head(10))
                st.info(f"Full report contains {len(df)} records")
            except Exception as e:
                st.error(f"Error loading final report: {e}")
    
    def _clear_download_session_state(self) -> None:
        """Clear any download-related session state keys to prevent duplicates."""
        keys_to_remove = []
        for key in st.session_state.keys():
            if (key.startswith('download_') or 
                key.startswith('zip_button_') or 
                key.startswith('downloads_rendered_')):
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del st.session_state[key]
    
    def _render_downloads(self, result) -> None:
        """Render download section."""
        st.subheader("Download Results")
        
        # Use a unique container ID to prevent re-rendering
        downloads_container_key = f"downloads_rendered_{result.run_id}"
        
        # Check if downloads for this run_id have already been rendered
        if downloads_container_key in st.session_state:
            st.info("Downloads already rendered above. Refresh page to reset.")
            return
        
        # Mark this run_id as having downloads rendered
        st.session_state[downloads_container_key] = True
        
        # Create download buttons for each artifact
        for artifact_name, artifact_path in result.artifacts.items():
            if artifact_path:
                # Handle different artifact path types
                if isinstance(artifact_path, list):
                    # Multiple files - create download buttons for each
                    for i, file_path in enumerate(artifact_path):
                        if file_path and isinstance(file_path, (str, Path)) and Path(file_path).exists():
                            with open(file_path, 'rb') as f:
                                st.download_button(
                                    label=f"📥 Download {artifact_name.replace('_', ' ').title()} ({i+1})",
                                    data=f.read(),
                                    file_name=Path(file_path).name,
                                    mime='application/octet-stream',
                                    key=f"download_{result.run_id}_{artifact_name}_{i}"
                                )
                elif isinstance(artifact_path, dict):
                    # Dictionary of files (e.g., knowledge base specific files)
                    for kb_name, file_path in artifact_path.items():
                        if file_path and isinstance(file_path, (str, Path)) and Path(file_path).exists():
                            with open(file_path, 'rb') as f:
                                st.download_button(
                                    label=f"📥 Download {artifact_name.replace('_', ' ').title()} ({kb_name})",
                                    data=f.read(),
                                    file_name=Path(file_path).name,
                                    mime='application/octet-stream',
                                    key=f"download_{result.run_id}_{artifact_name}_{kb_name}"
                                )
                else:
                    # Single file
                    if isinstance(artifact_path, (str, Path)) and Path(artifact_path).exists():
                        with open(artifact_path, 'rb') as f:
                            st.download_button(
                                label=f"📥 Download {artifact_name.replace('_', ' ').title()}",
                                data=f.read(),
                                file_name=Path(artifact_path).name,
                                mime='application/octet-stream',
                                key=f"download_{result.run_id}_{artifact_name}"
                            )
        
        # Zip all artifacts
        if st.button("📦 Download All Results (ZIP)", key=f"zip_button_{result.run_id}"):
            zip_path = self._create_results_zip(result)
            if zip_path:
                with open(zip_path, 'rb') as f:
                    st.download_button(
                        label="📥 Download Results ZIP",
                        data=f.read(),
                        file_name=f"genomics_results_{result.run_id}.zip",
                        mime='application/zip',
                        key=f"download_zip_{result.run_id}"
                    )
    
    def _create_results_zip(self, result) -> Optional[Path]:
        """Create a ZIP file with all results."""
        try:
            zip_path = result.run_directory / f"results_{result.run_id}.zip"
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for artifact_name, artifact_path in result.artifacts.items():
                    if artifact_path:
                        # Handle both single files and lists of files
                        if isinstance(artifact_path, list):
                            for i, file_path in enumerate(artifact_path):
                                if file_path and Path(file_path).exists():
                                    # Create unique names for multiple files
                                    base_name = Path(file_path).stem
                                    ext = Path(file_path).suffix
                                    zip_name = f"{artifact_name}_{i+1}_{base_name}{ext}"
                                    zipf.write(file_path, zip_name)
                        else:
                            if Path(artifact_path).exists():
                                zipf.write(artifact_path, Path(artifact_path).name)
            
            return zip_path
        except Exception as e:
            st.error(f"Error creating ZIP file: {e}")
            return None
    
    def _render_metrics(self, result) -> None:
        """Render detailed metrics."""
        st.subheader("Detailed Metrics")
        
        if result.metrics:
            for key, value in result.metrics.items():
                st.write(f"**{key.replace('_', ' ').title()}:** {value}")
        
        # Artifact details
        st.write("**Artifact Details:**")
        for artifact_name, artifact_path in result.artifacts.items():
            if artifact_path:
                # Handle different artifact path types
                if isinstance(artifact_path, list):
                    # Multiple files in a list
                    for i, file_path in enumerate(artifact_path):
                        # Ensure file_path is a string/path-like object, not an integer or other type
                        if file_path and isinstance(file_path, (str, Path)) and Path(file_path).exists():
                            file_size = Path(file_path).stat().st_size
                            st.write(f"- {artifact_name} ({i+1}): {file_size:,} bytes")
                        elif file_path is not None:
                            # Log what we got instead of a path
                            st.write(f"- {artifact_name} ({i+1}): {type(file_path).__name__} value: {file_path}")
                elif isinstance(artifact_path, dict):
                    # Dictionary of files (e.g., knowledge base specific files)
                    for kb_name, file_path in artifact_path.items():
                        # Ensure file_path is a string/path-like object, not an integer
                        if file_path and isinstance(file_path, (str, Path)) and Path(file_path).exists():
                            file_size = Path(file_path).stat().st_size
                            st.write(f"- {artifact_name} ({kb_name}): {file_size:,} bytes")
                        elif file_path is not None:
                            # Log what we got instead of a path
                            st.write(f"- {artifact_name} ({kb_name}): {type(file_path).__name__} value: {file_path}")
                else:
                    # Single file path
                    try:
                        if Path(artifact_path).exists():
                            file_size = Path(artifact_path).stat().st_size
                            st.write(f"- {artifact_name}: {file_size:,} bytes")
                    except (TypeError, ValueError) as e:
                        st.write(f"- {artifact_name}: Invalid path format ({type(artifact_path).__name__})")
    
    def _render_debug_info(self, result) -> None:
        """Render debug information."""
        st.subheader("Debug Information")
        
        st.write("**Configuration Used:**")
        
        # Handle both enum and string values safely
        db_value = self.config.transvar.database
        db_str = db_value.value if hasattr(db_value, 'value') else str(db_value)
        
        ref_value = self.config.transvar.ref_version
        ref_str = ref_value.value if hasattr(ref_value, 'value') else str(ref_value)
        
        config_dict = {
            'transvar_database': db_str,
            'ref_version': ref_str,
            'max_workers': self.config.processing.max_workers,
            'debug_mode': self.config.debug_mode
        }
        st.json(config_dict)
        
        if result.errors:
            st.write("**Errors:**")
            for error in result.errors:
                st.error(error)
        
        # Log files
        log_files = list(result.run_directory.glob("*.log"))
        if log_files:
            st.write("**Log Files:**")
            for log_file in log_files:
                with st.expander(f"View {log_file.name}"):
                    try:
                        with open(log_file, 'r') as f:
                            st.text(f.read())
                    except Exception as e:
                        st.error(f"Error reading log file: {e}")
    
    def _reset_pipeline(self) -> None:
        """Reset pipeline state."""
        st.session_state.pipeline_running = False
        st.session_state.current_results = None
        st.session_state.progress_messages = []
        st.success("Pipeline state reset")
    
    def _show_config_summary(self) -> None:
        """Show configuration summary."""
        with st.expander("Configuration Summary", expanded=True):
            # Handle enum/string values safely
            db_value = self.config.transvar.database
            db_str = db_value.value if hasattr(db_value, 'value') else str(db_value)
            
            ref_value = self.config.transvar.ref_version
            ref_str = ref_value.value if hasattr(ref_value, 'value') else str(ref_value)
            
            st.json({
                'transvar': {
                    'database': db_str,
                    'ref_version': ref_str,
                    'use_ccds': self.config.transvar.use_ccds
                },
                'processing': {
                    'max_workers': self.config.processing.max_workers,
                    'timeout_seconds': self.config.processing.timeout_seconds
                },
                'stages': {
                    'run_transvar': self.config.stages.run_transvar,
                    'run_sarj': self.config.stages.run_sarj,
                    'run_tps': self.config.stages.run_tps,
                    'run_json_conversion': self.config.stages.run_json_conversion,
                    'run_report_extraction': self.config.stages.run_report_extraction
                },
                'knowledge_bases': len(self.config.paths.knowledge_bases)
            })
    
    def render_variant_templates_info(self) -> None:
        """Render information about supported variant templates."""
        with st.expander("ℹ️ Supported Variant Types"):
            st.markdown("""
            ### Automated Processing (Supported)
            - **Substitutions**: p.A123T, c.123A>T, g.123A>T
            - **Small Deletions**: p.A123del, c.123delA
            - **Small Insertions**: p.A123_T124insV, c.123_124insA
            
            ### Manual Coordinates Required (Placeholders)
            - **CNV Gain/Loss**: Copy number variations - requires user-provided coordinates
            - **Splice Variants**: Exon skipping - requires user-provided breakpoints per gene
            - **RNA Fusions**: Transcript fusions - requires user-provided breakpoints per gene
            - **DNA Fusions**: Chromosomal rearrangements - requires user-provided breakpoints per gene
            
            ⚠️ Unsupported variants will be flagged and require manual coordinate specification.
            """)
    
    def render_help_section(self) -> None:
        """Render help and documentation section."""
        with st.expander("📚 Help & Documentation"):
            st.markdown("""
            ## Quick Start Guide
            
            1. **Configure Tools**: Set paths to TransVar, Junior, TPS, and Nirvana in the sidebar
            2. **Add Knowledge Bases**: Configure one or more knowledge bases for TPS processing
            3. **Select Input**: Choose between manual entry, CSV upload, or VCF upload
            4. **Run Pipeline**: Click "Run Full Pipeline" to execute the complete workflow
            
            ## Pipeline Stages
            
            1. **TransVar Annotation**: Converts protein notation to genomic coordinates
            2. **VCF Generation**: Creates VCF files from annotated variants
            3. **SARJ Generation**: Runs Nirvana Junior to create SARJ files
            4. **TPS Processing**: Processes SARJ through multiple knowledge bases
            5. **JSON to CSV**: Converts TPS output to CSV format
            6. **Report Extraction**: Generates final consolidated report
            
            ## Configuration Tips
            
            - **Reference FASTA**: Providing a reference FASTA file improves TransVar accuracy
            - **Max Workers**: Increase for faster processing on multi-core systems
            - **Debug Mode**: Enable to preserve intermediate files and detailed logs
            
            ## Troubleshooting
            
            - Check tool paths are correct and files exist
            - Ensure knowledge base paths are valid
            - Review error messages in the Debug tab
            - Check log files for detailed error information
            """)
    
    def run(self) -> None:
        """Main application entry point."""
        # Render sidebar
        self.render_sidebar()
        
        # Render main content
        self.render_header()
        
        # Input section
        pipeline_input = self.render_input_section()
        
        # Variant templates info
        self.render_variant_templates_info()
        
        # Pipeline control
        if pipeline_input:
            self.render_pipeline_control(pipeline_input)
        
        # Show current results if available
        if st.session_state.current_results:
            self._render_results(st.session_state.current_results)
        
        # Help section
        self.render_help_section()


def main():
    """Main application function."""
    app = StreamlitPipelineUI()
    app.run()


if __name__ == "__main__":
    main()
