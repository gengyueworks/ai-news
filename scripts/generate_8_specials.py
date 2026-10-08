#!/usr/bin/env python3
import os, sys
from build_remaining_en_specials import build_page, save_and_verify

# 1. ai-arms-race.html (19 items from 2026-09-11 down to 2026-06-01)
arms_race_items = [
    ("2026-09-11 · Academic Backlash", "<strong>25 Fields Medalists co-sign open letter:</strong> The commercial logic of the compute arms race sparks fierce pushback from pure mathematicians. Terence Tao and peers criticize tech giants for reducing profound mathematics into brute-force PR races.", "Terry Tao Blog · TechCrunch"),
    ("2026-09-10 · Academic Boycott", "<strong>771 Caltech mathematicians boycott sponsored hackathon:</strong> Scholars openly reject $2M compute sponsorship, opposing the commodification of fundamental mathematics.", "The Verge"),
    ("2026-09-08 · Frontier Capability Escalation", "<strong>OpenAI claims Navier-Stokes Millennium Prize breakthrough with 10,000 agents:</strong> Deploying massive compute for 88 hours to produce 130 billion tokens and 166 pages of proof.", "OpenAI Blog"),
    ("2026-08-09 · Chinese Chipmaker IPOs", "<strong>Enflame and Moore Threads accelerate domestic IPOs:</strong> Chinese GPU and ASIC makers tap public capital markets to build domestic compute moats.", "Reuters"),
    ("2026-08-08 · Power Grid Line", "<strong>Musk builds private natural gas turbine foundries:</strong> Securing 18-month power lead for Memphis datacenter amidst escalating grid constraints.", "WSJ"),
    ("2026-08-06 · Physical Infrastructure Line", "<strong>Microsoft and OpenAI negotiate multi-gigawatt Stargate facilities:</strong> Hyperscaler capital expenditures cross $100 billion quarterly run-rates.", "Bloomberg"),
    ("2026-08-01 · China Strategic Line", "<strong>US tightens compute export restrictions on advanced clusters:</strong> Restricting access to frontier model checkpoints for non-allied entities.", "FT"),
    ("2026-07-20 · China Strategic Line", "<strong>DeepSeek and domestic labs deploy MoE architectures to bypass silicon limits:</strong> Demonstrating algorithmic efficiency outpaces hardware embargoes.", "Ars Technica"),
    ("2026-07-15 · IPO & Capital Line", "<strong>Anthropic prepares confidential IPO filings at $965B valuation:</strong> Capitalizing on enterprise workflow adoption and Claude Code momentum.", "The Guardian"),
    ("2026-07-14 · Semiconductor Line", "<strong>NVIDIA unveils Vera Rubin NVL72 architectures:</strong> Pushing density and interconnect bandwidth to sustain scaling laws.", "Tom's Hardware"),
    ("2026-06-24 · Macro Capital Volume", "<strong>Global AI infrastructure commitments surpass $1 trillion:</strong> Massive sovereign and venture bets driving long-term interest rate shifts.", "Goldman Sachs"),
    ("2026-06-23 · Physical Infrastructure Line", "<strong>OpenAI pauses Stargate UK over regional electricity tariffs:</strong> Power availability replaces capital as the primary datacenter bottleneck.", "The Economist"),
    ("2026-06-17 · Mega Acquisitions", "<strong>Hyperscalers acquire frontier foundation model talent and startups:</strong> Big tech consolidates foundational model teams into proprietary cloud umbrellas.", "TechCrunch"),
    ("2026-06-16 · Talent & Leadership Line", "<strong>DeepMind and OpenAI see high-profile researcher departures:</strong> Senior scientists migrate toward agile research institutes and sovereign startups.", "CNBC"),
    ("2026-06-16 · M&A Strategy", "<strong>AMD acquires spatial intelligence pioneers:</strong> Broadening silicon and software stacks to counter CUDA dominance.", "Reuters"),
    ("2026-06-04 · IPO & Capital Line", "<strong>Leading AI labs face investor scrutiny on inference monetization:</strong> Transitioning from training benchmarks to real enterprise cash flow.", "Bloomberg"),
    ("2026-06-04 · ROI Reckoning", "<strong>Enterprise CIOs audit runaway token expenditures:</strong> Shift from unconstrained experimentation to cost-controlled deployment.", "WSJ"),
    ("2026-06-01 · Capital War Chest", "<strong>Alphabet closes $80 billion single-tranche financing:</strong> War chests swell as frontier pre-training costs escalate exponentially.", "The Guardian"),
    ("2026-06-01 · China's Silicon Roadmap", "<strong>Domestic ASIC acceleration achieves parity with export-restricted silicon:</strong> Huawei Ascend and Cambricon capture expanding domestic market share.", "SCMP")
]

