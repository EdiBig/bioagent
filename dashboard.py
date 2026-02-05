"""
BioAgent Web Dashboard

A Streamlit-based web interface for interacting with BioAgent.

Run with: streamlit run dashboard.py
"""

import streamlit as st
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add bioagent to path
sys.path.insert(0, str(Path(__file__).parent))

from config import Config
from agent import BioAgent


# Page configuration
st.set_page_config(
    page_title="BioAgent Dashboard",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1E88E5;
        margin-bottom: 0;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #666;
        margin-top: 0;
    }
    .tool-call {
        background-color: #E3F2FD;
        padding: 10px;
        border-radius: 5px;
        margin: 5px 0;
        border-left: 4px solid #1E88E5;
    }
    .tool-name {
        font-weight: bold;
        color: #1565C0;
    }
    .response-box {
        background-color: #F5F5F5;
        padding: 15px;
        border-radius: 10px;
        margin: 10px 0;
    }
    .status-online {
        color: #4CAF50;
        font-weight: bold;
    }
    .status-offline {
        color: #F44336;
        font-weight: bold;
    }
    .metric-card {
        background-color: #FAFAFA;
        padding: 15px;
        border-radius: 8px;
        text-align: center;
        border: 1px solid #E0E0E0;
    }
    .chat-user {
        background-color: #E3F2FD;
        padding: 10px 15px;
        border-radius: 15px;
        margin: 5px 0;
        margin-left: 20%;
    }
    .chat-assistant {
        background-color: #F5F5F5;
        padding: 10px 15px;
        border-radius: 15px;
        margin: 5px 0;
        margin-right: 20%;
    }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """Initialize session state variables."""
    if 'agent' not in st.session_state:
        st.session_state.agent = None
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    if 'tool_calls' not in st.session_state:
        st.session_state.tool_calls = []
    if 'initialized' not in st.session_state:
        st.session_state.initialized = False
    if 'query_count' not in st.session_state:
        st.session_state.query_count = 0


def initialize_agent():
    """Initialize the BioAgent."""
    try:
        config = Config.from_env()
        agent = BioAgent(config=config)
        st.session_state.agent = agent
        st.session_state.initialized = True
        return True, "Agent initialized successfully"
    except Exception as e:
        return False, str(e)


def get_system_status():
    """Get system status information."""
    status = {
        'api_key': bool(os.environ.get('ANTHROPIC_API_KEY')),
        'ncbi_key': bool(os.environ.get('NCBI_API_KEY')),
        'workspace': os.environ.get('BIOAGENT_WORKSPACE', 'Default'),
        'model': os.environ.get('BIOAGENT_MODEL', 'claude-sonnet-4-20250514'),
    }
    return status


