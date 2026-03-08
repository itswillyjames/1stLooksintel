"""Scope Summary Stage - Deterministic implementation.

Generates project type classification, scope summary, and buyer fit analysis
from permit data WITHOUT external LLM calls.
"""

from typing import Dict, Any, Tuple, List
from pydantic import BaseModel, Field
from app.pipeline.stage_runner import StageRunner


class ScopeSummaryInput(BaseModel):
    """Input model for scope_summary stage."""
    permit_id: str
    city: str
    address_raw: str
    work_type: str
    description_raw: str
    valuation: int
    filed_date: str
    issued_date: str | None = None


class BuyerFit(BaseModel):
    """Buyer fit scoring."""
    score: float = Field(ge=0.0, le=100.0)
    reasons: List[str]


class ScopeSummaryOutput(BaseModel):
    """Output model for scope_summary stage."""
    project_type: str = Field(pattern="^(commercial|mixed_use|industrial|institutional|residential|other)$")
    scope_summary: str = Field(min_length=10, max_length=500)
    estimated_size_sqft: int = Field(ge=0)
    buyer_fit: BuyerFit


class ScopeSummaryStage(StageRunner):
    """Deterministic scope summary generation.
    
    Classifies project type, generates summary, and scores buyer fit
    based on permit data using rule-based logic.
    """
    
    @property
    def stage_name(self) -> str:
        return "scope_summary"
    
    @property
    def input_model(self) -> type[BaseModel]:
        return ScopeSummaryInput
    
    @property
    def output_model(self) -> type[BaseModel]:
        return ScopeSummaryOutput
    
    def classify_project_type(self, work_type: str, description: str) -> str:
        """Deterministic project type classification."""
        work_type_lower = work_type.lower()
        description_lower = description.lower()
        
        # Commercial indicators
        if any(kw in work_type_lower for kw in ["commercial", "retail", "office", "restaurant"]):
            return "commercial"
        
        # Industrial indicators
        if any(kw in work_type_lower for kw in ["industrial", "warehouse", "manufacturing", "factory"]):
            return "industrial"
        
        # Institutional indicators
        if any(kw in work_type_lower for kw in ["institutional", "school", "hospital", "government", "civic"]):
            return "institutional"
        
        # Mixed-use indicators
        if "mixed" in work_type_lower or ("residential" in work_type_lower and "commercial" in description_lower):
            return "mixed_use"
        
        # Residential indicators
        if any(kw in work_type_lower for kw in ["residential", "apartment", "housing", "home"]):
            return "residential"
        
        return "other"
    
    def generate_scope_summary(self, work_type: str, description: str, valuation: int, address: str) -> str:
        """Generate human-readable scope summary."""
        project_type = self.classify_project_type(work_type, description)
        
        # Extract key details
        summary_parts = []
        
        # Project type
        summary_parts.append(f"{project_type.replace('_', ' ').title()} project")
        
        # Location
        summary_parts.append(f"at {address}")
        
        # Key work description
        work_desc = work_type.replace("_", " ").lower()
        if description:
            # Extract first sentence or first 100 chars
            desc_snippet = description.split(".")[0][:100]
            summary_parts.append(f"involving {desc_snippet.lower()}")
        else:
            summary_parts.append(f"involving {work_desc}")
        
        # Valuation
        if valuation >= 1000000:
            summary_parts.append(f"(${valuation / 1000000:.1f}M project value)")
        elif valuation >= 1000:
            summary_parts.append(f"(${valuation / 1000:.0f}K project value)")
        else:
            summary_parts.append(f"(${valuation:,} project value)")
        
        return " ".join(summary_parts) + "."
    
    def estimate_size(self, valuation: int, project_type: str) -> int:
        """Estimate square footage based on valuation and type."""
        # Cost per sqft estimates (rough averages)
        cost_per_sqft = {
            "commercial": 200,
            "industrial": 150,
            "institutional": 250,
            "mixed_use": 225,
            "residential": 175,
            "other": 180
        }
        
        cost = cost_per_sqft.get(project_type, 180)
        return int(valuation / cost)
    
    def score_buyer_fit(self, valuation: int, project_type: str, description: str) -> BuyerFit:
        """Score buyer fit based on deterministic rules."""
        score = 0.0
        reasons = []
        
        # Valuation scoring
        if valuation >= 1500000:
            score += 40
            reasons.append(f"High-value project: ${valuation / 1000000:.1f}M")
        elif valuation >= 750000:
            score += 30
            reasons.append(f"Mid-value project: ${valuation / 1000:.0f}K")
        elif valuation >= 250000:
            score += 15
            reasons.append(f"Moderate value: ${valuation / 1000:.0f}K")
        else:
            reasons.append(f"Low value: ${valuation / 1000:.0f}K")
        
        # Project type scoring
        if project_type in ["commercial", "industrial", "institutional"]:
            score += 35
            reasons.append(f"Target sector: {project_type}")
        elif project_type == "mixed_use":
            score += 25
            reasons.append("Mixed-use development")
        
        # Keywords scoring
        keywords = ["new construction", "expansion", "tenant improvement", "build-out", "renovation"]
        matched_keywords = [kw for kw in keywords if kw in description.lower()]
        if matched_keywords:
            score += 15
            reasons.append(f"Key activities: {', '.join(matched_keywords[:2])}")
        
        # Base score
        if not reasons:
            score = 10
            reasons = ["Standard permit scope"]
        else:
            score += 10  # Base score
        
        # Cap at 100
        score = min(score, 100.0)
        
        return BuyerFit(score=score, reasons=reasons)
    
    def validate_semantic(self, output: ScopeSummaryOutput) -> Tuple[bool, str]:
        """Semantic validation rules."""
        # Check buyer_fit score is reasonable
        if output.buyer_fit.score < 0 or output.buyer_fit.score > 100:
            return False, "Buyer fit score must be between 0 and 100"
        
        # Check buyer_fit has at least one reason
        if not output.buyer_fit.reasons:
            return False, "Buyer fit must include at least one reason"
        
        # Check scope_summary is not just placeholder
        if "test" in output.scope_summary.lower() and len(output.scope_summary) < 50:
            return False, "Scope summary appears to be placeholder text"
        
        # Check estimated_size_sqft is reasonable
        if output.estimated_size_sqft <= 0:
            return False, "Estimated size must be positive"
        
        if output.estimated_size_sqft > 10000000:  # 10M sqft is unreasonably large
            return False, "Estimated size exceeds reasonable limits"
        
        return True, ""
    
    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute scope summary generation."""
        # Extract fields
        work_type = input_data["work_type"]
        description = input_data["description_raw"]
        valuation = input_data["valuation"]
        address = input_data["address_raw"]
        
        # Classify project type
        project_type = self.classify_project_type(work_type, description)
        
        # Generate scope summary
        scope_summary = self.generate_scope_summary(work_type, description, valuation, address)
        
        # Estimate size
        estimated_size_sqft = self.estimate_size(valuation, project_type)
        
        # Score buyer fit
        buyer_fit = self.score_buyer_fit(valuation, project_type, description)
        
        return {
            "project_type": project_type,
            "scope_summary": scope_summary,
            "estimated_size_sqft": estimated_size_sqft,
            "buyer_fit": buyer_fit.model_dump()
        }