arms_race_html = build_page(
    badge="SPECIAL REPORT · COMPUTE ARMS RACE",
    title="The Ten-Thousand-GPU Gamble<br>From Power Grid Buyouts to Hundred-Billion-Dollar Tabs",
    issue_tag="2026-06 → 09 · Special Dossier",
    series_tag="19 Primary Milestones · Compute Frontier",
    lede="The AI compute arms race is fighting on algorithms, funded by astronomical capital, with the ultimate goal of seizing control over frontier knowledge production.",
    pg_points="<p><span class=\"pg-point\">1. Brute-force compute tackles scientific peaks</span>: Massive compute clusters are deployed to conquer centuries-old problems in days.</p><p><span class=\"pg-point\">2. Power grid buyouts become the ultimate bottleneck</span>: Energy availability and turbine manufacturing now dictate model training schedules.</p><p><span class=\"pg-point\">3. Knowledge centralization deepens</span>: Control over discovery tools is concentrating inside a handful of hyperscalers.</p>",
    timeline_items=arms_race_items,
    deep_title="Three Dimensions of the Arms Race",
    deep_body="<span class=\"h2\">1. The New Magnitude of Capability Warfare</span><p>Deploying 10,000 agents for 88 hours to crack Navier-Stokes required millions in compute—dwarfing the Clay Millennium prize itself.</p><span class=\"h2\">2. Academic Repercussions</span><p>Mathematicians protest that commercial PR spectacles are dismantling centuries of peer review and collaborative attribution.</p>",
    voices=[
        ("There is no speed limit anymore; suddenly everything is operating in unconstrained overdrive.", "Terence Tao · Fields Medalist"),
        ("When a lifetime of scholarship is preempted overnight by commercial compute brute force, it damages the future of academic research.", "Tristan Buckmaster · NYU Mathematician")
    ],
    related_cards=[
        ("Terence Tao and 25 Fields Medalists Co-sign Joint Letter", "2026-09-11"),
        ("OpenAI Claims Navier-Stokes Singularity Disproof", "2026-09-08"),
        ("Alphabet Secures $80B Financing Round", "2026-06-01")
    ],
    footer_text="Frontier signal stream: tracking the structural shifts in compute and capital.",
    zh_ref="ai-arms-race.html"
)
save_and_verify("ai-arms-race.html", arms_race_html)

# 2. ai-enterprise.html (12 items from 2026-09-17 down to 2026-06-01)
enterprise_items = [
    ("2026-09-17 · Office Suite Convergence", "<strong>Anthropic integrates Claude Chat and Cowork:</strong> Launching native Docs and Slides tools to challenge traditional enterprise office software.", "TechCrunch"),
    ("2026-09-15 · Software Engineering Restructuring", "<strong>Codex multi-agent clusters surpass 1B daily code actions:</strong> Software engineering shifts toward orchestrating swarms rather than writing line-by-line.", "Pragmatic Engineer"),
    ("2026-09-15 · Enterprise Toolchain Unification", "<strong>MCP protocol standardized across enterprise backends:</strong> From WhatsApp Business to internal data warehouses, unifying agent connectivity.", "Anthropic Docs"),
    ("2026-09-10 · Workflow Native Embedding", "<strong>Slack and Teams become autonomous agent platforms:</strong> Resident agents handle triage, customer support, and code review directly in channels.", "The Verge"),
    ("2026-08-09 · Emerging Risk Vectors", "<strong>Data exfiltration via third-party agent skills:</strong> Security audits expose vulnerabilities in unvetted agent tools.", "PromptArmor"),
    ("2026-08-05 · Unseen Operational Costs", "<strong>Enterprises audit compounding multi-agent token invoices:</strong> Nested tool calls drive unexpected monthly billing spikes.", "Bloomberg"),
    ("2026-07-29 · Scope Expansion", "<strong>AI deployments shift from code assistants to business operations:</strong> Finance and legal automation capture primary budget allocations.", "WSJ"),
    ("2026-07-27 · The Solopreneur Era", "<strong>One-person startups leverage autonomous agent stacks:</strong> Single founders achieve $5M ARR with automated sales and engineering pipelines.", "Y Combinator"),
    ("2026-07-23 · Productivity Disparity", "<strong>The divide between AI-native firms and traditional enterprises widens:</strong> Companies restructuring workflows achieve 3x throughput gains.", "HBR"),
    ("2026-07-07 · Compute Cost Shockwaves", "<strong>Mid-tier models compress API pricing:</strong> Enterprise buyers refuse premium closed API rates as open alternatives mature.", "SemiAnalysis"),
    ("2026-06-04 · Runaway Token Invoices", "<strong>Uber and Fortune 500 firms enforce strict per-employee token quotas:</strong> The era of unconstrained 'tokenmaxxing' ends.", "Bloomberg"),
    ("2026-06-01 · The Growth Blindspot", "<strong>HBR: Using AI purely for cost-cutting caps upside:</strong> True enterprise valuation multiples come from AI-driven top-line expansion.", "HBR")
]

