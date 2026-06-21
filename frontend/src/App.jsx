// frontend/src/App.jsx

import React, { useState, useEffect, useRef } from 'react';
import { 
  Search, Sparkles, Cpu, CheckCircle2, Activity, AlertCircle, 
  RefreshCw, Sliders, ShieldCheck, Terminal, ArrowRight, 
  Briefcase, Code2, Users, Target, ChevronDown, ChevronUp, Database, Trash2
} from 'lucide-react';

const API_BASE_URL = 'http://localhost:8000';

const PRESET_QUERIES = [
  "Find high-growth AI SaaS companies in the US and generate personalized outbound hooks for their VP Sales.",
  "Identify fintech startups hiring aggressively and suggest outreach strategies.",
  "Give me companies likely to churn competitors and how to target them.",
  "Search for acquisitions in the Fintech category.",
  "Find YC Batch 2005 companies in the vertical Consumer.",
  "Search LinkedIn job postings hiring for Therapist in Fort Collins."
];

export default function App() {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  
  // Real-time states
  const [timeline, setTimeline] = useState([]);
  const [logs, setLogs] = useState([]);
  const [activeTab, setActiveTab] = useState({}); // company_name -> persona_name ('CEO', 'VP Sales', 'CTO')
  const [showLogs, setShowLogs] = useState(true);
  const [showTimeline, setShowTimeline] = useState(false);
  
  // Final Result State
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  
  // Cache state
  const [cacheCount, setCacheCount] = useState(0);

  const logsEndRef = useRef(null);

  useEffect(() => {
    fetchCacheStatus();
  }, []);

  useEffect(() => {
    if (logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs]);

  const fetchCacheStatus = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/cache`);
      const data = await res.json();
      setCacheCount(data.cached_queries_count || 0);
    } catch (err) {
      console.error("Failed to fetch cache status:", err);
    }
  };

  const handleClearCache = async () => {
    try {
      await fetch(`${API_BASE_URL}/api/cache/clear`, { method: 'POST' });
      fetchCacheStatus();
      alert("Cache cleared successfully!");
    } catch (err) {
      console.error("Failed to clear cache:", err);
    }
  };

  const executeQuery = (searchQuery, forceRefresh = false) => {
    if (!searchQuery.trim()) return;
    
    setLoading(true);
    setError(null);
    setResult(null);
    setTimeline([]);
    setLogs([`[System] Initializing GTM pipeline connection for query: "${searchQuery}"`]);

    const url = `${API_BASE_URL}/api/query?query=${encodeURIComponent(searchQuery)}&refresh=${forceRefresh}`;
    const eventSource = new EventSource(url);

    eventSource.addEventListener('message', (event) => {
      try {
        const payload = JSON.parse(event.data);
        const { event: eventType, data } = payload;

        if (eventType === 'status') {
          const timestamp = new Date().toLocaleTimeString();
          
          // Log parsing
          let logClass = 'info';
          if (data.status === 'completed') logClass = 'success';
          if (data.status === 'failed') logClass = 'error';
          if (data.status === 'correcting') logClass = 'warning';

          setLogs(prev => [...prev, {
            time: timestamp,
            agent: data.agent,
            message: data.message,
            type: logClass
          }]);

          // Timeline tracking update
          setTimeline(prev => {
            // Check if step for this agent already exists
            const existingIndex = prev.findIndex(item => item.agent === data.agent && item.attempt === data.attempt);
            if (existingIndex > -1) {
              const updated = [...prev];
              updated[existingIndex] = {
                ...updated[existingIndex],
                status: data.status,
                message: data.message,
                feedback: data.feedback || updated[existingIndex].feedback
              };
              return updated;
            } else {
              return [...prev, {
                agent: data.agent,
                message: data.message,
                status: data.status,
                attempt: data.attempt || 1,
                feedback: data.feedback || null
              }];
            }
          });

        } else if (eventType === 'result') {
          setResult(data);
          setLoading(false);
          eventSource.close();
          fetchCacheStatus(); // update cache numbers
          
          // Initialize active tab for outreach persona cards
          const initialTabs = {};
          data.results.forEach(company => {
            initialTabs[company.name] = 'VP Sales'; // Default to VP Sales
          });
          setActiveTab(initialTabs);
          
          setLogs(prev => [...prev, {
            time: new Date().toLocaleTimeString(),
            agent: 'Orchestrator',
            message: 'Pipeline completed successfully. Layout compiled.',
            type: 'success'
          }]);
        } else if (eventType === 'error') {
          setError(data.message || 'Pipeline runtime encountered an issue.');
          setLoading(false);
          eventSource.close();
        }
      } catch (err) {
        console.error("SSE parsing error:", err);
      }
    });

    eventSource.onerror = (err) => {
      console.error("SSE connection failure:", err);
      setError("Network error: Server disconnected or rate limit exceeded.");
      setLoading(false);
      eventSource.close();
    };
  };

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    executeQuery(query);
  };

  // Helper for rendering step icons
  const getStepIcon = (agentName, status) => {
    if (status === 'running') return <Activity className="animate-spin text-cyan-400" size={18} />;
    if (status === 'completed') return <CheckCircle2 className="text-emerald-400" size={18} />;
    if (status === 'failed') return <AlertCircle className="text-rose-400" size={18} />;
    if (status === 'correcting') return <RefreshCw className="animate-spin text-amber-400" size={18} />;
    
    switch (agentName) {
      case 'Planner Agent': return <Sliders size={18} />;
      case 'Retrieval Agent': return <Database size={18} />;
      case 'Enrichment Agent': return <Sparkles size={18} />;
      case 'Validation / Critic Agent': return <ShieldCheck size={18} />;
      default: return <Cpu size={18} />;
    }
  };

  const getConfidenceClass = (conf) => {
    if (conf >= 0.8) return 'high';
    if (conf >= 0.5) return 'med';
    return 'low';
  };

  const hasQuery = loading || result || timeline.length > 0;

  return (
    <div className={`layout-wrapper ${hasQuery ? 'has-query' : 'no-query'}`}>
      <div className="app-container">

      {/* Input panel */}
      <section className="search-panel">
        <h2 className="search-title">Ask me</h2>
        <form onSubmit={handleSearchSubmit} className="search-form">
          <div className="search-input-wrapper">
            <input 
              type="text" 
              className="search-input"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. Find high-growth AI SaaS companies in the US and generate personalized outbound hooks for their VP Sales..."
              disabled={loading}
            />
          </div>
          <button type="submit" className="search-button" disabled={loading || !query.trim()}>
            {loading ? (
              <>
                <Activity className="animate-spin" size={18} />
                Analyzing...
              </>
            ) : (
              <>
                <Search size={18} />
                Search
              </>
            )}
          </button>
          {result && (
            <button 
              type="button" 
              className="search-button" 
              style={{ background: 'none', border: '1px solid var(--border-color)', color: 'var(--text-primary)' }}
              onClick={() => executeQuery(query, true)} 
              disabled={loading}
              title="Force pipeline re-execution"
            >
              <RefreshCw size={18} />
            </button>
          )}
        </form>
        
        {/* Preset chips */}
        <div className="presets-container">
          {PRESET_QUERIES.map((q, idx) => (
            <button
              key={idx}
              type="button"
              className="preset-chip"
              onClick={() => { setQuery(q); executeQuery(q); }}
              disabled={loading}
            >
              {q.substring(0, 48)}…
            </button>
          ))}
        </div>
      </section>

      {/* Main dashboard content */}
      <main className={`dashboard-grid ${hasQuery ? 'active' : ''}`}>
        
        {/* Left Side: Agent steps timeline and confidence */}
        <section className="side-panel">

          {/* Execution Timeline — collapsible */}
          <div className="panel">
            <div
              className="panel-header timeline-toggle"
              onClick={() => setShowTimeline(p => !p)}
              style={{ cursor: 'pointer', userSelect: 'none' }}
            >
              <h3 className="panel-title">
                <Cpu size={18} />
                Execution Timeline
                {loading && (
                  <span style={{ fontSize: '11px', color: 'var(--accent-cyan)', marginLeft: '8px' }} className="animate-pulse">
                    ● Live
                  </span>
                )}
              </h3>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                {/* Compact inline confidence pill */}
                {result && (
                  <span className={`conf-pill ${getConfidenceClass(result.confidence)}`}>
                    {Math.round(result.confidence * 100)}% confidence
                  </span>
                )}
                {showTimeline ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
              </div>
            </div>

            {showTimeline && (
              <div className="timeline">
                {timeline.length === 0 && (
                  <div style={{ color: 'var(--text-muted)', fontSize: '13px', textAlign: 'center', padding: '20px 0' }}>
                    No pipeline active. Submit a query above.
                  </div>
                )}
                {timeline.map((step, idx) => (
                  <div key={idx} className={`timeline-step ${step.status}`}>
                    <div className="step-indicator">
                      {getStepIcon(step.agent, step.status)}
                    </div>
                    <div className="step-details">
                      <span className="step-name">{step.agent}</span>
                      <span className="step-message">{step.message}</span>
                      {step.feedback && (
                        <span className="step-badge retry">Critic Rejection Loop</span>
                      )}
                      {step.status === 'correcting' && (
                        <span className="step-badge correction">Applying Self-Correction</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

        </section>

        {/* Right Side: Leads & GTM outbound copy */}
        <section className="main-panel">
          
          {error && (
            <div className="panel" style={{ borderColor: 'var(--accent-magenta)', background: 'var(--accent-magenta-glow)' }}>
              <div style={{ display: 'flex', gap: '12px', alignItems: 'center', color: 'var(--accent-magenta)' }}>
                <AlertCircle size={24} />
                <div>
                  <h4 style={{ fontWeight: 700 }}>Orchestrator Execution Error</h4>
                  <p style={{ fontSize: '13px', marginTop: '4px' }}>{error}</p>
                </div>
              </div>
            </div>
          )}

          {result && result.results && (
            <div className="leads-board">
              <h3 className="leads-heading">
                <Users size={20} />
                Prospect Accounts &amp; ICP Profiles
              </h3>

              {result.results.length === 0 ? (
                <div className="panel" style={{ textAlign: 'center', color: 'var(--text-secondary)' }}>
                  No target prospects matched the structured GTM filters.
                </div>
              ) : (
                result.results.map((company, cIdx) => {
                  const signalsObj = result.signals.find(s => s.company === company.name) || {};
                  const currentPersona = activeTab[company.name] || 'VP Sales';
                  const snippet = result.gtm_strategy.email_snippets.find(
                    s => s.company === company.name && s.persona === currentPersona
                  );

                  return (
                    <div key={cIdx} className="lead-card">
                      
                      {/* Company Header */}
                      <div className="lead-header">
                        <div className="lead-identity">
                          <h4 className="lead-name">{company.name}</h4>
                          <a href={`https://${company.domain}`} target="_blank" rel="noreferrer" className="lead-domain">
                            {company.domain}
                          </a>
                        </div>
                        <div className="lead-meta">
                          <span className="meta-badge industry">{company.industry}</span>
                          <span className="meta-badge">{company.location}</span>
                          <span className="meta-badge funding">{company.funding}</span>
                          <span className="meta-badge">{company.hiring}</span>
                        </div>
                      </div>

                      {/* ICP Score Breakdown */}
                      <div className="lead-scores">
                        <div className="score-item">
                          <span className="score-label">Fit Score</span>
                          <span className="score-val">{Math.round(company.icp_scores.fit * 100)}%</span>
                        </div>
                        <div className="score-item">
                          <span className="score-label">Intent Score</span>
                          <span className="score-val">{Math.round(company.icp_scores.intent * 100)}%</span>
                        </div>
                        <div className="score-item">
                          <span className="score-label">Growth Score</span>
                          <span className="score-val">{Math.round(company.icp_scores.growth * 100)}%</span>
                        </div>
                        <div className="score-item">
                          <span className="score-label">Overall ICP</span>
                          <span className="score-val overall">{Math.round(company.icp_scores.overall * 100)}%</span>
                        </div>
                      </div>

                      {/* Observed Buying Signals */}
                      {signalsObj && (
                        <div className="signals-section">
                          <span className="signals-title">Observed Signals</span>
                          <div className="signals-grid">
                            {signalsObj.tech_stack && signalsObj.tech_stack.slice(0, 4).map((tech, tIdx) => (
                              <span key={tIdx} className="signal-chip" style={{ color: 'var(--accent-cyan)', borderColor: 'var(--accent-cyan-glow)' }}>
                                <Code2 size={10} style={{ marginRight: '4px' }} />
                                {tech}
                              </span>
                            ))}
                            {signalsObj.hiring_roles && signalsObj.hiring_roles.map((role, rIdx) => (
                              <span key={rIdx} className="signal-chip">
                                <Briefcase size={10} style={{ marginRight: '4px' }} />
                                hiring: {role}
                              </span>
                            ))}
                            {signalsObj.competitors_used && signalsObj.competitors_used.map((comp, cpIdx) => (
                              <span key={cpIdx} className="signal-chip" style={{ color: 'var(--accent-magenta)', borderColor: 'var(--accent-magenta-glow)' }}>
                                competitor: {comp}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Buying intent explanation */}
                      {company.why_this_result && (
                        <div className="why-box">
                          <strong>Why this result? </strong> {company.why_this_result}
                        </div>
                      )}

                      {/* Multi-Persona Outbound Copy */}
                      <div className="persona-tabs-container">
                        <div className="persona-tabs">
                          {['CEO', 'VP Sales', 'CTO'].map(persona => (
                            <button
                              key={persona}
                              className={`persona-tab ${currentPersona === persona ? 'active' : ''}`}
                              onClick={() => setActiveTab(prev => ({ ...prev, [company.name]: persona }))}
                            >
                              {persona} Outbound
                            </button>
                          ))}
                        </div>
                        <div className="tab-content">
                          {snippet ? (
                            <>
                              <div className="email-subject">
                                <strong>Subject:</strong> {snippet.subject}
                              </div>
                              <div className="email-body">
                                {snippet.body}
                              </div>
                            </>
                          ) : (
                            <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                              Outreach strategy not generated for this persona.
                            </div>
                          )}
                        </div>
                      </div>

                    </div>
                  );
                })
              )}
            </div>
          )}

          {/* Reasoning trace logs (collapsible) */}
          {(loading || logs.length > 1) && (
            <section className="logs-section">
              <div className="logs-header" onClick={() => setShowLogs(!showLogs)}>
                <h4 className="panel-title">
                  <Terminal size={16} className="text-cyan-400" />
                  Observability & Live Agent Logs
                </h4>
                {showLogs ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
              </div>
              
              {showLogs && (
                <div className="logs-terminal">
                  {logs.map((log, idx) => (
                    <div key={idx} className={`log-entry ${log.type || 'info'}`}>
                      {log.time && <span>[{log.time}] </span>}
                      {log.agent && <strong>[{log.agent}] </strong>}
                      {log.message}
                    </div>
                  ))}
                  <div ref={logsEndRef} />
                </div>
              )}
            </section>
          )}

        </section>

      </main>
      </div>
    </div>
  );
}
