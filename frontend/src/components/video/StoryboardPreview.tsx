/**
 * StoryboardPreview — Cards for each scene in the generated storyboard.
 * Phase 20.5: Trust indicators, disclosure scene badge, AI pipeline legend.
 */
import type { VideoScene } from '../../api/videoApi'

interface StoryboardPreviewProps {
  scenes: VideoScene[]
}

const BG_COLORS: Record<string, string> = {
  dark_blue:          'linear-gradient(135deg, rgba(5,15,45,0.9), rgba(10,30,80,0.9))',
  dark_red:           'linear-gradient(135deg, rgba(45,5,10,0.9), rgba(80,10,20,0.9))',
  dark_teal:          'linear-gradient(135deg, rgba(5,40,45,0.9), rgba(10,70,80,0.9))',
  dark_purple:        'linear-gradient(135deg, rgba(25,5,50,0.9), rgba(50,10,90,0.9))',
  dark_orange:        'linear-gradient(135deg, rgba(50,25,5,0.9), rgba(90,45,10,0.9))',
  dark_green:         'linear-gradient(135deg, rgba(5,40,20,0.9), rgba(10,70,35,0.9))',
  dark_blue_gradient: 'linear-gradient(135deg, rgba(5,15,45,0.9), rgba(20,50,100,0.9))',
  dark_navy:          'linear-gradient(135deg, rgba(3,10,30,0.95), rgba(8,20,60,0.95))',
}

const ACCENT_COLORS: Record<string, string> = {
  dark_blue:          '#00a3ff',
  dark_red:           '#ff3c50',
  dark_teal:          '#00e5c8',
  dark_purple:        '#a050ff',
  dark_orange:        '#ffb400',
  dark_green:         '#00e582',
  dark_blue_gradient: '#64c8ff',
  dark_navy:          '#4682dc',
}

const ANIM_BADGES: Record<string, { label: string; color: string }> = {
  fade_in_logo:  { label: 'FADE IN',     color: '#00a3ff' },
  slide_in_left: { label: 'SLIDE',       color: '#ff5078' },
  node_spawn:    { label: 'NODE SPAWN',  color: '#00e5c8' },
  timeline_flow: { label: 'TIMELINE',    color: '#a050ff' },
  loop_diagram:  { label: 'LOOP ANIM',  color: '#ffb400' },
  card_reveal:   { label: 'CARD REVEAL', color: '#00e582' },
  approval_stamp:{ label: 'STAMP',       color: '#00a3ff' },
  metric_counter:{ label: 'COUNTER',     color: '#64c8ff' },
}

