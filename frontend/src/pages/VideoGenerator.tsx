/**
 * Phase 20 — VideoGenerator Page
 * AI-powered Story Video Generator for MedSync incidents.
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import { useStore } from '../store/appStore'
import { videoApi, pollVideoJob, VIDEO_STAGES, type VideoJob, type VideoJobStatus } from '../api/videoApi'
import { PipelineProgress } from '../components/video/PipelineProgress'
import { StoryboardPreview } from '../components/video/StoryboardPreview'
import { ScriptPreview } from '../components/video/ScriptPreview'

interface VideoGeneratorProps {
  onNavigate?: (page: string, incidentId?: string) => void
}

// ── Sub-components ────────────────────────────────────────────────────────────

function DifferentiatorCard({ icon, title, them, us }: {
  icon: string; title: string; them: string; us: string
}) {
  return (
    <div style={{
      background: 'rgba(255,255,255,0.03)',
      border: '1px solid rgba(255,255,255,0.07)',
      borderRadius: 12,
      padding: '16px 18px',
      display: 'flex',
      flexDirection: 'column',
      gap: 10,
    }}>
      <div style={{ fontSize: '1.5rem' }}>{icon}</div>
      <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#e8f0ff' }}>{title}</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div style={{
          display: 'flex', alignItems: 'flex-start', gap: 8,
          padding: '6px 10px', borderRadius: 6,
          background: 'rgba(255,60,80,0.08)', border: '1px solid rgba(255,60,80,0.2)',
        }}>
          <span style={{ fontSize: '0.65rem', color: '#ff6b7a', marginTop: 1 }}>✗</span>
          <span style={{ fontSize: '0.65rem', color: 'rgba(200,180,180,0.7)', lineHeight: 1.4 }}>{them}</span>
        </div>
        <div style={{
          display: 'flex', alignItems: 'flex-start', gap: 8,
          padding: '6px 10px', borderRadius: 6,
          background: 'rgba(0,229,160,0.08)', border: '1px solid rgba(0,229,160,0.2)',
        }}>
          <span style={{ fontSize: '0.65rem', color: '#00e5a0', marginTop: 1 }}>✓</span>
          <span style={{ fontSize: '0.65rem', color: 'rgba(180,220,200,0.85)', lineHeight: 1.4 }}>{us}</span>
        </div>
      </div>
    </div>
  )
}

function StorySection({ title, narrative, keyStat, accent }: {
  title: string; narrative: string; keyStat: string; accent: string
}) {
  return (
    <div style={{
      borderLeft: `3px solid ${accent}`,
      paddingLeft: 14,
      marginBottom: 16,
    }}>
      <div style={{ fontSize: '0.7rem', fontWeight: 700, color: accent, marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{title}</div>
      <div style={{ fontSize: '0.78rem', color: 'rgba(200,220,240,0.85)', lineHeight: 1.6, marginBottom: 6 }}>{narrative}</div>
      <div style={{ fontSize: '0.67rem', color: 'rgba(140,180,220,0.5)' }}>📊 {keyStat}</div>
    </div>
  )
}

const STORY_ACCENTS = ['#00a3ff', '#ff3c50', '#00e5c8', '#a050ff', '#ffb400', '#00e582']

// ── Main Page ─────────────────────────────────────────────────────────────────

export function VideoGenerator({ onNavigate }: VideoGeneratorProps) {
  const { incidents, selectedIncidentId, selectIncident } = useStore()
  const [job, setJob] = useState<VideoJob | null>(null)
  const [isGenerating, setIsGenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'story' | 'script' | 'storyboard'>('story')
  const [voiceProvider] = useState<string>('gtts')
  const videoRef = useRef<HTMLVideoElement>(null)

  // Trust indicators derived from storyboard
  const trustIndicators = job?.storyboard?.trust_indicators

  // Select incident (prefer plan_ready or plan_approved)
  const availableIncidents = incidents.filter(i =>
    ['plan_ready', 'plan_approved', 'agents_running'].includes(i.status)
  )
  const currentIncident = incidents.find(i => i.id === selectedIncidentId)
    || availableIncidents[0]
    || incidents[0]

  // Load existing jobs for current incident
  useEffect(() => {
    if (!currentIncident?.id) return
    videoApi.listJobs(currentIncident.id)
      .then(({ data }) => {
        if (data && data.length > 0) {
          setJob(data[0])
        }
      })
      .catch(() => {})
  }, [currentIncident?.id])

  // WS listener for video events
  useEffect(() => {
    if (!currentIncident?.id) return
    const wsUrl = `ws://localhost:8000/api/v1/ws/incidents/${currentIncident.id}`
    let ws: WebSocket | null = null
    try {
      ws = new WebSocket(wsUrl)
      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data)
          if (data.event_type === 'video:progress' || data.event_type === 'video:completed' || data.event_type === 'video:failed') {
            if (job?.id === data.job_id || data.job_id) {
              // Re-fetch the full job to get latest data
              const jid = data.job_id || job?.id
              if (jid) {
                videoApi.getJob(jid).then(({ data: j }) => setJob(j)).catch(() => {})
              }
            }
          }
        } catch {/* ignore */}
      }
    } catch {/* WS unavailable */}
    return () => { ws?.close() }
  }, [currentIncident?.id, job?.id])

  const handleGenerate = useCallback(async () => {
    if (!currentIncident?.id) return
    setIsGenerating(true)
    setError(null)
    setJob(null)

    try {
      const { data: resp } = await videoApi.generate(currentIncident.id, {
        voiceProvider,
        targetDurationSec: 120,
      })

      // Start with pending job
      const pending: VideoJob = {
        id: resp.job_id,
        incident_id: currentIncident.id,
        status: 'pending' as VideoJobStatus,
        progress_pct: 0,
        has_video: false,
        created_at: new Date().toISOString(),
      }
      setJob(pending)

      // Poll for updates
      const final = await pollVideoJob(resp.job_id, (updated) => {
        setJob(updated)
        if (updated.status === 'storyboard' || updated.status === 'script') {
          setActiveTab(updated.status as 'story' | 'script' | 'storyboard')
        }
      })
      setJob(final)
      if (final.status === 'failed') {
        setError(final.error_message || 'Video generation failed')
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Generation failed')
    } finally {
      setIsGenerating(false)
    }
  }, [currentIncident?.id, voiceProvider])

  const downloadUrl = job?.has_video ? videoApi.getDownloadUrl(job.id) : null

  const isReady = currentIncident && ['plan_ready', 'plan_approved'].includes(currentIncident.status)
  const canGenerate = isReady && !isGenerating && job?.status !== 'composing'

  return (
    <div style={{ padding: '24px 28px', maxWidth: 1400, margin: '0 auto' }}>

      {/* ── Page Header ── */}
      <div style={{ marginBottom: 28, display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 20 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
            <div style={{
              width: 44, height: 44, borderRadius: 12,
              background: 'linear-gradient(135deg, #7c5cff, #00a3ff)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: '1.4rem', boxShadow: '0 0 20px rgba(124,92,255,0.4)',
            }}>🎬</div>
            <div>
              <h1 style={{ fontSize: '1.5rem', fontWeight: 800, color: '#e8f0ff', margin: 0 }}>
                Story Video Generator
              </h1>
              <div style={{ fontSize: '0.75rem', color: 'rgba(140,180,220,0.6)', marginTop: 2 }}>
                AI-powered executive briefing video from incident data
              </div>
            </div>
          </div>
          {/* Phase badge */}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {['Phase 20', 'Hackathon Demo', '6-Stage AI Pipeline', 'FFmpeg · MoviePy · gTTS'].map(tag => (
              <span key={tag} style={{
                background: 'rgba(124,92,255,0.12)', border: '1px solid rgba(124,92,255,0.25)',
                borderRadius: 99, padding: '2px 10px', fontSize: '0.62rem', fontWeight: 700, color: '#a07cff',
              }}>{tag}</span>
            ))}
          </div>
        </div>

        {/* Generate button */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 8, flexShrink: 0 }}>
          <button
            onClick={handleGenerate}
            disabled={!canGenerate}
            style={{
              padding: '12px 28px',
              borderRadius: 10,
              border: 'none',
              background: canGenerate
                ? 'linear-gradient(135deg, #7c5cff, #00a3ff)'
                : 'rgba(255,255,255,0.06)',
              color: canGenerate ? '#fff' : 'rgba(140,180,220,0.3)',
              fontWeight: 700,
              fontSize: '0.88rem',
              cursor: canGenerate ? 'pointer' : 'not-allowed',
              display: 'flex', alignItems: 'center', gap: 8,
              transition: 'all 0.2s ease',
              boxShadow: canGenerate ? '0 4px 20px rgba(124,92,255,0.3)' : 'none',
              whiteSpace: 'nowrap',
            }}
          >
            {isGenerating ? (
              <>
                <span style={{ display: 'inline-block', animation: 'spin 1s linear infinite' }}>⚙️</span>
                Generating…
              </>
            ) : (
              <>🎬 Generate Video</>
            )}
          </button>

          {!isReady && !isGenerating && (
            <div style={{ fontSize: '0.65rem', color: 'rgba(255,180,0,0.7)', textAlign: 'right' }}>
              ⚠ Incident needs plan_ready status
              {currentIncident && (
                <span style={{ marginLeft: 4, color: 'rgba(140,180,220,0.5)' }}>
                  (Current: {currentIncident.status})
                </span>
              )}
            </div>
          )}
        </div>
      </div>

      {/* ── Incident Selector ── */}
      {incidents.length > 0 && (
        <div style={{
          background: 'rgba(255,255,255,0.02)',
          border: '1px solid rgba(255,255,255,0.07)',
          borderRadius: 12,
          padding: '14px 18px',
          marginBottom: 24,
          display: 'flex',
          alignItems: 'center',
          gap: 14,
          flexWrap: 'wrap',
        }}>
          <div style={{ fontSize: '0.7rem', fontWeight: 700, color: 'rgba(140,180,220,0.5)', textTransform: 'uppercase', letterSpacing: '0.08em', whiteSpace: 'nowrap' }}>
            Target Incident
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', flex: 1 }}>
            {incidents.slice(0, 5).map(inc => {
              const isSelected = inc.id === (currentIncident?.id)
              const isEligible = ['plan_ready', 'plan_approved'].includes(inc.status)
              return (
                <button
                  key={inc.id}
                  onClick={() => selectIncident(inc.id)}
                  style={{
                    padding: '6px 14px',
                    borderRadius: 8,
                    border: `1px solid ${isSelected ? '#00a3ff66' : 'rgba(255,255,255,0.08)'}`,
                    background: isSelected ? 'rgba(0,163,255,0.12)' : 'rgba(255,255,255,0.03)',
                    color: isSelected ? '#00a3ff' : isEligible ? 'rgba(200,220,240,0.7)' : 'rgba(140,180,220,0.3)',
                    fontSize: '0.7rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  <span style={{
                    display: 'inline-block', width: 6, height: 6, borderRadius: '50%',
                    background: isEligible ? '#00e5a0' : '#ffb400',
                    marginRight: 6, verticalAlign: 'middle',
                  }} />
                  {inc.incident_type?.replace(/_/g, ' ').toUpperCase().slice(0, 20)}
                  <span style={{ marginLeft: 6, opacity: 0.5, fontSize: '0.6rem' }}>
                    {inc.id.slice(0, 6)}
                  </span>
                </button>
              )
            })}
          </div>
        </div>
      )}

      {/* ── Pipeline Progress ── */}
      {job && (
        <div style={{
          background: 'rgba(255,255,255,0.02)',
          border: '1px solid rgba(255,255,255,0.07)',
          borderRadius: 16,
          padding: '20px 24px',
          marginBottom: 24,
        }}>
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            marginBottom: 20
          }}>
            <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'rgba(140,180,220,0.6)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              Pipeline Status
            </div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <span style={{
                padding: '3px 10px', borderRadius: 99, fontSize: '0.65rem', fontWeight: 700,
                background: job.status === 'completed' ? 'rgba(0,229,160,0.15)' :
                            job.status === 'failed'    ? 'rgba(255,60,80,0.15)'   :
                                                         'rgba(0,163,255,0.15)',
                border: `1px solid ${job.status === 'completed' ? 'rgba(0,229,160,0.4)' :
                                     job.status === 'failed'    ? 'rgba(255,60,80,0.4)'  :
                                                                  'rgba(0,163,255,0.4)'}`,
                color: job.status === 'completed' ? '#00e5a0' :
                       job.status === 'failed'    ? '#ff6b7a'  :
                                                    '#00a3ff',
              }}>
                {job.status?.toUpperCase()}
              </span>
              {job.duration_sec && (
                <span style={{ fontSize: '0.65rem', color: 'rgba(140,180,220,0.5)' }}>
                  {Math.floor(job.duration_sec / 60)}:{(Math.round(job.duration_sec) % 60).toString().padStart(2, '0')}
                </span>
              )}
            </div>
          </div>
          <PipelineProgress
            status={job.status}
            progressPct={job.progress_pct}
            error={job.error_message}
          />
        </div>
      )}

      {/* ── Trust & Governance Indicators (Task 6) ── */}
      {trustIndicators && (
        <div style={{
          background: 'rgba(0,229,160,0.04)',
          border: '1px solid rgba(0,229,160,0.2)',
          borderRadius: 12,
          padding: '14px 20px',
          marginBottom: 24,
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          flexWrap: 'wrap',
        }}>
          <div style={{ fontSize: '0.65rem', fontWeight: 700, color: 'rgba(0,229,160,0.6)', textTransform: 'uppercase', letterSpacing: '0.1em', marginRight: 4 }}>
            🔒 Trust & Governance
          </div>
          {[
            {
              icon: '✅',
              label: 'Compliance Approved',
              value: trustIndicators.compliance_status as string || 'VALIDATED',
              color: '#00e5a0',
              active: trustIndicators.compliance_status === 'VALIDATED',
            },
            {
              icon: '👤',
              label: 'Human Review Required',
              value: 'Required',
              color: '#ffb400',
              active: trustIndicators.human_review_required as boolean,
            },
            {
              icon: '📋',
              label: 'Audit Trail',
              value: 'Available',
              color: '#00a3ff',
              active: trustIndicators.audit_trail_available as boolean,
            },
            {
              icon: '🔄',
              label: 'Negotiation',
              value: 'Completed',
              color: '#a050ff',
              active: trustIndicators.negotiation_completed as boolean,
            },
            {
              icon: '🤖',
              label: 'AI-Generated',
              value: 'Disclosed',
              color: '#ff9c3a',
              active: trustIndicators.ai_generated as boolean,
            },
          ].map(({ icon, label, value, color, active }) => (
            <div key={label} style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              padding: '5px 12px',
              borderRadius: 20,
              background: active ? `${color}15` : 'rgba(255,255,255,0.03)',
              border: `1px solid ${active ? color + '40' : 'rgba(255,255,255,0.07)'}`,
              opacity: active ? 1 : 0.4,
            }}>
              <span style={{ fontSize: '0.75rem' }}>{icon}</span>
              <div>
                <div style={{ fontSize: '0.6rem', fontWeight: 700, color, lineHeight: 1.1 }}>{label}</div>
                <div style={{ fontSize: '0.58rem', color: 'rgba(180,210,240,0.6)', lineHeight: 1.1 }}>{value}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      {job?.has_video && downloadUrl && (
        <div style={{
          background: 'rgba(0,0,0,0.4)',
          border: '1px solid rgba(124,92,255,0.3)',
          borderRadius: 16,
          padding: 20,
          marginBottom: 24,
          boxShadow: '0 0 40px rgba(124,92,255,0.15)',
        }}>
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14
          }}>
            <div style={{
              fontSize: '0.75rem', fontWeight: 700, color: '#a07cff',
              textTransform: 'uppercase', letterSpacing: '0.08em',
              display: 'flex', alignItems: 'center', gap: 8
            }}>
              <span style={{ animation: 'pulse 2s infinite' }}>🎬</span>
              Executive Briefing Video — Ready
            </div>
            <a
              href={downloadUrl}
              download
              style={{
                padding: '8px 20px',
                borderRadius: 8,
                background: 'linear-gradient(135deg, #7c5cff, #00a3ff)',
                color: '#fff',
                fontWeight: 700,
                fontSize: '0.78rem',
                textDecoration: 'none',
                display: 'flex', alignItems: 'center', gap: 6,
                boxShadow: '0 4px 16px rgba(124,92,255,0.3)',
              }}
            >
              ⬇️ Download MP4
            </a>
          </div>
          <video
            ref={videoRef}
            src={downloadUrl}
            controls
            style={{
              width: '100%',
              maxHeight: 450,
              borderRadius: 10,
              background: '#000',
              boxShadow: '0 8px 32px rgba(0,0,0,0.6)',
            }}
          />
          <div style={{
            marginTop: 12, display: 'flex', gap: 10, flexWrap: 'wrap'
          }}>
            {[
              { label: 'Duration', value: job.duration_sec ? `${Math.floor(job.duration_sec)}s` : '—' },
              { label: 'Format', value: 'MP4 · H.264' },
              { label: 'Resolution', value: '1280×720' },
              { label: 'Provider', value: job.voice_provider?.toUpperCase() || 'GTTS' },
            ].map(({ label, value }) => (
              <div key={label} style={{
                padding: '4px 12px', borderRadius: 6,
                background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)',
              }}>
                <span style={{ fontSize: '0.6rem', color: 'rgba(140,180,220,0.5)', marginRight: 6 }}>{label}</span>
                <span style={{ fontSize: '0.7rem', fontWeight: 700, color: '#e8f0ff' }}>{value}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Story / Script / Storyboard Tabs ── */}
      {job && (job.story || job.script || job.storyboard) && (
        <div style={{ marginBottom: 24 }}>
          {/* Tab header */}
          <div style={{
            display: 'flex', gap: 4, marginBottom: 16,
            borderBottom: '1px solid rgba(255,255,255,0.07)',
          }}>
            {([
              { id: 'story',      label: '📖 Story',      available: !!job.story },
              { id: 'script',     label: '📝 Script',     available: !!job.script },
              { id: 'storyboard', label: '🎬 Storyboard', available: !!job.storyboard },
            ] as const).map(tab => (
              <button
                key={tab.id}
                onClick={() => tab.available && setActiveTab(tab.id)}
                disabled={!tab.available}
                style={{
                  padding: '8px 18px',
                  borderRadius: '8px 8px 0 0',
                  border: 'none',
                  borderBottom: activeTab === tab.id ? '2px solid #00a3ff' : '2px solid transparent',
                  background: activeTab === tab.id ? 'rgba(0,163,255,0.08)' : 'transparent',
                  color: !tab.available ? 'rgba(140,180,220,0.2)' : activeTab === tab.id ? '#00a3ff' : 'rgba(200,220,240,0.6)',
                  fontSize: '0.78rem',
                  fontWeight: 700,
                  cursor: tab.available ? 'pointer' : 'not-allowed',
                  transition: 'all 0.2s ease',
                }}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Tab content */}
          <div style={{
            background: 'rgba(255,255,255,0.02)',
            border: '1px solid rgba(255,255,255,0.07)',
            borderRadius: '0 12px 12px 12px',
            padding: '20px 24px',
          }}>
            {activeTab === 'story' && job.story && (
              <div>
                <div style={{ marginBottom: 16 }}>
                  <div style={{ fontSize: '1.1rem', fontWeight: 800, color: '#e8f0ff', marginBottom: 6 }}>
                    {job.story.title}
                  </div>
                  <div style={{ fontSize: '0.78rem', color: 'rgba(200,220,240,0.7)', lineHeight: 1.6, fontStyle: 'italic' }}>
                    "{job.story.hook}"
                  </div>
                </div>

                {/* Business impact */}
                {job.story.business_impact && (
                  <div style={{
                    display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
                    gap: 10, marginBottom: 20,
                  }}>
                    {Object.entries(job.story.business_impact).map(([key, val]) => (
                      <div key={key} style={{
                        padding: '10px 14px',
                        borderRadius: 8,
                        background: 'rgba(0,229,160,0.06)',
                        border: '1px solid rgba(0,229,160,0.15)',
                      }}>
                        <div style={{ fontSize: '0.6rem', color: 'rgba(0,229,160,0.6)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>
                          {key.replace(/_/g, ' ')}
                        </div>
                        <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#e8f0ff' }}>
                          {typeof val === 'boolean' ? (val ? '✓ Yes' : '✗ No') : String(val)}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {activeTab === 'script' && job.script && (
              <ScriptPreview
                sections={job.script.sections}
                totalWords={job.script.total_words}
                estimatedDuration={job.script.estimated_duration_sec}
              />
            )}

            {activeTab === 'storyboard' && job.storyboard && (
              <StoryboardPreview scenes={job.storyboard.scenes} />
            )}
          </div>
        </div>
      )}

      {/* ── Hackathon Differentiator ── */}
      <div style={{
        background: 'linear-gradient(135deg, rgba(124,92,255,0.06), rgba(0,163,255,0.04))',
        border: '1px solid rgba(124,92,255,0.2)',
        borderRadius: 16,
        padding: '22px 24px',
        marginBottom: 24,
      }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10, marginBottom: 18
        }}>
          <span style={{ fontSize: '1.2rem' }}>🏆</span>
          <div>
            <div style={{ fontSize: '0.85rem', fontWeight: 800, color: '#e8f0ff' }}>
              Hackathon Differentiator
            </div>
            <div style={{ fontSize: '0.65rem', color: 'rgba(140,180,220,0.5)' }}>
              Why MedSync's Video Generator wins
            </div>
          </div>
        </div>

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
          gap: 12
        }}>
          <DifferentiatorCard
            icon="📊"
            title="Decision Output"
            them="PDF reports & static dashboards"
            us="Cinematic executive video briefing"
          />
          <DifferentiatorCard
            icon="🤖"
            title="Agent Transparency"
            them="Log tables no one reads"
            us="Narrated story of AI collaboration"
          />
          <DifferentiatorCard
            icon="🔄"
            title="Negotiation Visibility"
            them="Hidden black-box decisions"
            us="Animated negotiation loop timeline"
          />
          <DifferentiatorCard
            icon="⏱️"
            title="Time-to-Insight"
            them="Read a 10-page incident report"
            us="Watch a 90-second executive video"
          />
          <DifferentiatorCard
            icon="👔"
            title="Target Audience"
            them="IT analysts & system admins"
            us="Hospital CEOs & board members"
          />
          <DifferentiatorCard
            icon="📝"
            title="Audit Trail"
            them="Separate export required"
            us="Video IS the audit trail"
          />
        </div>

        {/* Pipeline architecture */}
        <div style={{ marginTop: 20 }}>
          <div style={{ fontSize: '0.65rem', fontWeight: 700, color: 'rgba(140,180,220,0.4)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 12 }}>
            6-Stage AI Video Pipeline
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
            {VIDEO_STAGES.map((stage, i) => (
              <>
                <div key={stage.status} style={{
                  padding: '6px 12px',
                  borderRadius: 8,
                  background: 'rgba(124,92,255,0.1)',
                  border: '1px solid rgba(124,92,255,0.2)',
                  fontSize: '0.68rem',
                  fontWeight: 700,
                  color: '#a07cff',
                  display: 'flex', alignItems: 'center', gap: 5,
                }}>
                  <span>{stage.icon}</span>
                  {stage.label}
                </div>
                {i < VIDEO_STAGES.length - 1 && (
                  <span key={`arrow-${i}`} style={{ color: 'rgba(124,92,255,0.4)', fontSize: '0.7rem' }}>→</span>
                )}
              </>
            ))}
            <span style={{ color: 'rgba(124,92,255,0.4)', fontSize: '0.7rem' }}>→</span>
            <div style={{
              padding: '6px 12px',
              borderRadius: 8,
              background: 'rgba(0,229,160,0.1)',
              border: '1px solid rgba(0,229,160,0.25)',
              fontSize: '0.68rem',
              fontWeight: 700,
              color: '#00e5a0',
              display: 'flex', alignItems: 'center', gap: 5,
            }}>
              🎞️ incident-briefing.mp4
            </div>
          </div>
        </div>
      </div>

      {/* ── No incidents state ── */}
      {incidents.length === 0 && (
        <div style={{
          padding: '48px 24px', textAlign: 'center',
          background: 'rgba(255,255,255,0.02)',
          border: '1px solid rgba(255,255,255,0.07)',
          borderRadius: 16,
        }}>
          <div style={{ fontSize: '3rem', marginBottom: 12 }}>🚨</div>
          <div style={{ fontSize: '0.9rem', fontWeight: 700, color: 'rgba(200,220,240,0.7)', marginBottom: 8 }}>
            No incidents yet
          </div>
          <div style={{ fontSize: '0.75rem', color: 'rgba(140,180,220,0.4)', marginBottom: 20 }}>
            Create or simulate an incident first, then generate its executive video.
          </div>
          <button
            onClick={() => onNavigate?.('simulation')}
            style={{
              padding: '10px 24px',
              borderRadius: 8,
              border: '1px solid rgba(0,163,255,0.3)',
              background: 'rgba(0,163,255,0.1)',
              color: '#00a3ff',
              fontWeight: 700,
              fontSize: '0.8rem',
              cursor: 'pointer',
            }}
          >
            🧪 Go to Simulation
          </button>
        </div>
      )}

      {/* Inline keyframes */}
      <style>{`
        @keyframes spin-slow { to { transform: rotate(360deg); } }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
      `}</style>
    </div>
  )
}