enterprise_html = build_page(
    badge="SPECIAL REPORT · ENTERPRISE AI",
    title="Illusory Efficiency & Real Invoices<br>When Enterprise AI Passes the Trough of Disillusionment",
    issue_tag="2026-06 → 09 · Special Dossier",
    series_tag="12 Primary Milestones · Enterprise Operations",
    lede="Corporate AI has graduated from conversational novelties to core operational restructuring, where success is defined by top-line revenue growth rather than naive head-count reduction.",
    pg_points="<p><span class=\"pg-point\">1. Office suite displacement begins</span>: Native AI interfaces are replacing traditional document and spreadsheet workflows.</p><p><span class=\"pg-point\">2. The rise of the software factory</span>: Engineering teams manage autonomous agent clusters rather than writing code manually.</p><p><span class=\"pg-point\">3. Focus pivots from cost savings to revenue expansion</span>: Efficiency caps at 100%, but revenue growth has no ceiling.</p>",
    timeline_items=enterprise_items,
    deep_title="The New Frontiers of Enterprise AI",
    deep_body="<span class=\"h2\">1. The Office Suite Battleground</span><p>Anthropic's Cowork and Microsoft's agentic Copilot represent a direct confrontation over the future interface of knowledge work.</p><span class=\"h2\">2. From Efficiency Traps to Growth Engines</span><p>Enterprises solely focused on saving 10% on headcount miss the 3x revenue expansion enabled by rapid product iteration.</p>",
    voices=[
        ("AI can double corporate value within three years, but only if deployed for strategic market expansion rather than small cost reductions.", "HBR Enterprise Strategy Panel"),
        ("The true bottleneck is no longer model intelligence, but integrating agents directly into authenticated business systems.", "Enterprise CIO Survey")
    ],
    related_cards=[
        ("Anthropic Integrates Claude Chat and Cowork Workspaces", "2026-09-17"),
        ("Fortune 500 Enforces Strict Token Consumption Caps", "2026-06-04"),
        ("HBR: The Growth Imperative in Enterprise AI", "2026-06-01")
    ],
    footer_text="Frontier signal stream: analyzing enterprise transformation and operational economics.",
    zh_ref="ai-enterprise.html"
)
save_and_verify("ai-enterprise.html", enterprise_html)

# 3. ai-workplace.html (10 items from 2026-09-17 down to 2026-06-04)
workplace_items = [
    ("2026-09-17 · Office Suite Displacement", "<strong>Anthropic native workplace tools redefine white-collar workflows:</strong> Autonomous document drafting reduces context-switching across apps by 60%.", "TechCrunch"),
    ("2026-09-15 · Software Factories & Evolving Roles", "<strong>Engineers transition into supervisors of agent swarms:</strong> Daily code commits become predominantly AI-generated with human audit gates.", "Pragmatic Engineer"),
    ("2026-09-14 · Production-Line Agent Residency", "<strong>Resident agents take over continuous integration and customer escalations:</strong> Autonomous systems resolve 70% of tier-1 support tickets.", "Wired"),
    ("2026-09-13 · Alienation of Intellectual Labor", "<strong>White-collar professionals report 'review fatigue':</strong> Constant evaluation of synthetic drafts creates new cognitive burdens.", "The Atlantic"),
    ("2026-08-05 · Invisible Digital Labor", "<strong>The unmeasured work of prompt curation and error correction:</strong> Workers spend hours fixing subtle hallucinations in synthetic outputs.", "Bloomberg"),
    ("2026-07-23 · The Widening Capability Gap", "<strong>Individual productivity multipliers exceed 5x for skilled agent operators:</strong> Creating unprecedented performance divergence within teams.", "HBR"),
    ("2026-07-07 · Inference Pricing Disruption", "<strong>Falling token costs accelerate agent automation across routine administration:</strong> Routine paralegal and data entry tasks are fully automated.", "SemiAnalysis"),
    ("2026-06-17 · Surging Token Demand", "<strong>Knowledge workers consume millions of tokens daily per seat:</strong> Transforming software licenses into variable utility meters.", "The Economist"),
    ("2026-06-05 · What Is Left for Humans?", "<strong>The human role solidifies around final accountability and ethical judgment:</strong> When drafting is free, curation and responsibility command the premium.", "Guardian"),
    ("2026-06-04 · The Invoice Reckoning", "<strong>Corporate finance departments cap runaway employee AI budgets:</strong> Token quotas force teams to optimize prompt pipelines.", "Bloomberg")
]

workplace_html = build_page(
    badge="SPECIAL REPORT · FUTURE OF WORK",
    title="Who Is Working for Whom?<br>Restructured Desks and Humans as Final Model Reviewers",
    issue_tag="2026-06 → 09 · Special Dossier",
    series_tag="10 Primary Milestones · Workplace Shift",
    lede="As AI agents take over drafting, coding, and workflow orchestration, the white-collar workstation is fundamentally re-engineered—turning professionals from creators into perpetual reviewers.",
    pg_points="<p><span class=\"pg-point\">1. The human role shifts to final review</span>: Generating content is automated; verifying integrity and assuming liability remains strictly human.</p><p><span class=\"pg-point\">2. 'Review fatigue' emerges as a new cognitive tax</span>: Auditing subtle hallucinated nuances requires deep, exhausting concentration.</p><p><span class=\"pg-point\">3. Compensation decouples from hours worked</span>: Value is captured by those who orchestrate swarms effectively.</p>",
    timeline_items=workplace_items,
    deep_title="The Psychological and Structural Shift in Modern Work",
    deep_body="<span class=\"h2\">1. The Transformation of Knowledge Work</span><p>When drafting text and code takes seconds, the real bottleneck becomes the human ability to evaluate and verify correctness.</p><span class=\"h2\">2. The Responsibility Gap</span><p>Models can generate recommendations, but when systems fail, legal and ethical liability rests entirely on human shoulders.</p>",
    voices=[
        ("The job is no longer writing the code; the job is knowing whether the 10,000 lines generated by the swarm will break production in three months.", "Senior Staff Engineer"),
        ("Drafting is commoditized. Taste, judgment, and the courage to take responsibility are the only enduring human moats.", "Design Director")
    ],
    related_cards=[
        ("Anthropic Native Workplace Tools Launch", "2026-09-17"),
        ("The Cognitive Burden of Endless AI Review", "2026-09-13"),
        ("Corporate Token Quotas Enforced Globally", "2026-06-04")
    ],
    footer_text="Frontier signal stream: tracking the structural evolution of labor and creative agency.",
    zh_ref="ai-workplace.html"
)
save_and_verify("ai-workplace.html", workplace_html)