export function StoryboardPreview({ scenes }: StoryboardPreviewProps) {
  if (!scenes || scenes.length === 0) return null

  return (
    <div>
      <div style={{
        fontSize: '0.7rem', fontWeight: 700, color: 'rgba(140,180,220,0.5)',
        textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 14,
      }}>
        🎬 AI Executive Briefing Storyboard — {scenes.length} Scenes
      </div>

      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
        gap: 12,
      }}>
        {scenes.map((scene) => {
          const isDisclosure = scene.section_id === 'disclosure'
          const bg = BG_COLORS[scene.bg_theme] || BG_COLORS.dark_blue
          const accent = ACCENT_COLORS[scene.bg_theme] || '#00a3ff'
          const animBadge = ANIM_BADGES[scene.animation_type] || {
            label: scene.animation_type?.toUpperCase() || 'STATIC',
            color: '#00a3ff',
          }

          return (
            <div key={scene.scene_num} style={{
              background: bg,
              border: `1px solid ${isDisclosure ? '#ffb40066' : accent + '33'}`,
              borderRadius: 12,
              padding: 16,
              position: 'relative',
              overflow: 'hidden',
              transition: 'transform 0.2s ease, box-shadow 0.2s ease',
            }}
              onMouseEnter={e => {
                (e.currentTarget as HTMLElement).style.transform = 'translateY(-2px)'
                ;(e.currentTarget as HTMLElement).style.boxShadow = `0 8px 24px ${accent}22`
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLElement).style.transform = 'none'
                ;(e.currentTarget as HTMLElement).style.boxShadow = 'none'
              }}
            >
              {/* Scene number badge — top right */}
              <div style={{
                position: 'absolute', top: 10, right: 10,
                background: `${accent}22`,
                border: `1px solid ${accent}44`,
                borderRadius: 6,
                padding: '2px 8px',
                fontSize: '0.65rem',
                fontWeight: 700,
                color: accent,
              }}>
                SCENE {scene.scene_num}
              </div>

              {/* Disclosure badge — top left (Task 2/6) */}
              {isDisclosure && (
                <div style={{
                  position: 'absolute', top: 10, left: 10,
                  background: 'rgba(255,180,0,0.15)',
                  border: '1px solid rgba(255,180,0,0.4)',
                  borderRadius: 6,
                  padding: '2px 8px',
                  fontSize: '0.6rem',
                  fontWeight: 700,
                  color: '#ffb400',
                }}>
                  ⚠ AI DISCLOSURE
                </div>
              )}

              {/* Title */}
              <div style={{
                fontSize: '0.85rem',
                fontWeight: 700,
                color: '#e8f0ff',
                marginBottom: 6,
                paddingRight: 60,
                paddingTop: isDisclosure ? 22 : 0,
              }}>
                {scene.overlay_text || scene.title}
              </div>

              {/* Subtitle */}
              {scene.overlay_subtitle && (
                <div style={{
                  fontSize: '0.68rem',
                  color: accent,
                  marginBottom: 10,
                  opacity: 0.8,
                }}>
                  {scene.overlay_subtitle}
                </div>
              )}

              {/* Visual description */}
              <div style={{
                fontSize: '0.68rem',
                color: 'rgba(140,180,220,0.7)',
                lineHeight: 1.5,
                marginBottom: 12,
              }}>
                {scene.visual_description}
              </div>

              {/* Footer badges */}
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                <span style={{
                  background: `${accent}15`,
                  border: `1px solid ${accent}33`,
                  borderRadius: 4,
                  padding: '2px 7px',
                  fontSize: '0.6rem',
                  fontWeight: 700,
                  color: accent,
                }}>
                  ⏱ {scene.duration_sec}s
                </span>
                <span style={{
                  background: `${animBadge.color}15`,
                  border: `1px solid ${animBadge.color}33`,
                  borderRadius: 4,
                  padding: '2px 7px',
                  fontSize: '0.6rem',
                  fontWeight: 700,
                  color: animBadge.color,
                }}>
                  🎞 {animBadge.label}
                </span>
                {isDisclosure && (
                  <span style={{
                    background: 'rgba(0,229,160,0.1)',
                    border: '1px solid rgba(0,229,160,0.3)',
                    borderRadius: 4,
                    padding: '2px 7px',
                    fontSize: '0.6rem',
                    fontWeight: 700,
                    color: '#00e5a0',
                  }}>
                    🔒 GOVERNANCE
                  </span>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {/* AI Pipeline Tech Stack Legend (Task 6) */}
      <div style={{
        marginTop: 16,
        padding: '10px 14px',
        borderRadius: 8,
        background: 'rgba(255,255,255,0.02)',
        border: '1px solid rgba(255,255,255,0.06)',
        display: 'flex',
        alignItems: 'center',
        gap: 16,
        flexWrap: 'wrap',
      }}>
        <span style={{
          fontSize: '0.6rem', fontWeight: 700,
          color: 'rgba(140,180,220,0.4)',
          textTransform: 'uppercase', letterSpacing: '0.08em',
        }}>
          AI Pipeline
        </span>
        {[
          { label: 'Gemini AI',          color: '#00a3ff' },
          { label: 'gTTS Voice',         color: '#00e5a0' },
          { label: 'Pillow Renders',     color: '#a050ff' },
          { label: 'MoviePy MP4',        color: '#ffb400' },
          { label: 'SQLite Persistence', color: '#ff9c3a' },
        ].map(({ label, color }) => (
          <span key={label} style={{
            fontSize: '0.6rem', fontWeight: 700, color,
            display: 'flex', alignItems: 'center', gap: 4,
          }}>
            <span style={{
              width: 6, height: 6, borderRadius: '50%',
              background: color, display: 'inline-block',
            }} />
            {label}
          </span>
        ))}
      </div>
    </div>
  )
}
