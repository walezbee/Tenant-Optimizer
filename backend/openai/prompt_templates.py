# Prompt templates for OpenAI agent usage

DETECTION_PROMPT = (
    "You are an Azure optimization assistant. Given a list of Azure resources with properties, "
    "identify which ones are orphaned, idle, or safe to remove. Explain your reasoning for each."
)

DEPRECATED_PROMPT = (
    "Given a list of Azure resources, use Azure's latest documentation to spot those that are deprecated or outdated. "
    "For each, recommend a modern replacement or upgrade path."
)