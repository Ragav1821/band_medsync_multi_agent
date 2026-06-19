/**
 * ScriptPreview — Collapsible sections showing the voice-over script.
 */
import { useState } from 'react'
import type { VideoScriptSection } from '../../api/videoApi'

interface ScriptPreviewProps {
  sections: VideoScriptSection[]
  totalWords: number
  estimatedDuration: number
}

const SECTION_COLORS: Record<string, string> = {
  intro:        '#00a3ff',
  problem:      '#ff3c50',
  activation:   '#00e5c8',
  collaboration:'#a050ff',
  negotiation:  '#ffb400',
  action_plan:  '#00e582',
  outcome:      '#00a3ff',
  cta:          '#64c8ff',
}

export function ScriptPreview({ sections, totalWords, estimatedDuration }: ScriptPreviewProps) {
  const [openSection, setOpenSection] = useState<string | null>('intro')

  if (!sections || sections.length === 0) return null

  const mins = Math.floor(estimatedDuration / 60)
  const secs = estimatedDuration % 60

  return (
    <div>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        marginBottom: 14,
      }}>
        <div style={{
          fontSize: '0.7rem', fontWeight: 700, color: 'rgba(140,180,220,0.5)',
          textTransform: 'uppercase', letterSpacing: '0.1em',
        }}>
          📝 Voice-over Script
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <span style={{
            background: 'rgba(0,163,255,0.1)', border: '1px solid rgba(0,163,255,0.25)',
            borderRadius: 6, padding: '2px 10px', fontSize: '0.65rem', fontWeight: 700, color: '#00a3ff'
          }}>
            {totalWords} words
          </span>
          <span style={{
            background: 'rgba(0,229,160,0.1)', border: '1px solid rgba(0,229,160,0.25)',
            borderRadius: 6, padding: '2px 10px', fontSize: '0.65rem', fontWeight: 700, color: '#00e5a0'
          }}>
            ~{mins}:{secs.toString().padStart(2, '0')}
          </span>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {sections.map((section) => {
          const accent = SECTION_COLORS[section.section_id] || '#00a3ff'
          const isOpen = openSection === section.section_id

          return (
            <div key={section.section_id} style={{
              border: `1px solid ${isOpen ? accent + '44' : 'rgba(255,255,255,0.06)'}`,
              borderRadius: 10,
              overflow: 'hidden',
              transition: 'border-color 0.2s ease',
            }}>
              {/* Header */}
              <button
                onClick={() => setOpenSection(isOpen ? null : section.section_id)}
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  background: isOpen ? `${accent}0e` : 'rgba(255,255,255,0.02)',
                  border: 'none',
                  cursor: 'pointer',
                  textAlign: 'left',
                  transition: 'background 0.2s ease',
                }}
              >
                <div style={{
                  width: 8, height: 8, borderRadius: '50%',
                  background: accent, flexShrink: 0,
                  boxShadow: isOpen ? `0 0 8px ${accent}` : 'none',
                }} />
                <div style={{ flex: 1 }}>
                  <div style={{
                    fontSize: '0.75rem', fontWeight: 700,
                    color: isOpen ? accent : 'rgba(200,220,240,0.8)',
                  }}>
                    {section.title}
                  </div>
                  {!isOpen && (
                    <div style={{
                      fontSize: '0.65rem',
                      color: 'rgba(140,180,220,0.4)',
                      marginTop: 2,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                      maxWidth: 400,
                    }}>
                      {section.script_text?.slice(0, 80)}...
                    </div>
                  )}
                </div>
                <div style={{
                  fontSize: '0.65rem', fontWeight: 700, color: accent,
                  background: `${accent}15`, borderRadius: 4, padding: '2px 7px',
                }}>
                  {section.duration_sec}s
                </div>
                <div style={{ color: 'rgba(140,180,220,0.4)', fontSize: '0.7rem' }}>
                  {isOpen ? '▲' : '▼'}
                </div>
              </button>

              {/* Script text */}
              {isOpen && (
                <div style={{
                  padding: '12px 14px 14px',
                  background: `${accent}06`,
                  borderTop: `1px solid ${accent}22`,
                }}>
                  <div style={{
                    fontSize: '0.78rem',
                    color: 'rgba(200,220,240,0.85)',
                    lineHeight: 1.7,
                    fontStyle: 'italic',
                    marginBottom: section.scene_hint ? 10 : 0,
                  }}>
                    "{section.script_text}"
                  </div>
                  {section.scene_hint && (
                    <div style={{
                      fontSize: '0.65rem',
                      color: 'rgba(140,180,220,0.4)',
                      borderTop: `1px solid rgba(255,255,255,0.06)`,
                      paddingTop: 8,
                    }}>
                      🎬 Visual: {section.scene_hint}
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