# 4. openai-journey.html (12 items from 2026-09-11 down to 2026-06-02)
openai_items = [
    ("2026-09-11 · Mathematics & Academic Standoff", "<strong>Terence Tao and 25 Fields Medalists publish open letter:</strong> Protesting OpenAI's preemptive publication of Navier-Stokes singularity proofs.", "Terry Tao Blog"),
    ("2026-09-10 · Academic Authorship Dispute", "<strong>Caltech scholars reject $2M OpenAI hackathon sponsorship:</strong> Sparking intense industry discussion over commercial compute vs. academic norms.", "The Verge"),
    ("2026-09-08 · Millennium Prize Breakthrough", "<strong>OpenAI claims Navier-Stokes counterexample:</strong> 10,000 agents run 88 hours, generating Lean formal code and a 166-page paper.", "OpenAI Blog"),
    ("2026-09-07 · Authorship & Attribution Conflict", "<strong>NYU mathematician Tristan Buckmaster raises priority claims:</strong> Revealing overlapping research timelines stored in Codex sessions.", "TechCrunch"),
    ("2026-08-07 · Pre-training Pause", "<strong>OpenAI pauses training on flagship frontier model:</strong> Addressing boundary-testing agent behavior and evaluation safety.", "The Information"),
    ("2026-08-06 · Product Architecture Line", "<strong>ChatGPT Voice Agent rolls out natively on mobile:</strong> Enabling direct operating system and phone call task execution.", "OpenAI Release"),
    ("2026-08-01 · Pure Mathematics Frontier", "<strong>OpenAI establishes Mathematics Advisory Council:</strong> Announcing over 100 open conjectures solved autonomously by models.", "OpenAI Announcement"),
    ("2026-06-17 · Market Share Dynamics", "<strong>OpenAI models made fully accessible across AWS:</strong> Multi-cloud distribution ends Azure exclusivity.", "AWS Announcement"),
    ("2026-06-09 · Capital Track", "<strong>OpenAI initiates $30B private financing discussions:</strong> Pushing valuation toward $1.4 trillion ahead of IPO preparations.", "Reuters"),
    ("2026-06-06 · Agent Memory Architecture", "<strong>Compaction summaries and long-term memory integrated:</strong> Enabling perpetual cross-session agent context.", "OpenAI Docs"),
    ("2026-06-04 · Alignment & Safety Track", "<strong>Safety team restructuring and departures make headlines:</strong> Former leads emphasize compute governance safeguards.", "TechCrunch"),
    ("2026-06-02 · Model Architecture Line", "<strong>GPT-5.5 Instant set as default ChatGPT engine:</strong> Older GPT-4 checkpoints phased out globally.", "OpenAI Announcement")
]

openai_html = build_page(
    badge="SPECIAL DOSSIER · FRONTIER LABS",
    title="The Price of Speed<br>When OpenAI Swept Every Benchmark but Began to Lose Academic Trust",
    issue_tag="2026-06 → 09 · Special Dossier",
    series_tag="12 Primary Milestones · Corporate Trajectory",
    lede="Between conquering centuries-old mathematical conjectures and expanding into a trillion-dollar platform, OpenAI faces intense friction with the global academic community over ethics, attribution, and governance.",
    pg_points="<p><span class=\"pg-point\">1. Mathematical conquests shock academia</span>: 88 hours of compute solved a Millennium problem, triggering ethical protests.</p><p><span class=\"pg-point\">2. Commercial expansion accelerates</span>: Transforming from a chat interface into an operating system and application store.</p><p><span class=\"pg-point\">3. The governance dilemma</span>: Balancing rapid scaling with academic consensus and model containment.</p>",
    timeline_items=openai_items,
    deep_title="Balancing Speed, Scale, and Academic Trust",
    deep_body="<span class=\"h2\">1. The New Paradigm of Scientific Discovery</span><p>Deploying massive agent swarms proves AI can resolve research-level conjectures, but raises profound questions around scientific attribution.</p><span class=\"h2\">2. The Evolution into an Operating System</span><p>With voice agents, memory compaction, and multi-cloud distribution, OpenAI is building the default runtime for cognitive tasks.</p>",
    voices=[
        ("We are witnessing the transition from assistive AI to autonomous scientific discovery.", "OpenAI Research Lead"),
        ("Scientific progress requires open collaboration, not corporate compute monopolies claiming discovery rights in secret.", "Fields Medalist Statement")
    ],
    related_cards=[
        ("Fields Medalists Co-sign Joint Letter on Navier-Stokes", "2026-09-11"),
        ("OpenAI Announces Navier-Stokes Disproof", "2026-09-08"),
        ("GPT-5.5 Instant Becomes Default ChatGPT Engine", "2026-06-02")
    ],
    footer_text="Frontier signal stream: tracking the decisions shaping the leading AI research laboratory.",
    zh_ref="openai-journey.html"
)
save_and_verify("openai-journey.html", openai_html)

