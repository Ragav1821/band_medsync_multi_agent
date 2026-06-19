/**
 * Phase 20 — Video Generator API Client
 * Handles video job creation, status polling, and file download.
 */
import { api } from './client'

// ── Types ────────────────────────────────────────────────────────────────────

export type VideoJobStatus =
  | 'pending'
  | 'story'
  | 'script'
  | 'storyboard'
  | 'audio'
  | 'visuals'
  | 'composing'
  | 'completed'
  | 'failed'

export interface VideoStorySection {
  section_id: string
  title: string
  narrative: string
  key_stat: string
}

export interface VideoScriptSection {
  section_id: string
  title: string
  script_text: string
  duration_sec: number
  scene_hint: string
}

export interface VideoScene {
  scene_num: number
  section_id: string
  title: string
  visual_description: string
  screen_capture_req: string
  animation_type: string
  bg_theme: string
  duration_sec: number
  overlay_text: string
  overlay_subtitle: string
  script_text?: string
  data_overlay?: Record<string, unknown>
}

export interface VideoJob {
  id: string
  incident_id: string
  status: VideoJobStatus
  progress_pct: number
  voice_provider?: string
  created_at: string
  completed_at?: string
  duration_sec?: number
  error_message?: string
  has_video: boolean
  story?: {
    title: string
    hook: string
    section_count: number
    business_impact: Record<string, unknown>
  }
  script?: {
    total_words: number
    estimated_duration_sec: number
    sections: VideoScriptSection[]
  }
  storyboard?: {
    total_scenes: number
    total_duration_sec: number
    scenes: VideoScene[]
    trust_indicators?: {
      compliance_status?: string
      human_review_required?: boolean
      audit_trail_available?: boolean
      negotiation_completed?: boolean
      ai_generated?: boolean
    }
  }
}

// ── Stage metadata ────────────────────────────────────────────────────────────

export const VIDEO_STAGES: Array<{
  status: VideoJobStatus
  label: string
  icon: string
  description: string
}> = [
  { status: 'story',      label: 'Storytelling',  icon: '📖', description: 'AI generates executive narrative' },
  { status: 'script',     label: 'Script',         icon: '📝', description: 'Voice-over script with timing' },
  { status: 'storyboard', label: 'Storyboard',     icon: '🎬', description: 'Visual scene planning' },
  { status: 'audio',      label: 'Voice-over',     icon: '🎙️', description: 'Professional narration audio' },
  { status: 'visuals',    label: 'Scene Visuals',  icon: '🖼️', description: 'Rendering 8 cinematic slides' },
  { status: 'composing',  label: 'Composition',    icon: '🎞️', description: 'Combining into final MP4' },
]

export const STAGE_ORDER: VideoJobStatus[] = ['story', 'script', 'storyboard', 'audio', 'visuals', 'composing', 'completed']

export function getStageIndex(status: VideoJobStatus): number {
  return STAGE_ORDER.indexOf(status)
}

// ── API Methods ───────────────────────────────────────────────────────────────

export const videoApi = {
  /**
   * Kick off a new video generation pipeline for an incident.
   * Returns immediately with job_id — use getJob() to poll.
   */
  generate: (incidentId: string, options?: { voiceProvider?: string; targetDurationSec?: number }) =>
    api.post<{ job_id: string; incident_id: string; status: string; poll_url: string }>
    (`/incidents/${incidentId}/generate-video`, {
      incident_id: incidentId,
      voice_provider: options?.voiceProvider ?? 'gtts',
      target_duration_sec: options?.targetDurationSec ?? 120,
    }),

  /** Get current job status + partial results */
  getJob: (jobId: string) =>
    api.get<VideoJob>(`/video-jobs/${jobId}`),

  /** List all video jobs for an incident */
  listJobs: (incidentId: string) =>
    api.get<VideoJob[]>(`/incidents/${incidentId}/video-jobs`),

  /** Delete a video job and its generated files */
  deleteJob: (jobId: string) =>
    api.delete<{ job_id: string; message: string }>(`/video-jobs/${jobId}`),

  /** Get the download URL for a completed video */
  getDownloadUrl: (jobId: string): string =>
    `/api/v1/video-jobs/${jobId}/download`,
}

/**
 * Poll a video job until it reaches a terminal state (completed / failed).
 * Calls onProgress with each status update. Returns the final job.
 */
export async function pollVideoJob(
  jobId: string,
  onProgress: (job: VideoJob) => void,
  intervalMs = 2000,
  maxWaitMs = 600_000,
): Promise<VideoJob> {
  const start = Date.now()
  while (Date.now() - start < maxWaitMs) {
    await new Promise(r => setTimeout(r, intervalMs))
    try {
      const { data: job } = await videoApi.getJob(jobId)
      onProgress(job)
      if (job.status === 'completed' || job.status === 'failed') {
        return job
      }
    } catch {
      // Network hiccup — keep polling
    }
  }
  throw new Error('Video generation timed out after 10 minutes')
}
