"""
Transcript preference configuration for genomics pipeline.
"""

from typing import Dict, List, Set
from dataclasses import dataclass
from enum import Enum


class TranscriptSource(str, Enum):
    """Available transcript sources."""
    REFSEQ = "refseq"
    ENSEMBL = "ensembl"
    UCSC = "ucsc"
    MANE = "mane"  # Matched Annotation from NCBI and EMBL-EBI


@dataclass
class TranscriptPreference:
    """Configuration for transcript selection preferences."""
    
    # Preferred sources in order of priority
    preferred_sources: List[TranscriptSource] = None
    
    # Preferred transcript prefixes (in order of priority)
    preferred_prefixes: List[str] = None
    
    # MANE Select transcripts (highest priority)
    use_mane_select: bool = True
    
    # MANE Plus Clinical transcripts (second priority)
    use_mane_plus_clinical: bool = True
    
    # Canonical transcripts from Ensembl
    use_ensembl_canonical: bool = True
    
    def __post_init__(self):
        """Set default values if not provided."""
        if self.preferred_sources is None:
            self.preferred_sources = [
                TranscriptSource.MANE,
                TranscriptSource.REFSEQ,
                TranscriptSource.ENSEMBL,
                TranscriptSource.UCSC
            ]
        
        if self.preferred_prefixes is None:
            self.preferred_prefixes = [
                "NM_",      # RefSeq mRNA
                "ENST",     # Ensembl transcript
                "uc",       # UCSC transcript
                "NR_",      # RefSeq non-coding RNA
            ]


class TranscriptSelector:
    """Utility class for selecting preferred transcripts."""
    
    def __init__(self, preferences: TranscriptPreference = None):
        self.preferences = preferences or TranscriptPreference()
        
        # Known MANE transcripts (this would be loaded from database in production)
        self.mane_select_transcripts: Set[str] = {
            "NM_000059.3",  # BRCA2 example
            "NM_007294.3",  # BRCA1 example
            "NM_000314.6",  # PTEN example
            "NM_004333.4",  # BRAF example
            # Add more as needed
        }
        
        self.mane_plus_clinical_transcripts: Set[str] = {
            "NM_000038.5",  # APC example
            "NM_000222.2",  # KIT example
            # Add more as needed
        }
    
    def is_preferred_transcript(self, transcript_id: str, gene: str = None) -> tuple[bool, str]:
        """
        Determine if a transcript is preferred and return reasoning.
        
        Args:
            transcript_id: The transcript identifier
            gene: Optional gene name for context
        
        Returns:
            Tuple of (is_preferred, reason)
        """
        if not transcript_id:
            return False, "No transcript ID provided"
        
        # Check MANE Select (highest priority)
        if self.preferences.use_mane_select and transcript_id in self.mane_select_transcripts:
            return True, "MANE Select"
        
        # Check MANE Plus Clinical
        if self.preferences.use_mane_plus_clinical and transcript_id in self.mane_plus_clinical_transcripts:
            return True, "MANE Plus Clinical"
        
        # Check preferred prefixes
        for prefix in self.preferences.preferred_prefixes:
            if transcript_id.startswith(prefix):
                return True, f"Preferred source ({prefix})"
        
        # Check if it's a known canonical transcript
        if self.preferences.use_ensembl_canonical and "canonical" in transcript_id.lower():
            return True, "Ensembl Canonical"
        
        return False, "Non-preferred transcript"
    
    def rank_transcripts(self, transcripts: List[str], gene: str = None) -> List[tuple[str, int, str]]:
        """
        Rank a list of transcripts by preference.
        
        Args:
            transcripts: List of transcript identifiers
            gene: Optional gene name for context
        
        Returns:
            List of tuples (transcript_id, rank, reason) sorted by preference
        """
        ranked = []
        
        for transcript in transcripts:
            is_preferred, reason = self.is_preferred_transcript(transcript, gene)
            
            # Assign numeric rank based on preference type
            if "MANE Select" in reason:
                rank = 1
            elif "MANE Plus Clinical" in reason:
                rank = 2
            elif "NM_" in transcript:
                rank = 3
            elif "ENST" in transcript:
                rank = 4
            elif is_preferred:
                rank = 5
            else:
                rank = 10
            
            ranked.append((transcript, rank, reason))
        
        # Sort by rank (lower is better)
        ranked.sort(key=lambda x: x[1])
        return ranked
    
    def select_best_transcript(self, transcripts: List[str], gene: str = None) -> tuple[str, str]:
        """
        Select the best transcript from a list.
        
        Args:
            transcripts: List of transcript identifiers
            gene: Optional gene name for context
        
        Returns:
            Tuple of (best_transcript, reason)
        """
        if not transcripts:
            return "", "No transcripts available"
        
        if len(transcripts) == 1:
            is_preferred, reason = self.is_preferred_transcript(transcripts[0], gene)
            return transcripts[0], reason
        
        ranked = self.rank_transcripts(transcripts, gene)
        return ranked[0][0], ranked[0][2]


# Default transcript selector instance
default_transcript_selector = TranscriptSelector()