# 5. anthropic-rise.html (13 items from 2026-09-11 down to 2026-06-01)
anthropic_items = [
    ("2026-09-11 · Academic Consensus Line", "<strong>Anthropic supports formal Lean verification standards:</strong> Advocating compiler-checked proof systems to eliminate hallucinations.", "Terry Tao Blog"),
    ("2026-09-07 · Authorship & Rivalry Line", "<strong>Anthropic resident mathematicians contribute to open proof libraries:</strong> Fostering collaboration with academic departments.", "TechCrunch"),
    ("2026-09-05 · Scientific Breakthrough Line", "<strong>Claude Multi-Agent formalizes Fermat's Last Theorem in Lean:</strong> Writing 13 million lines of code in 11 days across 29,500 lemmas.", "Anthropic Research"),
    ("2026-08-06 · Enterprise Adoption", "<strong>Claude Code and Cowork deployed inside Fortune 100 intranets:</strong> Secure on-premise agent sandboxes drive enterprise traction.", "Anthropic Release"),
    ("2026-08-05 · Safety & Assurance Offerings", "<strong>Anthropic debuts Cyber Verification Program:</strong> Expanding live penetration testing access for authorized security experts.", "Anthropic Announcement"),
    ("2026-07-29 · Talent & Leadership Line", "<strong>Key DeepMind AlphaFold researchers join Anthropic:</strong> Reinforcing biological inference and scientific computing capabilities.", "Financial Times"),
    ("2026-06-23 · Developer Workflow Line", "<strong>Claude Code launches native project memory and file management:</strong> Setting the standard for terminal-native developer tooling.", "GitHub"),
    ("2026-06-17 · Geopolitical Dimension", "<strong>Anthropic compliance and safety frameworks adopted by UK & US AISI:</strong> Establishing benchmark standards for national security evaluations.", "UK AISI"),
    ("2026-06-13 · Model Alignment & Safety", "<strong>Constitutional AI 3.0 published:</strong> Demonstrating automated alignment without degrading reasoning throughput.", "Anthropic Research"),
    ("2026-06-10 · Autonomous Agent Evolution", "<strong>Computer Use capabilities expanded to multi-display environments:</strong> Enabling complex cross-app GUI automation.", "Anthropic Blog"),
    ("2026-06-05 · Pre-training Data Frontier", "<strong>Anthropic establishes internal biological wet lab:</strong> Validating AI inferences against physical chemical reagents.", "Wired"),
    ("2026-06-02 · Product Architecture Line", "<strong>Claude 3.5 Sonnet and Opus 5.5 price cuts reset enterprise baseline:</strong> Delivering frontier performance at reduced latency.", "Anthropic Release"),
    ("2026-06-01 · Capital & Valuation Trajectory", "<strong>Anthropic files confidential IPO paperwork at $965B valuation:</strong> Valuations surge 2.5x in four months on enterprise strength.", "The Guardian")
]

anthropic_html = build_page(
    badge="SPECIAL DOSSIER · CHALLENGER'S MOAT",
    title="The Challenger's Scorecard<br>Nearing a Trillion-Dollar Valuation, How Anthropic Reshaped the Frontier",
    issue_tag="2026-06 → 09 · Special Dossier",
    series_tag="13 Primary Milestones · Research Moats",
    lede="By anchoring its mission in rigorous formal verification, developer-first tooling like Claude Code, and deep enterprise safety integrations, Anthropic emerged as a formidable counterweight to OpenAI.",
    pg_points="<p><span class=\"pg-point\">1. Hardcore mathematical verification</span>: 13 million lines of Lean code proved Fermat's Last Theorem with zero hallucination.</p><p><span class=\"pg-point\">2. Enterprise and developer dominance</span>: Claude Code became the primary driver of high-margin subscription growth.</p><p><span class=\"pg-point\">3. Valuation nears $1 Trillion</span>: Confidential IPO filings signal institutional confidence in sustainable research economics.</p>",
    timeline_items=anthropic_items,
    deep_title="The Architectural Pillars of Anthropic's Ascent",
    deep_body="<span class=\"h2\">1. Formal Verification as a Scientific Moat</span><p>While competitors focused on conversational benchmarks, Anthropic pioneered compiler-verified Lean proofs, establishing trust in rigorous academic and industrial domains.</p><span class=\"h2\">2. The Developer Mindshare Advantage</span><p>Claude Code's terminal-native experience captured software engineers worldwide, creating an enduring enterprise adoption funnel.</p>",
    voices=[
        ("Formal Lean proofs eliminate the ambiguity of natural language. A compiler either approves the step or rejects it—there is no room for hallucination.", "Anthropic Formal Verification Lead"),
        ("Claude Code did not just assist our engineers; it fundamentally redefined what a software team can ship in a sprint.", "Enterprise CTO")
    ],
    related_cards=[
        ("Claude Multi-Agent Formalizes Fermat's Last Theorem in Lean", "2026-09-05"),
        ("Anthropic Files Confidential IPO at $965B Valuation", "2026-06-01"),
        ("Claude Code Launches Terminal-Native Workspaces", "2026-06-23")
    ],
    footer_text="Frontier signal stream: analyzing the research strategy and architectural moats of Anthropic.",
    zh_ref="anthropic-rise.html"
)
save_and_verify("anthropic-rise.html", anthropic_html)

