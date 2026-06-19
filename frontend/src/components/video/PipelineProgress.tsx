/**
 * PipelineProgress — Animated 6-step pipeline stepper for video generation.
 */
import { VIDEO_STAGES, getStageIndex, type VideoJobStatus } from '../../api/videoApi'

interface PipelineProgressProps {
  status: VideoJobStatus
  progressPct: number
  error?: string | null
}

const bgTheme: Record<string, { bg: string; glow: string }> = {
  story:      { bg: 'rgba(0,163,255,0.12)',  glow: '#00a3ff' },
  script:     { bg: 'rgba(0,229,160,0.12)',  glow: '#00e5a0' },
  storyboard: { bg: 'rgba(160,80,255,0.12)', glow: '#a050ff' },
  audio:      { bg: 'rgba(255,180,0,0.12)',  glow: '#ffb400' },
  visuals:    { bg: 'rgba(255,80,120,0.12)', glow: '#ff5078' },
  composing:  { bg: 'rgba(0,229,200,0.12)',  glow: '#00e5c8' },
}

export function PipelineProgress({ status, progressPct, error }: PipelineProgressProps) {
  const currentIdx = getStageIndex(status)
  const isComplete = status === 'completed'
  const isFailed   = status === 'failed'

  return (
    <div style={{ width: '100%' }}>
      {/* Overall progress bar */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24
      }}>
        <div style={{
          flex: 1,
          height: 8,
          background: 'rgba(255,255,255,0.06)',
          borderRadius: 99,
          overflow: 'hidden',
          border: '1px solid rgba(255,255,255,0.08)',
        }}>
          <div style={{
            height: '100%',
            width: `${progressPct}%`,
            borderRadius: 99,
            background: isFailed
              ? 'linear-gradient(90deg, #ff3c50, #ff6b6b)'
              : isComplete
                ? 'linear-gradient(90deg, #00e5a0, #00a3ff)'
                : 'linear-gradient(90deg, #00a3ff, #7c5cff)',
            transition: 'width 0.8s cubic-bezier(0.4,0,0.2,1)',
            boxShadow: isFailed ? '0 0 12px #ff3c5066' : '0 0 12px #00a3ff66',
          }} />
        </div>
        <span style={{
          fontSize: '0.85rem', fontWeight: 700,
          color: isFailed ? '#ff3c50' : isComplete ? '#00e5a0' : '#00a3ff',
          minWidth: 40, textAlign: 'right',
        }}>
          {progressPct}%
        </span>
      </div>

      {/* Stage steps */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(6, 1fr)',
        gap: 8,
      }}>
        {VIDEO_STAGES.map((stage, idx) => {
          const isActive   = stage.status === status && !isComplete && !isFailed
          const isDone     = isComplete || (currentIdx > idx)
          const isUpcoming = !isDone && !isActive

          const colors = bgTheme[stage.status] || { bg: 'rgba(255,255,255,0.05)', glow: '#fff' }

          return (
            <div
              key={stage.status}
              style={{
                padding: '12px 8px',
                borderRadius: 12,
                background: isDone
                  ? 'rgba(0,229,160,0.08)'
                  : isActive
                    ? colors.bg
                    : 'rgba(255,255,255,0.03)',
                border: `1px solid ${
                  isDone   ? 'rgba(0,229,160,0.3)' :
                  isActive ? colors.glow + '66'     :
                             'rgba(255,255,255,0.06)'
                }`,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: 6,
                transition: 'all 0.4s ease',
                boxShadow: isActive ? `0 0 20px ${colors.glow}22` : 'none',
              }}
            >
              {/* Icon / spinner */}
              <div style={{
                width: 36,
                height: 36,
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '1.1rem',
                background: isDone
                  ? 'rgba(0,229,160,0.2)'
                  : isActive
                    ? colors.bg
                    : 'rgba(255,255,255,0.05)',
                border: `2px solid ${
                  isDone   ? '#00e5a0' :
                  isActive ? colors.glow :
                             'rgba(255,255,255,0.1)'
                }`,
                animation: isActive ? 'spin-slow 3s linear infinite' : 'none',
                position: 'relative',
              }}>
                {isDone ? '✓' : isActive ? stage.icon : stage.icon}
              </div>

              {/* Label */}
              <div style={{
                fontSize: '0.62rem',
                fontWeight: 700,
                textAlign: 'center',
                color: isDone
                  ? '#00e5a0'
                  : isActive
                    ? colors.glow
                    : 'rgba(140,180,220,0.4)',
                letterSpacing: '0.04em',
                textTransform: 'uppercase',
              }}>
                {stage.label}
              </div>

              {/* Active label */}
              {isActive && (
                <div style={{
                  fontSize: '0.55rem',
                  color: 'rgba(140,180,220,0.6)',
                  textAlign: 'center',
                  lineHeight: 1.3,
                }}>
                  {stage.description}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Error message */}
      {isFailed && error && (
        <div style={{
          marginTop: 16,
          padding: '12px 16px',
          borderRadius: 8,
          background: 'rgba(255,60,80,0.1)',
          border: '1px solid rgba(255,60,80,0.3)',
          fontSize: '0.78rem',
          color: '#ff6b7a',
        }}>
          ⚠️ {error}
        </div>
      )}
    </div>
  )
}
