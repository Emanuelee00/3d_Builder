'use client'

import { Component, ReactNode, Suspense, useCallback, useState } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls, Environment, Center } from '@react-three/drei'
import { ScannedModel } from './ScannedModel'

function ViewerFallback({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 w-full h-full bg-[#1a1a1e] text-white/60 text-sm text-center p-6">
      <span>{message}</span>
      <button
        onClick={() => window.location.reload()}
        className="px-4 py-2 rounded-full bg-white/10 hover:bg-white/20 transition-colors text-white"
      >
        Ricarica
      </button>
    </div>
  )
}

// Un fallimento nel parsing del glb o un errore interno di Three.js durante il
// render (non catturabile da Suspense, che gestisce solo il caricamento asincrono)
// mandava in crash l'intero albero React senza error boundary: la pagina
// diventava bianca/inutilizzabile invece di mostrare solo il viewer come rotto.
class ModelErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean }> {
  constructor(props: { children: ReactNode }) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  render() {
    if (this.state.hasError) {
      return <ViewerFallback message="Impossibile visualizzare il modello 3D in questo browser." />
    }
    return this.props.children
  }
}

function Viewer({ modelPath }: { modelPath: string }) {
  const [contextLost, setContextLost] = useState(false)

  // Il contesto WebGL puo' saltare per memoria GPU insufficiente o rendering
  // software senza vera accelerazione hardware (es. sessioni remote/VM). Senza
  // questo listener la pagina restava bloccata su schermo nero invece di
  // offrire un modo per recuperare.
  const handleCreated = useCallback((state: { gl: { domElement: HTMLCanvasElement } }) => {
    const canvas = state.gl.domElement
    canvas.addEventListener('webglcontextlost', (e) => {
      e.preventDefault()
      setContextLost(true)
    })
    canvas.addEventListener('webglcontextrestored', () => {
      setContextLost(false)
    })
  }, [])

  if (contextLost) {
    return <ViewerFallback message="Il contesto grafico è stato perso (memoria GPU insufficiente sul dispositivo)." />
  }

  return (
    <Canvas
      camera={{ position: [2, 1.5, 2.5], fov: 45 }}
      shadows={false}
      dpr={[1, 1.5]}
      onCreated={handleCreated}
    >
      <color attach="background" args={['#1a1a1e']} />
      <ambientLight intensity={0.8} />
      <directionalLight position={[3, 5, 2]} intensity={1.2} />
      <Suspense fallback={null}>
        <Center>
          <ScannedModel modelPath={modelPath} />
        </Center>
        <Environment preset="apartment" resolution={128} />
      </Suspense>
      <OrbitControls autoRotate autoRotateSpeed={0.6} enableDamping />
    </Canvas>
  )
}

export function ModelViewer({ modelPath }: { modelPath: string }) {
  return (
    <ModelErrorBoundary key={modelPath}>
      <Viewer modelPath={modelPath} />
    </ModelErrorBoundary>
  )
}