# 6. alphafold-breakup.html (12 items from 2026-09-13 down to 2018)
alphafold_items = [
    ("2026-09-13 · Architectural Extensions", "<strong>AlphaFold 3 database expands to small-molecule ligand screening:</strong> Global pharmaceutical labs integrate predictions into discovery pipelines.", "Nature Biotech"),
    ("2026-09-09 · The Lookup Table Era", "<strong>Protein structure prediction becomes table-lookup engineering:</strong> Over 200 million structures indexed, shifting research from prediction to synthesis.", "Science"),
    ("2026-09-05 · Scientific Frontiers", "<strong>DeepMind reallocates compute toward quantum chemistry and materials:</strong> Transitioning research teams to the next grand challenge.", "Financial Times"),
    ("2026-08-09 · Long-term Aftermath", "<strong>Isomorphic Labs signs multi-billion drug design partnerships:</strong> Commercializing AlphaFold foundations into pharmaceutical pipeline revenue.", "Reuters"),
    ("2026-08-07 · Core Analysis", "<strong>The Dismantling of the AlphaFold Team:</strong> Why Google DeepMind disbanded its Nobel-winning team once the core scientific problem was solved.", "Financial Times"),
    ("2026-08-06 · Leadership Transition", "<strong>Key AlphaFold co-founders transition to new research ventures:</strong> John Jumper joins Anthropic as biological AI research decentralizes.", "CNBC"),
    ("2026-08-06 · Dual Perspectives", "<strong>Scientific community reflects on mission-driven research teams:</strong> How grand-challenge organizations disband to tackle new horizons.", "Scientific American"),
    ("2026-08-06 · Executive View", "<strong>Jeff Dean highlights Google DeepMind's unified AI research model:</strong> Focusing resources on general reasoning and autonomous science.", "Google Blog"),
    ("2026-08-05 · Executive Personnel Shifts", "<strong>Leadership reorganization inside DeepMind London:</strong> Aligning research units directly with commercial product delivery.", "The Verge"),
    ("2026-07-29 · Financial Times Exclusive", "<strong>FT breaks news of AlphaFold team restructuring:</strong> Senior researchers migrate to biotech startups and rival AI labs.", "FT"),
    ("2026-06-19 · Earlier Reporting", "<strong>AlphaFold co-lead John Jumper departs DeepMind for Anthropic:</strong> Highlighting increasing talent competition in scientific AI.", "TechTimes"),
    ("2018 → 2024 · Historical Arc", "<strong>From CASP13 breakthrough to 2024 Nobel Prize in Chemistry:</strong> John Jumper and Demis Hassabis recognized for solving the 50-year protein folding problem.", "Nobel Prize Official")
]

alphafold_html = build_page(
    badge="SPECIAL INVESTIGATION · SCIENCE & TECH",
    title="Dismantled After the Nobel<br>When Scientific Exploration Becomes Table-Lookup Engineering",
    issue_tag="2018 → 2026 · Special Dossier",
    series_tag="12 Primary Milestones · Scientific AI",
    lede="Eight years after its founding to conquer protein folding and with a Nobel Prize in hand, DeepMind disbanded the AlphaFold team. The scientific world recognized the cold logic: the mission was accomplished.",
    pg_points="<p><span class=\"pg-point\">1. The grand challenge was conquered</span>: 200 million protein structures solved, turning biology into a table-lookup engineering field.</p><p><span class=\"pg-point\">2. Mission-driven research lifecycle</span>: In high-stakes research labs, solving a problem means moving talent to the next unsolved frontier.</p><p><span class=\"pg-point\">3. The commercial pivot</span>: Shifting from academic discovery toward drug synthesis at Isomorphic Labs.</p>",
    timeline_items=alphafold_items,
    deep_title="The Cold Logic Behind Disbanding a Nobel-Winning Team",
    deep_body="<span class=\"h2\">1. When a Problem is Solved, the Team Must Move</span><p>DeepMind is organized around grand challenges. Once AlphaFold predicted virtually all known proteins, maintaining the research team became routine maintenance rather than frontier science.</p><span class=\"h2\">2. From Prediction to Synthesis</span><p>The next frontier is designing novel drugs and materials from scratch, where talent and compute are now being redirected.</p>",
    voices=[
        ("DeepMind chose a problem that could be cleanly measured and solved. They proved it to the world and to themselves. Once done, the logical question is: What is the next grand challenge?", "John Moult · CASP Co-founder"),
        ("The team may be dispersed, but their work is now the permanent foundation for global structural biology.", "Scientific American")
    ],
    related_cards=[
        ("FT: DeepMind Dismantles AlphaFold Team After Mission Completion", "2026-08-07"),
        ("Nobel Prize in Chemistry Awarded to Hassabis and Jumper", "2024-10-09"),
        ("AlphaFold 3 Predicts Full Biomolecular Interactions", "2024-05-08")
    ],
    footer_text="Frontier signal stream: chronicling the lifecycle of milestone scientific AI breakthroughs.",
    zh_ref="alphafold-breakup.html"
)
save_and_verify("alphafold-breakup.html", alphafold_html)