def render_sidebar():
    """Render the sidebar with system information."""
    with st.sidebar:
        st.markdown("## 🧬 BioAgent")
        st.markdown("AI-Powered Bioinformatics Assistant")

        st.markdown("---")

        # System Status
        st.markdown("### System Status")
        status = get_system_status()

        if status['api_key']:
            st.markdown("**API Key:** <span class='status-online'>✓ Configured</span>", unsafe_allow_html=True)
        else:
            st.markdown("**API Key:** <span class='status-offline'>✗ Not Set</span>", unsafe_allow_html=True)

        if status['ncbi_key']:
            st.markdown("**NCBI Key:** <span class='status-online'>✓ Configured</span>", unsafe_allow_html=True)
        else:
            st.markdown("**NCBI Key:** ⚠️ Not Set (optional)")

        st.markdown(f"**Model:** `{status['model']}`")
        st.markdown(f"**Workspace:** `{status['workspace']}`")

        st.markdown("---")

        # Session Stats
        st.markdown("### Session Statistics")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Queries", st.session_state.query_count)
        with col2:
            st.metric("Tool Calls", len(st.session_state.tool_calls))

        st.markdown("---")

        # Quick Actions
        st.markdown("### Quick Actions")

        if st.button("🔄 Reset Session", use_container_width=True):
            st.session_state.messages = []
            st.session_state.tool_calls = []
            st.session_state.query_count = 0
            st.rerun()

        if st.button("📥 Export Chat", use_container_width=True):
            export_data = {
                'messages': st.session_state.messages,
                'tool_calls': st.session_state.tool_calls,
                'timestamp': datetime.now().isoformat()
            }
            st.download_button(
                "Download JSON",
                json.dumps(export_data, indent=2),
                file_name=f"bioagent_chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )

        st.markdown("---")

        # Capabilities
        st.markdown("### Capabilities")
        st.markdown("""
        - 🗄️ **11 Databases** (NCBI, UniProt, KEGG...)
        - 🧠 **5 ML/AI Tools** (Pathogenicity, Structure...)
        - 🔬 **Code Execution** (Python, R, Bash)
        - 📊 **Visualization** (Publication figures)
        - ☁️ **Cloud/HPC** (AWS, GCP, Azure, SLURM)
        """)


def render_main_chat():
    """Render the main chat interface."""
    st.markdown("<p class='main-header'>🧬 BioAgent Dashboard</p>", unsafe_allow_html=True)
    st.markdown("<p class='sub-header'>AI-Powered Bioinformatics Assistant</p>", unsafe_allow_html=True)

    st.markdown("---")

    # Initialize agent if needed
    if not st.session_state.initialized:
        with st.spinner("Initializing BioAgent..."):
            success, message = initialize_agent()
            if success:
                st.success("✓ BioAgent ready!")
            else:
                st.error(f"Failed to initialize: {message}")
                st.info("Please ensure ANTHROPIC_API_KEY is set in your environment.")
                return

    # Chat interface
    chat_container = st.container()

    # Display chat history
    with chat_container:
        for msg in st.session_state.messages:
            if msg['role'] == 'user':
                with st.chat_message("user"):
                    st.markdown(msg['content'])
            else:
                with st.chat_message("assistant", avatar="🧬"):
                    st.markdown(msg['content'])

                    # Show tool calls if any
                    if 'tool_calls' in msg and msg['tool_calls']:
                        with st.expander("🔧 Tool Calls", expanded=False):
                            for tool in msg['tool_calls']:
                                st.markdown(f"**{tool['name']}**")
                                if tool.get('input'):
                                    st.code(json.dumps(tool['input'], indent=2), language='json')

    # Input area
    st.markdown("---")

    # Example queries
    with st.expander("💡 Example Queries", expanded=False):
        col1, col2 = st.columns(2)

        examples_col1 = [
            "Get UniProt information for TP53",
            "What pathways involve BRCA1?",
            "Find proteins that interact with MYC",
            "Search PubMed for CRISPR cancer therapy",
        ]

        examples_col2 = [
            "Predict pathogenicity of 17-7577121-G-A",
            "Get AlphaFold structure for P04637",
            "What drugs target EGFR mutations?",
            "Check gnomAD frequency for BRCA1 variants",
        ]

        with col1:
            for ex in examples_col1:
                if st.button(ex, key=f"ex_{ex[:20]}", use_container_width=True):
                    st.session_state.pending_query = ex
                    st.rerun()

        with col2:
            for ex in examples_col2:
                if st.button(ex, key=f"ex_{ex[:20]}", use_container_width=True):
                    st.session_state.pending_query = ex
                    st.rerun()

    # Check for pending query
    pending = st.session_state.get('pending_query', '')
    if pending:
        del st.session_state.pending_query

    # Chat input
    query = st.chat_input("Ask BioAgent anything about bioinformatics...", key="chat_input")

    if pending:
        query = pending

    if query:
        # Add user message
        st.session_state.messages.append({
            'role': 'user',
            'content': query
        })

        # Display user message
        with st.chat_message("user"):
            st.markdown(query)

        # Get response
        with st.chat_message("assistant", avatar="🧬"):
            with st.spinner("Thinking..."):
                try:
                    response = st.session_state.agent.run(query)

                    # Extract tool calls from agent history
                    tool_calls = []
                    if hasattr(st.session_state.agent, 'history'):
                        for msg in st.session_state.agent.history[-10:]:
                            if msg.get('role') == 'assistant':
                                content = msg.get('content', [])
                                if isinstance(content, list):
                                    for block in content:
                                        if isinstance(block, dict) and block.get('type') == 'tool_use':
                                            tool_calls.append({
                                                'name': block.get('name'),
                                                'input': block.get('input')
                                            })

                    st.markdown(response)

                    # Show tool calls
                    if tool_calls:
                        with st.expander("🔧 Tool Calls", expanded=False):
                            for tool in tool_calls:
                                st.markdown(f"**{tool['name']}**")
                                if tool.get('input'):
                                    st.code(json.dumps(tool['input'], indent=2)[:500], language='json')

                    # Save to history
                    st.session_state.messages.append({
                        'role': 'assistant',
                        'content': response,
                        'tool_calls': tool_calls
                    })

                    st.session_state.tool_calls.extend(tool_calls)
                    st.session_state.query_count += 1

                except Exception as e:
                    st.error(f"Error: {str(e)}")
                    st.session_state.messages.append({
                        'role': 'assistant',
                        'content': f"Error: {str(e)}",
                        'tool_calls': []
                    })


def render_tools_page():
    """Render the tools overview page."""
    st.markdown("## 🔧 Available Tools")
    st.markdown("BioAgent has access to 43 tools across 9 categories.")

    st.markdown("---")

    tools_data = {
        "🗄️ Database Queries": {
            "description": "Query 11 major biological databases",
            "tools": [
                ("query_ncbi", "NCBI Gene, PubMed, Nucleotide, Protein"),
                ("query_ensembl", "Genomic annotations, variants"),
                ("query_uniprot", "Protein sequences and annotations"),
                ("query_kegg", "Pathways, genes, compounds"),
                ("query_string", "Protein-protein interactions"),
                ("query_pdb", "3D protein structures"),
                ("query_alphafold", "AI-predicted structures"),
                ("query_interpro", "Protein domains and families"),
                ("query_reactome", "Biological pathways"),
                ("query_go", "Gene Ontology annotations"),
                ("query_gnomad", "Population variant frequencies"),
            ]
        },
        "🧠 ML/AI Predictions": {
            "description": "Machine learning and AI-powered analysis",
            "tools": [
                ("predict_pathogenicity", "Variant pathogenicity (CADD, REVEL, AlphaMissense)"),
                ("predict_structure", "Protein structure prediction"),
                ("predict_drug_response", "Drug sensitivity prediction"),
                ("annotate_cell_types", "Single-cell type annotation"),
                ("discover_biomarkers", "Biomarker discovery pipeline"),
            ]
        },
        "💻 Code Execution": {
            "description": "Run analysis code",
            "tools": [
                ("execute_python", "Execute Python scripts"),
                ("execute_r", "Execute R scripts"),
                ("execute_bash", "Execute shell commands"),
            ]
        },
        "📁 File Operations": {
            "description": "Manage files in workspace",
            "tools": [
                ("read_file", "Read file contents"),
                ("write_file", "Write to files"),
                ("list_files", "List directory contents"),
            ]
        },
        "🔄 Workflow Engines": {
            "description": "Create and run bioinformatics pipelines",
            "tools": [
                ("workflow_create", "Create new workflow"),
                ("workflow_run", "Execute workflow"),
                ("workflow_status", "Check workflow status"),
                ("workflow_outputs", "Get workflow outputs"),
                ("workflow_list", "List workflows"),
                ("workflow_check_engines", "Check available engines"),
            ]
        },
        "☁️ Cloud & HPC": {
            "description": "Scale to cloud computing",
            "tools": [
                ("cloud_submit_job", "Submit cloud job"),
                ("cloud_job_status", "Check job status"),
                ("cloud_job_logs", "Get job logs"),
                ("cloud_cancel_job", "Cancel running job"),
                ("cloud_list_jobs", "List all jobs"),
                ("cloud_estimate_cost", "Estimate job cost"),
            ]
        },
        "📊 Visualization": {
            "description": "Create figures and reports",
            "tools": [
                ("create_plot", "Create publication figures"),
                ("generate_report", "Generate analysis reports"),
                ("create_dashboard", "Create interactive dashboards"),
            ]
        },
        "🧠 Memory System": {
            "description": "Context and artifact management",
            "tools": [
                ("memory_search", "Search past analyses"),
                ("memory_save_artifact", "Save analysis artifacts"),
                ("memory_list_artifacts", "List saved artifacts"),
                ("memory_read_artifact", "Retrieve artifact"),
                ("memory_get_entities", "Get knowledge graph entities"),
            ]
        },
        "🌐 Web Search": {
            "description": "Search documentation and literature",
            "tools": [
                ("web_search", "Search the web"),
            ]
        },
    }

    for category, info in tools_data.items():
        with st.expander(f"{category} ({len(info['tools'])} tools)", expanded=False):
            st.markdown(f"*{info['description']}*")
            st.markdown("")

            for tool_name, tool_desc in info['tools']:
                st.markdown(f"- **`{tool_name}`** - {tool_desc}")


def render_docs_page():
    """Render the documentation page."""
    st.markdown("## 📚 Documentation")

    st.markdown("---")

    tab1, tab2, tab3 = st.tabs(["Quick Start", "Common Queries", "Configuration"])

    with tab1:
        st.markdown("""
        ### Getting Started with BioAgent

        **1. Basic Queries**

        Ask questions in natural language:
        ```
        What is the function of the TP53 gene?
        ```

        **2. Database Lookups**

        Query specific databases:
        ```
        Get UniProt information for human insulin
        ```

        **3. Multi-step Analysis**

        Combine multiple operations:
        ```
        For gene BRCA1:
        1. Get protein info from UniProt
        2. Find all pathways in KEGG
        3. Get interaction partners from STRING
        ```

        **4. Code Execution**

        Run analysis code:
        ```
        Read the file data.csv and calculate summary statistics
        ```

        **5. Predictions**

        Use ML/AI tools:
        ```
        Predict the pathogenicity of variant 17-7577121-G-A
        ```
        """)

    with tab2:
        st.markdown("""
        ### Common Query Patterns

        | Task | Example Query |
        |------|---------------|
        | Gene info | "Get information about TP53 from UniProt" |
        | Pathways | "What pathways involve BRCA1?" |
        | Interactions | "Find proteins that interact with MYC" |
        | Variants | "Check gnomAD frequency for rs121913529" |
        | Structure | "Get AlphaFold structure for P04637" |
        | Literature | "Search PubMed for CRISPR therapy papers" |
        | Pathogenicity | "Predict pathogenicity of chr17:7577121:G>A" |
        | Drug response | "How do EGFR-mutant tumors respond to Erlotinib?" |
        | Analysis | "Analyze expression data in counts.csv" |
        | Visualization | "Create a volcano plot from deg_results.csv" |
        """)

    with tab3:
        st.markdown("""
        ### Configuration

        **Environment Variables**

        Set these in your `.env` file or environment:

        ```bash
        # Required
        ANTHROPIC_API_KEY=sk-ant-your-key-here

        # Recommended
        NCBI_EMAIL=your.email@example.com
        NCBI_API_KEY=your_ncbi_key

        # Optional
        BIOAGENT_MODEL=claude-sonnet-4-20250514
        BIOAGENT_WORKSPACE=/path/to/workspace
        BIOAGENT_VERBOSE=true
        BIOAGENT_AUTO_SAVE=true
        ```

        **Multi-Agent Mode**

        Enable for complex tasks:
        ```bash
        BIOAGENT_MULTI_AGENT=true
        ```

        **Cloud Configuration**

        See `docs/cloud-setup.md` for detailed cloud setup instructions.
        """)


def main():
    """Main application entry point."""
    init_session_state()

    # Sidebar
    render_sidebar()

    # Main content with tabs
    tab1, tab2, tab3 = st.tabs(["💬 Chat", "🔧 Tools", "📚 Docs"])

    with tab1:
        render_main_chat()

    with tab2:
        render_tools_page()

    with tab3:
        render_docs_page()


if __name__ == "__main__":
    main()
