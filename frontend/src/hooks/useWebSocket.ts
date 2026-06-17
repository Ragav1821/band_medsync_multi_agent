import { useEffect, useRef, useCallback } from 'react'
import { useStore } from '../store/appStore'
import { actionPlanApi } from '../api/client'

export function useWebSocket(incidentId: string | null) {
  const wsRef = useRef<WebSocket | null>(null)
  // BLOCKER 4 FIX: stable ref so reconnect closure always reads the current incidentId
  const incidentIdRef = useRef<string | null>(incidentId)
  const { handleWSEvent, setWsConnected, setActionPlan } = useStore()

  // Keep ref in sync with prop
  useEffect(() => { incidentIdRef.current = incidentId }, [incidentId])

  const connect = useCallback((id: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const wsUrl = `ws://localhost:8000/api/v1/ws/incidents/${id}`
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      setWsConnected(true)
      console.log(`[WS] Connected to incident ${id}`)
    }

    ws.onmessage = async (evt) => {
      try {
        const event = JSON.parse(evt.data)
        handleWSEvent(event)

        // BLOCKER 3 FIX: when plan is ready, immediately fetch it instead of waiting for poll
        if (event.event_type === 'plan:ready' && event.incident_id) {
          try {
            const res = await actionPlanApi.get(event.incident_id)
            setActionPlan(event.incident_id, res.data)
          } catch {
            // fallback: polling in ActionPlan page will pick it up within 5s
          }
        }
      } catch (e) {
        console.warn('[WS] Failed to parse event:', e)
      }
    }

    ws.onerror = () => { setWsConnected(false) }
    ws.onclose = () => {
      setWsConnected(false)
      // BLOCKER 4 FIX: read from ref, not from stale closure
      setTimeout(() => {
        const currentId = incidentIdRef.current
        if (wsRef.current === ws && currentId) connect(currentId)
      }, 2000)
    }
  }, [handleWSEvent, setWsConnected, setActionPlan])

  useEffect(() => {
    if (!incidentId) return
    connect(incidentId)
    return () => {
      wsRef.current?.close()
      wsRef.current = null
    }
  }, [incidentId, connect])

  return { isConnected: wsRef.current?.readyState === WebSocket.OPEN }
}