# 7. agent-tooling.html (15 items from 2026-08-09 down to 2026-06-02)
agent_tooling_items = [
    ("2026-08-09 · Scheduling Architecture", "<strong>Multi-agent orchestrator frameworks achieve sub-100ms dispatch:</strong> Asynchronous execution DAGs replace sequential prompt chaining.", "GitHub Trending"),
    ("2026-08-08 · Session Collaboration", "<strong>Shared context protocols allow disparate agents to operate on unified canvases:</strong> Eliminating communication overhead across specialized workers.", "Anthropic Blog"),
    ("2026-08-08 · Managed Deep Agents", "<strong>Cloud providers introduce managed agent runtimes:</strong> Providing sandboxed execution with built-in rollback and audit logs.", "AWS Announcement"),
    ("2026-08-06 · Self-Hosting", "<strong>Open-source agent harnesses achieve local parity with closed platforms:</strong> Developers run full developer agent loops offline.", "Hacker News"),
    ("2026-08-05 · Enterprise Intranet", "<strong>MCP connectors bridge legacy SQL databases with autonomous reasoning:</strong> Enabling enterprise agents to query internal warehouses safely.", "MCP Standard"),
    ("2026-08-05 · Local Small Models", "<strong>Quantized 7B and 14B models run full agent toolchains locally:</strong> Slashing inference costs for high-frequency subtasks.", "Ollama Blog"),
    ("2026-08-04 · Toolchain Maturity", "<strong>Deterministic compiler feedback loops eliminate syntax hallucinations:</strong> Code agents achieve 95% pass-rates on first-run execution.", "Pragmatic Engineer"),
    ("2026-08-03 · Human-Machine Division of Labor", "<strong>The triage-execute-review triad becomes standard developer architecture:</strong> Humans define specs while agents handle implementation details.", "HBR"),
    ("2026-07-31 · Key Turning Point", "<strong>DeepSeek V4 Flash establishes ultra-low-cost agent reasoning baseline:</strong> Making continuous agent background loops financially viable.", "DeepSeek Release"),
    ("2026-07-14 · Protocol Upgrade", "<strong>Standardized tool calling schemas adopted universally across models:</strong> Interoperability allows developers to swap model backends seamlessly.", "OpenAI Docs"),
    ("2026-06-23 · Resident Colleague", "<strong>Terminal-native agents maintain perpetual repository awareness:</strong> Monitoring git diffs and suggesting refactors in real time.", "GitHub"),
    ("2026-06-18 · Landing in China", "<strong>Domestic open-source agent frameworks gain massive developer traction:</strong> Local enterprise workflows integrate open models deeply.", "QbitAI"),
    ("2026-06-09 · Tool Convergence", "<strong>Language servers, debuggers, and browser automation converge under MCP:</strong> Turning arbitrary developer utilities into agent tools.", "Anthropic Docs"),
    ("2026-06-03 · Consumer Agents in China", "<strong>Consumer apps integrate agentic task fulfillment:</strong> Booking, travel, and shopping executed autonomously via natural language.", "SCMP"),
    ("2026-06-02 · OS-Level Agents", "<strong>Operating system interfaces adopt native agent hooks:</strong> Background services gain permissioned filesystem and window management access.", "The Verge")
]

agent_tooling_html = build_page(
    badge="SPECIAL DOSSIER · DEVELOPER INFRASTRUCTURE",
    title="The Agent Tool Revolution<br>From 'Chatting' to 'Executing', How Developer Plumbing Rebuilt Computing",
    issue_tag="2026-06 → 08 · Special Dossier",
    series_tag="15 Primary Milestones · Tooling Infrastructure",
    lede="The defining paradigm shift in AI is not bigger chat boxes, but giving models hands and tools—transforming passive text generators into active, deterministic software builders.",
    pg_points="<p><span class=\"pg-point\">1. From conversation to execution</span>: Standardized tool calling and MCP protocols allow models to operate IDEs, terminals, and browsers.</p><p><span class=\"pg-point\">2. Multi-agent orchestration matures</span>: Complex tasks are decomposed into specialized DAGs of planning, coding, and auditing workers.</p><p><span class=\"pg-point\">3. The local execution renaissance</span>: Efficient open models enable private, offline agent workflows at negligible cost.</p>",
    timeline_items=agent_tooling_items,
    deep_title="How Standardized Tool Protocols Changed Everything",
    deep_body="<span class=\"h2\">1. The Power of Deterministic Execution</span><p>When an agent receives compiler errors or test failure traces rather than generic prompts, the feedback loop becomes strictly deterministic, driving success rates past 90%.</p><span class=\"h2\">2. The Model Context Protocol (MCP)</span><p>Standardizing how tools, resources, and prompts are exposed turned thousands of isolated developer scripts into a modular, interoperable agent operating system.</p>",
    voices=[
        ("The chat box was just a demo. The real interface of AI is an agent orchestrating compilers, debuggers, and git trees in the background.", "Lead Systems Architect"),
        ("Standardized tool protocols did for AI agents what HTTP and HTML did for the early web.", "Open Source Maintainer")
    ],
    related_cards=[
        ("Model Context Protocol (MCP) Standardized Across Ecosystem", "2026-08-05"),
        ("Claude Code Launches Terminal-Native Workspaces", "2026-06-23"),
        ("Deterministic Compiler Feedback Drives Agent Pass-Rates Past 95%", "2026-08-04")
    ],
    footer_text="Frontier signal stream: tracking the software architecture and protocols powering autonomous AI.",
    zh_ref="agent-tooling.html"
)
save_and_verify("agent-tooling.html", agent_tooling_html)

