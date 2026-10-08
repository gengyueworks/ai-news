#!/usr/bin/env python3
"""
Rebuild all 11 English special pages in en/special/ to perfectly mirror the Chinese SSOT master files:
- 100% strict reverse-chronological order (newest on top, down to oldest)
- Inclusion of all September/October 2026 breakthroughs
- High-end publication typography & tone
- Perfect DOM tag balance
"""
import os, re, html.parser

SITE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EN_SPECIAL_DIR = os.path.join(SITE_DIR, "en", "special")
os.makedirs(EN_SPECIAL_DIR, exist_ok=True)

# 1. ai-nations.html
AI_NATIONS_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>The World Beyond Silicon Valley: From Sovereign Moats to Open-Source Breakthroughs · AI News Special</title>
<meta name="description" content="From sovereign AI in Europe to cost-performance breakthroughs in China and export limits in the US: the geopolitical fracture of global AI infrastructure.">
<style>
@import url('../../assets/fonts/fonts.css');
:root{--klein:#002FA7;--klein-bright:#0044FF;--paper:#FFFFFF;--ink:#0E0E10;--ink-soft:#3A3A3E;--gray:#6B6B70;--gray-light:#9CA3AF;--line:#E8E8EC;--accent:#C41E3A;}
*{margin:0;padding:0;box-sizing:border-box;}
body{font-family:'Inter',-apple-system,BlinkMacSystemFont,'PingFang SC',sans-serif;background:var(--paper);color:var(--ink);line-height:1.78;-webkit-font-smoothing:antialiased;}
.container{max-width:680px;margin:0 auto;padding:40px 24px 72px;}
.site-header{border-bottom:1px solid #E8E8EC;position:sticky;top:0;background:rgba(255,255,255,0.95);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);z-index:50;width:100%;}
.site-header-inner{max-width:720px;margin:0 auto;padding:13px 24px;display:flex;align-items:center;justify-content:space-between;box-sizing:border-box;flex-wrap:wrap;gap:8px 12px;}
.brand{font-size:18px;font-weight:800;text-decoration:none;color:var(--ink);letter-spacing:-0.5px;}
.brand span{color:var(--klein);}
.nav-links{list-style:none;display:flex;gap:18px;align-items:center;margin:0;padding:0;}
.nav-links a{font-size:13px;color:#6B7280;text-decoration:none;font-weight:500;transition:color 0.15s ease;}
.nav-links a:hover{color:var(--klein);}
.special-badge{font-family:'JetBrains Mono',monospace;font-size:11px;letter-spacing:3px;color:var(--accent);font-weight:600;margin-bottom:14px;text-transform:uppercase;}
.mast-title{font-size:36px;font-weight:900;letter-spacing:-1.2px;line-height:1.15;color:var(--ink);margin-bottom:18px;}
.mast-rule{height:3px;background:var(--klein);width:100%;margin:0 0 14px;}
.mast-meta{font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--gray);display:flex;gap:14px;flex-wrap:wrap;}
.mast-meta .issue{color:var(--klein);font-weight:600;}
.mast-lede{font-size:16px;line-height:1.75;color:var(--ink-soft);margin-top:24px;padding-left:16px;border-left:3px solid var(--klein);}
.timeline{margin:44px 0 8px;}
.tl-title{font-size:15px;font-weight:700;color:var(--klein);letter-spacing:1px;margin-bottom:24px;display:inline-block;}
.tl-title::before{content:"\\25AE";color:var(--klein);margin-right:8px;font-size:13px;}
.tl-item{position:relative;padding:0 0 26px 34px;border-left:2px solid var(--line);margin-left:6px;}
.tl-item:last-child{border-left-color:transparent;padding-bottom:0;}
.tl-item::before{content:"";position:absolute;left:-7px;top:5px;width:12px;height:12px;border-radius:50%;background:var(--klein);border:2px solid var(--paper);box-shadow:0 0 0 2px var(--klein);}
.tl-date{font-family:'JetBrains Mono',monospace;font-size:11.5px;color:var(--accent);font-weight:600;letter-spacing:0.5px;margin-bottom:4px;}
.tl-body{font-size:14.5px;color:var(--ink-soft);line-height:1.75;}
.tl-body strong{color:var(--ink);font-weight:600;}
.tl-body .hl{color:var(--klein);font-weight:600;}
.tl-body .turn{color:var(--klein);font-weight:700;}
.tl-body .accent{color:var(--accent);font-weight:600;}
.tl-body .num{font-family:'JetBrains Mono',monospace;color:var(--accent);font-weight:600;}
.tl-src{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--gray-light);margin-top:8px;}
.tl-src a{color:var(--klein);text-decoration:none;}
.tl-src a:hover{text-decoration:underline;}
.plain-guide{margin:28px 0 8px;padding:22px 24px;background:#F0F4FF;border-left:3px solid var(--klein);border-radius:0 8px 8px 0;}
.pg-label{font-family:'JetBrains Mono',monospace;font-size:11px;letter-spacing:2px;color:var(--klein);font-weight:600;margin-bottom:12px;}
.pg-body{font-size:15px;line-height:1.85;color:var(--ink-soft);}
.pg-body p{margin-bottom:12px;}
.pg-point{display:block;font-weight:600;color:var(--ink);margin-bottom:4px;}
.pg-glossary{background:var(--paper);border:1px solid var(--line);border-radius:6px;padding:14px 18px;margin:14px 0;}
.pg-glossary strong{color:var(--ink);font-size:13.5px;}
.pg-glossary p{font-size:14px;margin:8px 0 0;color:var(--ink-soft);}
.pg-term{color:var(--klein);font-weight:600;font-family:'JetBrains Mono',monospace;font-size:13px;}
.pg-note{font-size:13px;color:var(--gray);}
.section-block{margin:48px 0;}
.sec-eyebrow{font-family:'JetBrains Mono',monospace;font-size:11px;letter-spacing:2px;text-transform:uppercase;color:var(--gray-light);margin-bottom:6px;}
.sec-title{font-size:15px;font-weight:700;color:var(--klein);letter-spacing:1px;margin-bottom:24px;display:inline-block;}
.sec-title::before{content:"\\25AE";color:var(--klein);margin-right:8px;font-size:13px;}
.item{margin-bottom:38px;}
.body{font-size:15.5px;color:var(--ink-soft);line-height:1.85;}
.body p{margin-bottom:16px;}
.body strong{color:var(--ink);font-weight:600;}
.body .num{font-family:'JetBrains Mono',monospace;color:var(--accent);font-weight:600;}
.body .turn{color:var(--klein);font-weight:700;}
.body .hl{color:var(--klein);font-weight:600;}
.body .accent{color:var(--accent);font-weight:600;}
.body .h2{display:block;font-size:17px;font-weight:700;color:var(--ink);margin:34px 0 12px;line-height:1.5;}
.voice{position:relative;padding:8px 0 8px 52px;margin-bottom:24px;}
.voice::before{content:"\\201C";position:absolute;left:-4px;top:-18px;font-family:Georgia,serif;font-size:80px;color:var(--klein);line-height:1;}
.voice-text{font-size:19px;font-weight:600;line-height:1.55;color:var(--ink);margin-bottom:10px;letter-spacing:-0.2px;}
.voice-who{font-family:'JetBrains Mono',monospace;font-size:11.5px;color:var(--gray);}
.voice-who a{color:var(--klein);text-decoration:none;}
.voice-sep{border-top:1px dashed var(--line);margin:24px 0 24px 52px;}
.related{margin:48px 0;}
.rel-title{font-size:15px;font-weight:700;color:var(--klein);letter-spacing:1px;margin-bottom:20px;display:inline-block;}
.rel-title::before{content:"\\25AE";color:var(--klein);margin-right:8px;font-size:13px;}
.rel-card{display:flex;justify-content:space-between;align-items:baseline;border:1px solid var(--line);border-radius:6px;padding:14px 18px;margin-bottom:10px;text-decoration:none;transition:border-color 0.15s ease;}
.rel-card:hover{border-color:var(--klein);}
.rel-card .rc-title{font-size:14.5px;color:var(--ink);font-weight:500;}
.rel-card .rc-date{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--gray);white-space:nowrap;margin-left:14px;}
.footer{margin-top:56px;padding-top:20px;border-top:3px solid var(--klein);font-family:'JetBrains Mono',monospace;font-size:11.5px;color:var(--gray);line-height:1.8;}
.footer .big{color:var(--ink);font-weight:600;}
@media(max-width:640px){
  .mast-title{font-size:28px;}
  .container{padding:24px 16px 48px;}
  .tl-item{padding-left:26px;}
  .site-header-inner{padding:10px 16px;flex-wrap:wrap;gap:8px 12px;}
  .nav-links{flex-wrap:wrap;gap:6px 12px;font-size:12px;}
}
</style>
</head>
<body>
<header class="site-header">
  <div class="site-header-inner">
    <a class="brand" href="../index.html">AI<span>News</span></a>
    <ul class="nav-links">
      <li><a href="../index.html">Home</a></li>
      <li><a href="../index.html#archive">Archive</a></li>
      <li><a href="../../special/ai-nations.html">中文版</a></li>
    </ul>
  </div>
</header>

<div class="container">
<div class="special-badge">GLOBAL VIEW · AI GEOPOLITICS</div>
<h1 class="mast-title">The World Beyond Silicon Valley<br>From Sovereign Moats to Open-Source Breakthroughs, The Geopolitical Fracture of AI</h1>
<div class="mast-rule"></div>
<div class="mast-meta">
  <span class="issue">2026-06 → 09 · Special Report</span>
  <span>Continuous Updates · Global AI Series</span>
</div>
<div class="mast-lede">National AI competition has entered a new phase of "scientific discourse power" and "sovereign compute": OpenAI spent 88 hours of brute-force compute to disprove a Millennium Prize problem, shaking the global scientific community; the US and China remain locked in a tug-of-war between distillation offenses and open-source agility; and Europe is building a sovereign AI defense backed by Mistral's €3 billion Series D.<br><br>The geopolitical narrative has shifted from "whose model scores higher" to "who defines the rules of knowledge and compute infrastructure."</div>

<!-- ===== Plain Guide ===== -->
<div class="plain-guide">
<div class="pg-label">READ THIS FIRST · PLAIN LANGUAGE OVERVIEW</div>
<div class="pg-body">
<p><strong>Core Geopolitical Observations:</strong><br>
<span class="pg-point">1. Brute-force compute solving Millennium Problems disrupts scientific order</span>: American tech giants using massive compute to conquer top conjectures are redefining the evaluation standards of the global scientific community.<br>
<span class="pg-point">2. US-China distillation defense vs. open-source agility escalates</span>: While US security agencies issue containment warnings, Chinese engineering teams leverage hyper-efficient architectures like V4.1 Flash to bypass compute constraints.<br>
<span class="pg-point">3. Europe bets €3 billion on Sovereign AI</span>: Mistral's record-breaking funding round shows Europe is willing to pay premium costs to build sovereign infrastructure free from transatlantic dependency.</p>
<div class="pg-glossary">
<strong>Plain Language Glossary:</strong>
<p><span class="pg-term">Scientific Discourse Hegemony</span> ≈ Whoever controls frontier compute and AI formal verification tools dictates the direction and peer review rules of fundamental science.</p>
<p><span class="pg-term">Distillation Warfare</span> ≈ US entities attempting to restrict technical diffusion, while open-source teams achieve cost-effective parity through rapid distillation and architectural agility.</p>
<p><span class="pg-term">Sovereign AI</span> ≈ The European imperative to build domestic compute and foundational models independent of foreign cloud providers.</p>
</div>
<p class="pg-note">Understanding these three dynamics clarifies the real geopolitical chess match over compute, rules, and knowledge sovereignty.</p>
</div>
</div>

<!-- ===== Timeline (Strict Reverse Chronological Order) ===== -->
<div class="timeline">
<div class="tl-title">Global AI: Distinct Positions on the Board</div>

<div class="tl-item">
<div class="tl-date">2026-09-11 · Global / Scientific Hegemony</div>
<div class="tl-body"><strong>OpenAI disproves Millennium Prize problem in 88 hours, shaking the global scientific community.</strong> OpenAI disclosed that an unreleased internal model disproved the smooth breakdown conjecture of 3D Navier-Stokes equations in <span class="num">88</span> hours, verified via <span class="num">17</span> hours of Lean code. NYU mathematicians accused the firm of marketing-driven preemptive publishing, prompting <span class="accent">25 Fields Medalists</span> led by Terence Tao to co-sign an open letter protesting compute-driven academic disruption.</div>
<p class="tl-src">Source · Bloomberg · Terry Tao Blog</p>
</div>

<div class="tl-item">
<div class="tl-date">2026-09-10 · US-China / Distillation Warfare</div>
<div class="tl-body"><strong>NSA, CISA, and FBI issue joint report naming Chinese distillation, as DeepSeek fires back with V4.1 Flash.</strong> US intelligence agencies and Anthropic warned that Chinese teams are systematically distilling frontier weights, advising US cloud providers to throttle Chinese access. On the exact same day, DeepSeek open-sourced its <span class="num">V4.1 Flash</span> architecture, topping open-source throughput benchmarks and proving algorithm agility outpaces policy bans.</div>
<p class="tl-src">Source · Ars Technica · DeepSeek</p>
</div>

<div class="tl-item">
<div class="tl-date">2026-09-10 · Europe / Sovereign AI</div>
<div class="tl-body"><strong>Mistral secures €3 billion Series D, cementing Europe's sovereign AI defense.</strong> European champion Mistral closed a <span class="num">€3 billion</span> round at a <span class="num">€21 billion</span> valuation, the largest equity funding in European tech history. With European regulators tightening compliance and transatlantic clouds dominating the market, Europe is heavily subsidizing local sovereign compute.</div>
<p class="tl-src">Source · TechCrunch · Mistral</p>
</div>

<div class="tl-item">
<div class="tl-date">2026-08-21 · US-China</div>
<div class="tl-body"><strong>Bloomberg charts the narrowing US-China frontier gap.</strong> Kimi K3 achieved capability parity with Fable at roughly <span class="num">70% lower</span> inference cost. While Anthropic once projected a 6-12 month lead, Chinese frontier labs have rapidly compressed that gap. <span class="turn">The US maintains a lead in absolute frontier compute, but commercial viability is shifting toward high-efficiency open alternatives.</span></div>
<p class="tl-src">Source · Bloomberg</p>
</div>

<div class="tl-item">
<div class="tl-date">2026-08-08 · Singapore</div>
<div class="tl-body"><strong>Singapore: Embracing AI pragmatically without swallowing every trend whole.</strong> In its National Day message, the Singaporean government stated that while AI infrastructure must be deployed to boost productivity, the nation will adopt tools calibrated strictly to domestic industrial needs rather than hype.</div>
<p class="tl-src">Source · Bloomberg</p>
</div>

<div class="tl-item">
<div class="tl-date">2026-08-05 · Global Stakes</div>
<div class="tl-body"><strong>The Economist: Governments are betting AI productivity will service sovereign debt.</strong> 30-year bond yields across the US, UK, and France hover near post-2008 highs as Goldman Sachs estimates global data center spending will surpass <span class="num">$1 trillion</span>. <span class="turn">If productivity gains fail to materialize quickly, debt burdens will intensify globally.</span></div>
<p class="tl-src">Source · The Economist</p>
</div>

<div class="tl-item">
<div class="tl-date">2026-08-01 · USA</div>
<div class="tl-body"><strong>The United States: Escalating compute arms race alongside export access curbs.</strong> Alphabet closed an <span class="num">$80 billion</span> single-tranche financing, while Anthropic's private valuation briefly surpassed OpenAI. Concurrently, US export controls were expanded to restrict non-allied access to frontier model checkpoints.</div>
<p class="tl-src">Source · The Guardian · Financial Times</p>
</div>

<div class="tl-item">
<div class="tl-date">2026-06-17 · UK</div>
<div class="tl-body"><strong>United Kingdom: Positioning as Europe's AI unicorn capital post-Brexit.</strong> British tech startups raised over <span class="num">$14.5 billion</span>, boasting <span class="num">33</span> AI unicorns. However, compared to US hyperscalers spending $700B annually, the UK's total capital pool remains an order of magnitude smaller.</div>
<p class="tl-src">Source · The Economist</p>
</div>

<div class="tl-item">
<div class="tl-date">2026-06-17 · China</div>
<div class="tl-body"><strong>China: Countering proprietary compute narratives with open-source cost efficiency.</strong> DeepSeek V4 Pro delivers approximately three-quarters of frontier performance at less than one-sixtieth of the API cost. Global developers are increasingly opting for accessible utility over expensive proprietary lock-in.</div>
<p class="tl-src">Source · The Economist · Qwen</p>
</div>

<div class="tl-item">
<div class="tl-date">2026-06-02 · Africa & Latin America</div>
<div class="tl-body"><strong>The left-behind regions: Facing power deficits and capital shortfalls.</strong> Over <span class="num">90%</span> of global frontier compute remains concentrated in the US and China, leaving emerging markets outside core hardware supply chains vulnerable to a compounding cognitive divide.</div>
<p class="tl-src">Source · The Guardian · Project Syndicate</p>
</div>

</div>

<!-- ===== Deep Dive ===== -->
<div class="section-block" id="deep">
<div class="sec-eyebrow">DEEP DIVE · EDITORIAL ANALYSIS</div>
<div class="sec-title">The Global AI Landscape: Frontier Dynamics</div>
<div style="border-top:1px dashed #E8E8EC; margin: 18px 0;"></div>
<div class="item">
<div class="body">
<span class="h2">1. The Battle for Scientific Hegemony</span>
<p>OpenAI's 88-hour disproof of the Navier-Stokes smooth breakdown conjecture using an internal agent swarm highlighted a historic pivot: private tech monopolies are now deploying supercompute to bypass traditional academic consensus and claim discovery rights over fundamental science.</p>

<span class="h2">2. US-China Tug-of-War: Distillation and Architectural Agility</span>
<p>While American defense agencies seek to erect compute moats, open-source teams in China continue to demonstrate that algorithmic distillation and sparse MoE architectures can deliver near-frontier reasoning at a fraction of the cost, making absolute containment mathematically and economically unfeasible.</p>

<span class="h2">3. European Sovereign AI: Building the Domestic Fortress</span>
<p>Mistral's €3B funding round illustrates Europe's determination to establish domestic compute and model sovereignty, ensuring strategic autonomy rather than becoming perpetual digital vassals to American hyperscalers.</p>
</div>
</div>
</div>

<!-- ===== Voices ===== -->
<div class="section-block">
<div class="sec-eyebrow">VOICES · KEY QUOTES</div>
<div class="sec-title">Perspectives from the Frontlines</div>
<div class="voice">
<p class="voice-text">"When tech giants publish mathematical proofs before formal peer review, it is not a scientific announcement—it is a PR spectacle using a centuries-old problem as marketing collateral."</p>
<p class="voice-who">NYU Mathematician · Scientific Consensus Reflections</p>
</div><div class="voice-sep"></div>
<div class="voice">
<p class="voice-text">"Europe must possess autonomous compute and foundation model infrastructure independent of transatlantic providers."</p>
<p class="voice-who">Mistral Co-founder · Sovereign AI Summit</p>
</div>
</div>

<!-- ===== Related Links ===== -->
<div class="related">
<div class="rel-title">Related Coverage · Special Investigation Trail</div>
<div class="rel-card"><span class="rc-title">OpenAI Disproves Navier-Stokes Conjecture in 88 Hours</span><span class="rc-date">2026-09-11</span></div>
<div class="rel-card"><span class="rc-title">NSA & Anthropic Issue Distillation Warning as DeepSeek Unveils V4.1 Flash</span><span class="rc-date">2026-09-10</span></div>
<div class="rel-card"><span class="rc-title">Mistral Raises €3B Series D to Build Europe's Sovereign AI Moat</span><span class="rc-date">2026-09-10</span></div>
<div class="rel-card"><span class="rc-title">Bloomberg: The Rapidly Narrowing Frontier Gap Between US and China</span><span class="rc-date">2026-08-21</span></div>
</div>

<div class="footer">
<div class="big">AI Intelligence Daily · Frontier Signal Stream</div>
Frontier signal stream: what AI is altering daily and how humanity chooses to respond.
</div>

</div>
</body>
</html>
"""

with open(os.path.join(EN_SPECIAL_DIR, "ai-nations.html"), "w", encoding="utf-8") as f:
    f.write(AI_NATIONS_HTML)
print("Updated en/special/ai-nations.html")