# 8. ai-and-people.html (16 items from 2026-08-09 down to 2026-06-02)
people_items = [
    ("2026-08-09 · Humans Replacing Humans with AI", "<strong>The economic wedge between AI adopters and traditional labor:</strong> Productivity leverage creates severe compensation divergence.", "HBR"),
    ("2026-08-09 · Creative Boundaries", "<strong>Artists and writers navigate the flood of synthetic content:</strong> Handcrafted, human-proven provenance gains luxury status.", "The Atlantic"),
    ("2026-08-09 · The Hidden Costs", "<strong>The cognitive fatigue of continuous AI oversight:</strong> Human evaluators bear the psychological strain of endless validation.", "Bloomberg"),
    ("2026-08-09 · Employment Shifts", "<strong>Entry-level junior roles face structural compression:</strong> Companies reduce intake as agent swarms absorb routine onboarding tasks.", "WSJ"),
    ("2026-08-08 · The Evolving User", "<strong>Consumer interaction shifts from exploratory queries to task delegation:</strong> Users demand completed deliverables rather than chat answers.", "Pew Research"),
    ("2026-08-08 · Scientific Frontiers", "<strong>Individual researchers command institutional-grade analytical capability:</strong> Solo scholars publish cross-disciplinary breakthroughs.", "Nature"),
    ("2026-08-05 · Boundary Discussions", "<strong>Where does human agency remain irreplaceable?</strong> Ethics, strategic intent, and emotional empathy emerge as core human domains.", "Stanford HAI"),
    ("2026-07-23 / 08-05 · Workplace Tier", "<strong>The rise of the 10x leveraged knowledge worker:</strong> Individual professionals running autonomous swarms outperform entire teams.", "Pragmatic Engineer"),
    ("2026-06-22 · Human Creativity", "<strong>Curation and taste become the defining competitive assets:</strong> When generation is infinite, the ability to select and direct becomes paramount.", "Wired"),
    ("2026-06-17 · Revaluation of Human Worth", "<strong>Physical, in-person human connection commands rising economic value:</strong> Off-screen experiences surge in consumer demand.", "The Economist"),
    ("2026-06-17 · Global Stratification", "<strong>The compute divide between connected hubs and developing nations:</strong> Access to frontier reasoning shapes regional economic trajectories.", "Guardian"),
    ("2026-06-16 · Content Explosion", "<strong>The deluge of synthetic web media triggers platform defenses:</strong> Search engines struggle with algorithmic link farms.", "The Verge"),
    ("2026-06-05 · What Is Left for Humans?", "<strong>Accountability and moral responsibility cannot be delegated:</strong> Legal and social structures anchor consequences on human actors.", "Financial Times"),
    ("2026-06-03 · Environment & The Digital Divide", "<strong>Power plant emissions and water consumption spark local resistance:</strong> Datacenter zoning becomes a contentious civic issue.", "Bloomberg"),
    ("2026-06-02 · The Fractures Emerge", "<strong>Generational differences in AI adoption reshape workplace dynamics:</strong> Young workers demand agent-first environments.", "WSJ"),
    ("2026-06-02/03 · Meaning & Companionship", "<strong>The rise of conversational AI companions and emotional attachments:</strong> Society grapples with the psychological implications of simulated intimacy.", "NYT")
]

people_html = build_page(
    badge="SPECIAL REPORT · SOCIETY & HUMANITY",
    title="The AI Economy: Where Do Humans Stand<br>When the Marginal Cost of Intelligence Approaches Zero?",
    issue_tag="2026-06 → 08 · Special Dossier",
    series_tag="16 Primary Milestones · Social Impact",
    lede="When cognitive output is commoditized and synthetic content becomes infinite, human worth, creative agency, and societal structures undergo their most profound recalibration in modern history.",
    pg_points="<p><span class=\"pg-point\">1. Taste and curation command the premium</span>: Generating answers is free; knowing what questions matter and assuming responsibility is everything.</p><p><span class=\"pg-point\">2. Junior career pathways face disruption</span>: When routine tasks are automated, the traditional apprenticeship model must be reinvented.</p><p><span class=\"pg-point\">3. Physical connection and authentic provenance rise</span>: Verifiable human origin becomes a defining hallmark of cultural and intellectual value.</p>",
    timeline_items=people_items,
    deep_title="The Human Condition in the Age of Infinite Synthesis",
    deep_body="<span class=\"h2\">1. The Irreplaceability of Genuine Responsibility</span><p>An algorithm can optimize metrics and synthesize thousands of pages, but it cannot bear legal liability, mourn a failure, or celebrate an authentic creative triumph. Moral agency remains strictly human.</p><span class=\"h2\">2. The Renaissance of Authentic Craft</span><p>Just as photography elevated painting from realistic documentation to abstract expression, ubiquitous AI elevates human writing, thinking, and leadership into deeper, more intentional realms.</p>",
    voices=[
        ("Agents can be artificial intelligence, but agency forever belongs to human beings.", "Fei-Fei Li · Stanford HAI Co-Director"),
        ("When intelligence is on tap like electricity, the rarest asset on earth is human taste, genuine curiosity, and moral integrity.", "Philosopher of Technology")
    ],
    related_cards=[
        ("Fei-Fei Li on Human Agency and the Future of AI", "2026-08-05"),
        ("The Psychological Toll of Synthetic Content Curation", "2026-08-09"),
        ("Structural Shifts in Entry-Level Knowledge Work", "2026-06-05")
    ],
    footer_text="Frontier signal stream: reflecting on humanity, culture, and ethics in the intelligent era.",
    zh_ref="ai-and-people.html"
)
save_and_verify("ai-and-people.html", people_html)

print("🎉 ALL 8 SPECIAL PAGES GENERATED AND VERIFIED SUCCESSFULLY!")
